import os
import sys
import time
import json
import argparse

from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_instagram_profile_dir, get_instagram_reels_dir
from services.platform.instagram.support.instagram_replies_utils import scrape_instagram_reels_comments, generate_instagram_replies, post_instagram_reply, move_to_next_reel, download_instagram_reel, parse_instagram_comments_robust, extract_structured_comments

console = Console()


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Instagram Replies CLI Tool")
    
    # Profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use.")

    # Scrape & reply
    parser.add_argument("--scrape-and-reply", action="store_true", help="Scrape comments from Instagram Reels and generate replies.")
    parser.add_argument("--max-comments", type=int, default=50, help="Maximum number of comments to scrape (default: 50).")
    parser.add_argument("--number-of-reels", type=int, default=1, help="Number of Instagram Reels to process (default: 1).")
    parser.add_argument("--parse", action="store_true", help="Parse the existing instagram_comments_dump.html file and print the JSON output.")

    # Clear
    parser.add_argument("--clear", action="store_true", help="Clear all generated files (HTML dumps, downloaded reels) for the profile.")

    # Additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")
    parser.add_argument("--gemini-api-key", type=str, help="Gemini API key for generating replies.")

    args = parser.parse_args()

    if args.scrape_and_reply:
        profile_name = args.profile
        driver = None
        try:
            user_data_dir = get_browser_data_dir(profile_name)
            profile_base_dir = get_instagram_profile_dir(profile_name)
            os.makedirs(profile_base_dir, exist_ok=True)

            with Status(f"[white]Initializing WebDriver for profile '{profile_name}'...[/white]", spinner="dots", console=console) as status:
                driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=not args.no_headless)
                for msg in setup_messages:
                    status.update(f"[white]{msg}[/white]")
                    time.sleep(0.1)
                status.update("[white]WebDriver initialized.[/white]")
            status.stop()

            if not driver:
                log("WebDriver could not be initialized. Aborting.", args.verbose, is_error=True, log_caller_file="replies.py")
                sys.exit(1) 

            with Status("[white]Navigating to Instagram Reels...[/white]", spinner="dots", console=console) as status:
                driver.get("https://www.instagram.com/reels/")
                time.sleep(5)
            status.stop()

            for i in range(args.number_of_reels):
                video_path = None
                log(f"--- Processing Reel {i+1}/{args.number_of_reels} ---", args.verbose, log_caller_file="replies.py")
                
                html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")
                
                with Status(f"[white]Running Instagram Replies: Scraping comments for {profile_name}...[/white]", spinner="dots", console=console) as status:
                    structured_comments_for_gemini, reel_url = scrape_instagram_reels_comments(
                        driver=driver,
                        max_comments=args.max_comments,
                        status=status,
                        html_dump_path=html_dump_path,
                        verbose=args.verbose
                    )
                status.stop()

                if reel_url and structured_comments_for_gemini:
                    log(f"Scraped {len(structured_comments_for_gemini)} comments from {reel_url}.", args.verbose, log_caller_file="replies.py")
                    
                    with Status(f"[white]Downloading Instagram Reel: {reel_url}...[/white]", spinner="dots", console=console) as status:
                        video_path = download_instagram_reel(reel_url, profile_name, status, verbose=args.verbose)
                    status.stop()

                    if video_path:
                        log(f"Downloaded reel to: {video_path}", args.verbose, log_caller_file="replies.py")
                    else:
                        log("Could not download Instagram Reel. Continuing without video content.", args.verbose, log_caller_file="replies.py")

                    with Status("[white]Generating reply...[/white]", spinner="dots", console=console) as status:
                        generated_reply = generate_instagram_replies(
                            comments_data=structured_comments_for_gemini,
                            video_path=video_path,
                            api_key=args.gemini_api_key,
                            verbose=args.verbose
                        )
                        status.stop()
                        
                        if generated_reply and not generated_reply.startswith("Error"):
                            log("Generated Reply:", args.verbose, log_caller_file="replies.py")
                            log(f"{generated_reply}", args.verbose, log_caller_file="replies.py")
                            
                            with Status("[white]Attempting to post reply...[/white]", spinner="dots", console=console) as status:
                                post_instagram_reply(driver, generated_reply, status, verbose=args.verbose)
                            status.stop()
                            log("Reply process completed.", args.verbose, log_caller_file="replies.py")
                        else:
                            log(f"Failed to generate reply: {generated_reply}", args.verbose, is_error=True, log_caller_file="replies.py")
                else:
                    log("No comments scraped or no reel URL found to generate replies for.", args.verbose, log_caller_file="replies.py")
                
                if i < args.number_of_reels - 1:
                    if not move_to_next_reel(driver, verbose=args.verbose):
                        log("Could not move to the next reel. Ending process.", args.verbose, log_caller_file="replies.py")
                        break
                else:
                    log("Finished processing all requested reels.", args.verbose, log_caller_file="replies.py")

        except Exception as e:
            log(f"An unexpected error occurred: {e}", args.verbose, is_error=True, log_caller_file="replies.py")
        finally:
            if driver:
                driver.quit()
                log("WebDriver closed.", args.verbose, log_caller_file="replies.py")
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
                log(f"Deleted downloaded reel: {video_path}", args.verbose, log_caller_file="replies.py")

    elif args.parse:
        profile_name = args.profile 
        profile_base_dir = get_instagram_profile_dir(profile_name)
        os.makedirs(profile_base_dir, exist_ok=True)

        html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")
        if os.path.exists(html_dump_path):
            with open(html_dump_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            cleaned_html = parse_instagram_comments_robust(html_content)
            
            cleaned_dump_path = os.path.join(profile_base_dir, "instagram_comments_cleaned_dump.html")
            with open(cleaned_dump_path, "w", encoding="utf-8") as f:
                f.write(cleaned_html)
            log(f"Cleaned HTML (without classes) saved to: {cleaned_dump_path}", args.verbose, log_caller_file="replies.py")
            
            structured_comments = extract_structured_comments(cleaned_html)
            console.print(json.dumps(structured_comments, indent=2))
        else:
            log(f"Error: {html_dump_path} not found. Please run --scrape-and-reply first to generate the dump file.", args.verbose, is_error=True, log_caller_file="replies.py")

    elif args.clear:
        profile_name = args.profile
        profile_base_dir = get_instagram_profile_dir(profile_name)
        html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")
        
        if os.path.exists(html_dump_path):
            os.remove(html_dump_path)
            log(f"Deleted HTML dump: {html_dump_path}", args.verbose, log_caller_file="replies.py")

        reels_dir = get_instagram_reels_dir(profile_name)
        if os.path.exists(reels_dir):
            for file_name in os.listdir(reels_dir):
                file_path = os.path.join(reels_dir, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(reels_dir)
            log(f"Deleted reels directory: {reels_dir}", args.verbose, log_caller_file="replies.py")

        log(f"Cleared all generated files for profile '{profile_name}'.", args.verbose, log_caller_file="replies.py")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
