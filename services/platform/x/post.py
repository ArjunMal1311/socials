# socials x <profile> post generate --days 3
# socials x <profile> post process
# socials x <profile> post clear-media
# socials x <profile> post watch

import os
import sys
import argparse

from dotenv import load_dotenv
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.platform.x.support.post_watcher import run_watcher
from services.platform.x.support.clear_media_files import clear_media
from services.platform.x.support.generate_sample_posts import generate_sample_posts
from services.platform.x.support.process_scheduled_tweets import process_scheduled_tweets

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="X Post Scheduler CLI Tool")

    # Profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use")

    # Mode
    parser.add_argument("mode", choices=["generate", "process", "clear-media", "watch"], help="Post mode: 'generate' for sample posts, 'process' for scheduling, 'clear-media' for cleanup, 'watch' for post watcher")

    # Generate options
    parser.add_argument("--days", type=int, help="Number of days to generate sample posts for")

    # Watch options (none needed - uses profile settings)

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="post.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    verbose = profile_props.get('verbose', False)
    headless = profile_props.get('headless', True)
    post_watcher_interval = profile_props.get('post_watcher_interval', 60)
    gap_type = profile_props.get('gap_type', 'random')
    min_gap_hours = profile_props.get('min_gap_hours', 0)
    min_gap_minutes = profile_props.get('min_gap_minutes', 1)
    max_gap_hours = profile_props.get('max_gap_hours', 0)
    max_gap_minutes = profile_props.get('max_gap_minutes', 50)
    fixed_gap_hours = profile_props.get('fixed_gap_hours', 2)
    fixed_gap_minutes = profile_props.get('fixed_gap_minutes', 0)
    tweet_text = profile_props.get('tweet_text', 'This is a sample tweet!')
    start_image_number = profile_props.get('start_image_number', 1)
    num_days = args.days if args.days is not None else profile_props.get('num_days', 1)

    if args.mode == "generate":
        if gap_type == "random":
            gap_minutes_min = min_gap_hours * 60 + min_gap_minutes
            gap_minutes_max = max_gap_hours * 60 + max_gap_minutes
            if gap_minutes_min > gap_minutes_max:
                log("Minimum gap cannot be greater than maximum gap. Adjusting maximum to minimum.", verbose, status=None, api_info=None, log_caller_file="post.py")
                gap_minutes_max = gap_minutes_min
            generate_sample_posts(gap_minutes_min=gap_minutes_min, gap_minutes_max=gap_minutes_max, scheduled_tweet_text=tweet_text, start_image_number=start_image_number, profile_name=profile, num_days=num_days, verbose=verbose)
        else:
            generate_sample_posts(fixed_gap_hours=fixed_gap_hours, fixed_gap_minutes=fixed_gap_minutes, scheduled_tweet_text=tweet_text, start_image_number=start_image_number, profile_name=profile, num_days=num_days, verbose=verbose)
        log("Sample posts generated and saved to schedule.json", verbose, status=None, api_info=None, log_caller_file="post.py")

    elif args.mode == "process":
        process_scheduled_tweets(profile, headless=headless, verbose=verbose)
        log("Processing complete.", verbose, status=None, api_info=None, log_caller_file="post.py")

    elif args.mode == "clear-media":
        clear_media(profile, verbose=verbose)

    elif args.mode == "watch":
        run_watcher(profile_keys=[profile], interval_seconds=post_watcher_interval, verbose=verbose)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()

