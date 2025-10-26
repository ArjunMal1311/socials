import os
import re
import argparse

from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from typing import Optional, Dict, Any

from profiles import PROFILES

from services.support.path_config import initialize_directories
from services.platform.x.support.post_watcher import run_watcher
from services.platform.x.support.clear_media_files import clear_media
from services.platform.x.support.display_tweets import display_scheduled_tweets
from services.platform.x.support.generate_sample_posts import generate_sample_posts
from services.platform.x.support.generate_captions import generate_captions_for_schedule
from services.platform.x.support.process_scheduled_tweets import process_scheduled_tweets
from services.platform.x.support.move_tomorrow_schedules import move_tomorrows_from_schedule2

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if status and (is_error or verbose):
        status.stop()

    log_message = message
    if is_error:
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[scheduler.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[scheduler.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[scheduler.py] {timestamp}|[{color}]{message}[/{color}]")

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="Twitter Scheduler CLI Tool")
    
    # Profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use")
    
    # Processing Tweets (Scheduling)
    parser.add_argument("--process-tweets", action="store_true", help="Process and schedule tweets.")
    # Make content for multiple days (--sched-tom will just schedule posts for the next day)
    parser.add_argument("--sched-tom", action="store_true", help="Before processing, move tomorrow's tweets from schedule2.json to schedule.json and schedule them.")

    # Generating sample
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample posts.")
    parser.add_argument("--gap-type", type=str, choices=["random", "fixed"], default="random", help="Type of gap for sample post generation.")
    parser.add_argument("--min-gap-hours", type=int, default=0, help="Minimum gap hours for random gap.")
    parser.add_argument("--min-gap-minutes", type=int, default=1, help="Minimum gap minutes for random gap.")
    parser.add_argument("--max-gap-hours", type=int, default=0, help="Maximum gap hours for random gap.")
    parser.add_argument("--max-gap-minutes", type=int, default=50, help="Maximum gap minutes for random gap.")
    parser.add_argument("--fixed-gap-hours", type=int, default=2, help="Fixed gap hours.")
    parser.add_argument("--fixed-gap-minutes", type=int, default=0, help="Fixed gap minutes.")
    parser.add_argument("--tweet-text", type=str, default="This is a sample tweet!", help="Default tweet text for sample posts.")
    parser.add_argument("--start-image-number", type=int, default=1, help="Starting image number for sample posts.")
    parser.add_argument("--num-days", type=int, default=1, help="Number of days to schedule sample posts for.")
    parser.add_argument("--start-date", type=str, help="Start date for scheduling in YYYY-MM-DD format.")
    
    # Generate Captions
    parser.add_argument("--generate-captions", action="store_true", help="Generate Gemini captions for scheduled media.")

    # Display Scheduled Tweets
    parser.add_argument("--display-tweets", action="store_true", help="Display scheduled tweets.")
    # can pass but .env can handle 
    parser.add_argument("--gemini-api-key", type=str, help="Gemini API key for caption generation.")
    
    # Clear All media
    parser.add_argument("--clear-media", action="store_true", help="Delete all media files for the profile in the schedule folder.")

    # Additional
    parser.add_argument("--show-complete", action="store_true", help="Show complete logs (INFO level and above).") 
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    # Post Watcher
    parser.add_argument("--post-watch", action="store_true", help="Continuously watch and post scheduled tweets/community posts.")
    parser.add_argument("--post-watch-profiles", type=str, help="Comma-separated profile keys for post watcher.")
    parser.add_argument("--post-watch-interval", type=int, default=60, help="Polling interval in seconds for post watcher (default: 60).")
    parser.add_argument("--post-watch-run-once", action="store_true", help="Run post watcher a single scan and exit.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        _log(f"Profile '{args.profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
        _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
        return

    if args.post_watch:
        profile_keys = [p.strip() for p in (args.post_watch_profiles or args.profile).split(',') if p.strip()]
        run_watcher(profile_keys=profile_keys, interval_seconds=args.post_watch_interval, run_once=args.post_watch_run_once, verbose=args.verbose)
        return

    if getattr(args, 'sched_tom', False) and not args.process_tweets and not args.display_tweets and not args.generate_sample and not args.generate_captions and not args.clear_media:
        moved = move_tomorrows_from_schedule2(args.profile, verbose=args.verbose)
        if moved:
            _log(f"{moved} tweet(s) moved from schedule2.json to schedule.json for tomorrow.", args.verbose, status=None, api_info=None)
        else:
            _log("No tomorrow tweets found in schedule2.json. schedule.json was cleared if present.", args.verbose, status=None, api_info=None)
        return

    if args.display_tweets:
        display_scheduled_tweets(args.profile, verbose=args.verbose)
    elif args.generate_sample:
        if args.gap_type == "random":
            gap_minutes_min = args.min_gap_hours * 60 + args.min_gap_minutes
            gap_minutes_max = args.max_gap_hours * 60 + args.max_gap_minutes
            if gap_minutes_min > gap_minutes_max:
                _log("Minimum gap cannot be greater than maximum gap. Adjusting maximum to minimum.", args.verbose, status=None, api_info=None)
                gap_minutes_max = gap_minutes_min
            generate_sample_posts(gap_minutes_min=gap_minutes_min, gap_minutes_max=gap_minutes_max, scheduled_tweet_text=args.tweet_text, start_image_number=args.start_image_number, profile_name=args.profile, num_days=args.num_days, start_date=args.start_date, verbose=args.verbose)
        else:
            generate_sample_posts(fixed_gap_hours=args.fixed_gap_hours, fixed_gap_minutes=args.fixed_gap_minutes, scheduled_tweet_text=args.tweet_text, start_image_number=args.start_image_number, profile_name=args.profile, num_days=args.num_days, start_date=args.start_date, verbose=args.verbose)
        _log("Sample posts generated and saved to schedule.json", args.verbose, status=None, api_info=None)
        
    elif args.process_tweets:
        if args.sched_tom:
            moved = move_tomorrows_from_schedule2(args.profile, verbose=args.verbose)
            if moved:
                _log(f"{moved} tweet(s) moved from schedule2.json to schedule.json for tomorrow.", args.verbose, status=None, api_info=None)
            else:
                _log("No tomorrow tweets found in schedule2.json.", args.verbose, status=None, api_info=None)
        process_scheduled_tweets(args.profile, headless=not args.no_headless, verbose=args.verbose)
        _log("Processing complete.", args.verbose, status=None, api_info=None)
    elif args.generate_captions:
        gemini_api_key = args.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            _log("Please provide a Gemini API key using --gemini-api-key argument or set GEMINI_API_KEY environment variable.", args.verbose, is_error=True, status=None, api_info=None)
            return
        generate_captions_for_schedule(args.profile, gemini_api_key, verbose=args.verbose)
    elif args.clear_media:
        clear_media(args.profile)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()

