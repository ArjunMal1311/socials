import os
import sys
import time
import json
import argparse

from datetime import datetime
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from typing import Optional, Dict, Any
from services.support.web_driver_handler import setup_driver
from services.platform.instagram.support.instagram_replies_utils import scrape_instagram_reels_comments, generate_instagram_replies, post_instagram_reply, move_to_next_reel, download_instagram_reel, parse_instagram_comments_robust, extract_structured_comments

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None, api_info: Optional[Dict[str, Any]] = None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_error:
        level = "ERROR"
        style = "bold red"
    else:
        level = "INFO"
        style = "white"
    
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    if api_info:
        api_message = api_info.get('message', '')
        if api_message:
            formatted_message += f" | API: {api_message}"
    
    console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Instagram Replies CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--scrape-and-reply", action="store_true", help="Scrape comments from Instagram Reels and generate replies.")
    parser.add_argument("--max-comments", type=int, default=50, help="Maximum number of comments to scrape (default: 50).")
    parser.add_argument("--gemini-api-key", type=str, help="Gemini API key for generating replies.")
    parser.add_argument("--number-of-reels", type=int, default=1, help="Number of Instagram Reels to process (default: 1).")
    parser.add_argument("--parse", action="store_true", help="Parse the existing instagram_comments_dump.html file and print the JSON output.")
    parser.add_argument("--clear", action="store_true", help="Clear all generated files (HTML dumps, downloaded reels) for the profile.")

    args = parser.parse_args()

    if args.scrape_and_reply:
        profile_name = args.profile
        driver = None
        try:
            user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'browser-data', profile_name))
            profile_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instagram', profile_name))
            os.makedirs(profile_base_dir, exist_ok=True)

            with Status(f"[white]Initializing WebDriver for profile '{profile_name}'...[/white]", spinner="dots", console=console) as status:
                driver, setup_messages = setup_driver(user_data_dir, profile=profile_name)
                for msg in setup_messages:
                    status.update(f"[white]{msg}[/white]")
                    time.sleep(0.1)
                status.update("[white]WebDriver initialized.[/white]")
            status.stop()

            if not driver:
                _log("WebDriver could not be initialized. Aborting.", args.verbose, is_error=True)
                sys.exit(1) 

            with Status("[white]Navigating to Instagram Reels...[/white]", spinner="dots", console=console) as status:
                driver.get("https://www.instagram.com/reels/")
                time.sleep(5)
            status.stop()

            for i in range(args.number_of_reels):
                video_path = None
                _log(f"--- Processing Reel {i+1}/{args.number_of_reels} ---", args.verbose)
                
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
                    _log(f"Scraped {len(structured_comments_for_gemini)} comments from {reel_url}.", args.verbose)
                    
                    with Status(f"[white]Downloading Instagram Reel: {reel_url}...[/white]", spinner="dots", console=console) as status:
                        video_path = download_instagram_reel(reel_url, profile_name, status, verbose=args.verbose)
                    status.stop()

                    if video_path:
                        _log(f"Downloaded reel to: {video_path}", args.verbose)
                    else:
                        _log("Could not download Instagram Reel. Continuing without video content.", args.verbose)

                    with Status("[white]Generating reply...[/white]", spinner="dots", console=console) as status:
                        generated_reply = generate_instagram_replies(
                            comments_data=structured_comments_for_gemini,
                            video_path=video_path,
                            api_key=args.gemini_api_key,
                            verbose=args.verbose
                        )
                        status.stop()
                        
                        if generated_reply and not generated_reply.startswith("Error"):
                            _log("Generated Reply:", args.verbose)
                            _log(f"{generated_reply}", args.verbose)
                            
                            with Status("[white]Attempting to post reply...[/white]", spinner="dots", console=console) as status:
                                post_instagram_reply(driver, generated_reply, status, verbose=args.verbose)
                            status.stop()
                            _log("Reply process completed.", args.verbose)
                        else:
                            _log(f"Failed to generate reply: {generated_reply}", args.verbose, is_error=True)
                else:
                    _log("No comments scraped or no reel URL found to generate replies for.", args.verbose)
                
                if i < args.number_of_reels - 1:
                    if not move_to_next_reel(driver, verbose=args.verbose):
                        _log("Could not move to the next reel. Ending process.", args.verbose)
                        break
                else:
                    _log("Finished processing all requested reels.", args.verbose)

        except Exception as e:
            _log(f"An unexpected error occurred: {e}", args.verbose, is_error=True)
        finally:
            if driver:
                driver.quit()
                _log("WebDriver closed.", args.verbose)
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
                _log(f"Deleted downloaded reel: {video_path}", args.verbose)

    elif args.parse:
        profile_name = args.profile 
        profile_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instagram', profile_name))
        os.makedirs(profile_base_dir, exist_ok=True)

        html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")
        if os.path.exists(html_dump_path):
            with open(html_dump_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            cleaned_html = parse_instagram_comments_robust(html_content)
            
            cleaned_dump_path = os.path.join(profile_base_dir, "instagram_comments_cleaned_dump.html")
            with open(cleaned_dump_path, "w", encoding="utf-8") as f:
                f.write(cleaned_html)
            _log(f"Cleaned HTML (without classes) saved to: {cleaned_dump_path}", args.verbose)
            
            structured_comments = extract_structured_comments(cleaned_html)
            console.print(json.dumps(structured_comments, indent=2))
        else:
            _log(f"Error: {html_dump_path} not found. Please run --scrape-and-reply first to generate the dump file.", args.verbose, is_error=True)

    elif args.clear:
        profile_name = args.profile
        profile_base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instagram', profile_name))
        html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")
        
        if os.path.exists(html_dump_path):
            os.remove(html_dump_path)
            _log(f"Deleted HTML dump: {html_dump_path}", args.verbose)

        reels_dir = os.path.join(profile_base_dir, "reels")
        if os.path.exists(reels_dir):
            for file_name in os.listdir(reels_dir):
                file_path = os.path.join(reels_dir, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(reels_dir)
            _log(f"Deleted reels directory: {reels_dir}", args.verbose)

        _log(f"Cleared all generated files for profile '{profile_name}'.", args.verbose)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
