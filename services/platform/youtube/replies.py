import os
import sys
import time
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_youtube_profile_dir
from services.platform.youtube.support.review_server import start_youtube_review_server
from services.platform.youtube.support.replies_utils import scrape_youtube_shorts_comments, generate_youtube_replies, download_youtube_short, post_youtube_reply_api, post_youtube_reply, move_to_next_short, save_youtube_reply_for_review, load_approved_youtube_replies, mark_youtube_reply_as_posted

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="YouTube Replies CLI Tool")
    
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use.")
    
    # scrape & reply
    parser.add_argument("--scrape-and-reply", action="store_true", help="Scrape comments from YouTube Shorts and generate replies.")
    parser.add_argument("--max-comments", type=int, default=50, help="Maximum number of comments to scrape (default: 50).")
    parser.add_argument("--number-of-shorts", type=int, default=1, help="Number of YouTube Shorts to process (default: 1).")

    # review comments
    parser.add_argument("--review", action="store_true", help="Start a local review server for YouTube reply schedules.")

    # post approved comments
    parser.add_argument("--method", type=str, choices=["api", "direct"], default="api", help="Method to post replies: 'api' for YouTube Data API, 'direct' for Selenium automation (default: api).")
    parser.add_argument("--post-approved", action="store_true", help="Post all approved replies for the selected profile.")

    # additional
    parser.add_argument("--gemini-api-key", type=str, help="Gemini API key for generating replies.")
    parser.add_argument("--account", type=str, default="Default", help="YouTube account name from schedule-videos directory.")
    parser.add_argument("--port", type=int, default=8767, help="Port for review server (default: 8767).")
    parser.add_argument("--clear", action="store_true", help="Clear all generated files for the profile (downloaded videos, review JSONs). ")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        sys.exit(1)
    
    api_key_pool = APIKeyPool(api_keys_string=args.gemini_api_key, verbose=args.verbose)
    api_call_tracker = APICallTracker()
    rate_limiter = RateLimiter(verbose=args.verbose)

    if args.scrape_and_reply:
        profile_name = args.profile
        driver = None
        video_path = None
        try:
            user_data_dir = get_browser_data_dir(profile_name)
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

            with Status("[white]Navigating to YouTube Shorts...[/white]", spinner="dots", console=console) as status:
                driver.get("https://www.youtube.com/shorts")
                time.sleep(5)
            status.stop()

            for i in range(args.number_of_shorts):
                video_path = None
                log(f"--- Processing Short {i+1}/{args.number_of_shorts} ---", args.verbose, log_caller_file="replies.py")
                
                with Status(f"[white]Running YouTube Replies: Scraping comments for {profile_name}...[/white]", spinner="dots", console=console) as status:
                    scraped_comments, _, video_url = scrape_youtube_shorts_comments(profile_name=profile_name, driver=driver, max_comments=args.max_comments, status=status, verbose=args.verbose)
                status.stop()

                if video_url and scraped_comments:
                    log(f"Scraped {len(scraped_comments)} comments from {video_url}.", args.verbose, log_caller_file="replies.py")
                    
                    with Status("[white]Downloading video...[/white]", spinner="dots", console=console) as status:
                        video_path = download_youtube_short(video_url, profile_name, status, verbose=args.verbose)
                    status.stop()

                    if not video_path:
                        log("Failed to download video. Cannot generate reply.", args.verbose, is_error=True, log_caller_file="replies.py")
                        if i < args.number_of_shorts - 1:
                            if not move_to_next_short(driver, verbose=args.verbose):
                                log("Could not move to the next short. Ending process.", args.verbose, is_error=True, log_caller_file="replies.py")
                                break
                        continue

                    video_context = "The video is a short, engaging clip. Focus replies on humor and positivity."
                    
                    with Status("[white]Generating reply...[/white]", spinner="dots", console=console) as status:
                        generated_reply = generate_youtube_replies(profile_name=profile_name, comments_data=scraped_comments, video_context=video_context, video_path=video_path, api_key_pool=api_key_pool, api_call_tracker=api_call_tracker, rate_limiter=rate_limiter, verbose=args.verbose)
                        status.stop()
                        
                        if generated_reply and not generated_reply.startswith("Error"):
                            log("Generated Reply:", args.verbose, log_caller_file="replies.py")
                            log(generated_reply, args.verbose, log_caller_file="replies.py")
                            
                            with Status("[white]Saving reply for review...[/white]", spinner="dots", console=console) as status:
                                save_youtube_reply_for_review(profile_name=profile_name, video_url=video_url, generated_reply=generated_reply, scraped_comments=scraped_comments, video_path=video_path, verbose=args.verbose)
                            status.stop()
                            log("Reply saved for review.", args.verbose, log_caller_file="replies.py")
                        else:
                            log(f"Failed to generate reply: {generated_reply}", args.verbose, is_error=True, log_caller_file="replies.py")
                else:
                    log("No comments scraped or no video URL found to generate replies for.", args.verbose, is_error=True, log_caller_file="replies.py")

                if i < args.number_of_shorts - 1:
                    if not move_to_next_short(driver, verbose=args.verbose):
                        log("Could not move to the next short. Ending process.", args.verbose, is_error=True, log_caller_file="replies.py")
                        break
                else:
                    log("Finished processing all requested shorts.", args.verbose, log_caller_file="replies.py")
            
        except Exception as e:
            log(f"An unexpected error occurred: {e}", args.verbose, is_error=True, log_caller_file="replies.py")
        finally:
            if driver:
                driver.quit()
                log("WebDriver closed.", args.verbose, log_caller_file="replies.py")

    elif args.review:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        port = args.port
        start_youtube_review_server(profile_name, port=port, verbose=args.verbose)

    elif args.post_approved:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']

        with Status(f"[white]Posting approved YouTube replies for {profile_name}...[/white]", spinner="dots", console=console) as status:
            approved_replies = load_approved_youtube_replies(profile_name, verbose=args.verbose)
            total_to_post = len(approved_replies)
            posted_count = 0
            failed_count = 0
            already_posted_count = 0

            if not approved_replies:
                status.update("[yellow]No approved replies found to post.[/yellow]")
                log("No approved replies found to post.", args.verbose, log_caller_file="replies.py")
                return
            
            for i, reply in enumerate(approved_replies):
                reply_id = reply['id']
                video_url = reply['video_url']
                generated_reply_text = reply['generated_reply']
                current_status = reply['status']

                if current_status == 'posted':
                    status.update(f"[yellow]Reply {i+1}/{total_to_post}: '{reply_id}' already posted. Skipping.[/yellow]")
                    already_posted_count += 1
                    continue

                status.update(f"[white]Posting reply {i+1}/{total_to_post} for video {video_url}...[/white]")
                success = post_youtube_reply_api(profile_name, video_url, generated_reply_text, status, verbose=args.verbose)
                
                if success:
                    mark_youtube_reply_as_posted(profile_name, reply_id, verbose=args.verbose)
                    posted_count += 1
                else:
                    failed_count += 1
                    log(f"Failed to post reply '{reply_id}' for video {video_url}.", args.verbose, is_error=True, log_caller_file="replies.py")
            
            status.stop()
            log(f"YouTube Reply Posting Summary for {profile_name}:", args.verbose, log_caller_file="replies.py")
            log(f"Total approved replies: {total_to_post}", args.verbose, log_caller_file="replies.py")
            log(f"Successfully posted: {posted_count}", args.verbose, log_caller_file="replies.py")
            log(f"Failed to post: {failed_count}", args.verbose, log_caller_file="replies.py")
            log(f"Already posted (skipped): {already_posted_count}", args.verbose, log_caller_file="replies.py")

    elif args.clear:
        profile_name = args.profile
        profile_base_dir = get_youtube_profile_dir(profile_name)
        
        shorts_dir = os.path.join(profile_base_dir, "shorts")
        if os.path.exists(shorts_dir):
            for file_name in os.listdir(shorts_dir):
                file_path = os.path.join(shorts_dir, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            os.rmdir(shorts_dir)
            log(f"Deleted shorts directory: {shorts_dir}", args.verbose, log_caller_file="replies.py")

        review_json_path = os.path.join(profile_base_dir, "youtube_replies_for_review.json")
        if os.path.exists(review_json_path):
            os.remove(review_json_path)
            log(f"Deleted review JSON: {review_json_path}", args.verbose, log_caller_file="replies.py")

        log(f"Cleared all generated files for profile '{profile_name}'.", args.verbose, log_caller_file="replies.py")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
