import os
import sys
import time
import argparse

from profiles import PROFILES

from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.status import Status
from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from services.support.web_driver_handler import setup_driver
from services.platform.linkedin.support.message_generator import generate_linkedin_message
from services.platform.linkedin.support.linkedin_scraper import scrape_linkedin_profile, parse_linkedin_html
from services.support.path_config import get_browser_data_dir, initialize_directories, get_linkedin_output_dir, get_linkedin_html_dir, get_linkedin_data_dir
from services.support.sheets_util import get_google_sheets_service, save_linkedin_message_to_sheet, get_approved_linkedin_messages

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    sheets_service = get_google_sheets_service(verbose=args.verbose)
    if not sheets_service:
        log("Failed to initialize Google Sheets service. Exiting.", True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="LinkedIn DM CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")
    parser.add_argument("--profile-index", type=int, required=True, help="Index of the LinkedIn profile URL to scrape from linkedin_target_profiles.")
    parser.add_argument("--api-key", type=str, default=None, help="Override the default Gemini API key from environment variables.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation.")
    parser.add_argument("--initial-login", action="store_true", help="If set, the script will wait for 60 seconds after opening the browser, allowing for manual login.")
    
    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    linkedin_user_prompt = PROFILES[args.profile].get('linkedin_user_prompt')
    if not linkedin_user_prompt:
        log(f"linkedin_user_prompt not found for profile '{args.profile}'. Please define it in profiles.py.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    target_profiles = PROFILES[args.profile].get('linkedin_target_profiles')
    if not target_profiles or not isinstance(target_profiles, list) or len(target_profiles) == 0:
        log(f"linkedin_target_profiles not found or is empty for profile '{args.profile}'. Please define it in profiles.py.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    if not (0 <= args.profile_index < len(target_profiles)):
        log(f"Invalid --profile-index {args.profile_index}. Must be between 0 and {len(target_profiles) - 1}.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    target_profile_url = target_profiles[args.profile_index]

    user_data_dir = get_browser_data_dir(args.profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=args.profile, headless=not args.no_headless)
            for msg in setup_messages:
                log(msg, args.verbose, status, log_caller_file="dm.py")
            status.update("[white]WebDriver setup complete.[/white]")

        if args.initial_login:
            log("Initial login flag detected. Waiting for 60 seconds to allow manual login...", args.verbose, status, log_caller_file="dm.py")
            time.sleep(60)
            log("Resuming script after initial login delay.", args.verbose, status, log_caller_file="dm.py")
            
        with Status("[white]Fetching approved messages from Google Sheets...[/white]", spinner="dots", console=console) as status:
            approved_messages = get_approved_linkedin_messages(sheets_service, args.profile, verbose=args.verbose, status=status)
            status.update(f"[white]Fetched {len(approved_messages)} approved messages.[/white]")

        with Status("[white]Scraping LinkedIn profile...[/white]", spinner="dots", console=console) as status:
            raw_html = scrape_linkedin_profile(driver, target_profile_url, verbose=args.verbose, status=status)
            status.update("[white]LinkedIn raw HTML scraped.[/white]")

        profile_data = {}
        if raw_html:
            with Status("[white]Parsing LinkedIn HTML content...[/white]", spinner="dots", console=console) as status:
                profile_data = parse_linkedin_html(raw_html, args.profile, verbose=args.verbose, status=status)
                status.update("[white]LinkedIn HTML parsing complete.[/white]")

        profile_name_for_files = profile_data.get("name", args.profile).replace(" ", "_")

        html_output_dir = get_linkedin_html_dir(args.profile)
        os.makedirs(html_output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_output_filename = os.path.join(html_output_dir, f"{profile_name_for_files}_{timestamp}.html")
        with open(html_output_filename, 'w', encoding='utf-8') as f:
            f.write(raw_html)
        log(f"Raw HTML saved to {html_output_filename}", args.verbose, log_caller_file="dm.py")
        
        log("\n--- Profile Data ---", args.verbose, log_caller_file="dm.py")
        log(f"Name: {profile_data.get("name", "N/A")}", args.verbose, log_caller_file="dm.py")
        log(f"Job Title: {profile_data.get("job_title", "N/A")}", args.verbose, log_caller_file="dm.py")
        log(f"Profile Text: {profile_data.get("profile_text", "N/A")[:500]}...", args.verbose, log_caller_file="dm.py")

        if not profile_data.get("profile_text") or len(profile_data["profile_text"].strip()) < 50: 
            log("No significant profile text was parsed. Cannot generate a personalized message.", args.verbose, is_error=True, log_caller_file="dm.py")
            sys.exit(1)

        api_pool = APIKeyPool()
        if args.api_key:
            api_pool.set_explicit_key(args.api_key)
        rate_limiter = RateLimiter()

        with Status("[white]Generating personalized message with Gemini AI...[/white]", spinner="dots", console=console) as status:
            gemini_api_key = api_pool.get_key()
            if not gemini_api_key:
                log("No Gemini API key available. Cannot generate message.", args.verbose, is_error=True, status=status, log_caller_file="dm.py")
                sys.exit(1)
            
            generated_message = generate_linkedin_message(profile_data=profile_data, user_input_prompt=linkedin_user_prompt, api_key=gemini_api_key, profile_name=args.profile, rate_limiter=rate_limiter, verbose=args.verbose, status=status, approved_messages=approved_messages)
            status.update("[white]Message generation complete.[/white]")
        
        log("\n--- Generated Message ---", args.verbose, log_caller_file="dm.py")
        log(generated_message, args.verbose, log_caller_file="dm.py")

        approval_prompt = "\nPress ENTER to approve and save to Google Sheets, or type 'n' (or anything else) and ENTER to discard: "
        user_input = console.input(f"[bold yellow]{approval_prompt}[/bold yellow]")

        if user_input.lower() == '':
            log("Message approved. Saving to Google Sheets...", args.verbose, log_caller_file="dm.py")
            success = save_linkedin_message_to_sheet(sheets_service, args.profile, target_profile_url, profile_data.get("job_title", "N/A"), generated_message, verbose=args.verbose, status=status)
            if success:
                log("Message successfully saved to Google Sheets.", args.verbose, log_caller_file="dm.py")
            else:
                log("Failed to save message to Google Sheets.", args.verbose, is_error=True, log_caller_file="dm.py")
        else:
            log("Message discarded.", args.verbose, log_caller_file="dm.py")


    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="dm.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()