# socials x <profile> reply home
# socials x <profile> reply profiles

# add api if want to use api (will only work if api is available)

import os
import sys
import argparse

from dotenv import load_dotenv
from urllib.parse import quote

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories

from services.platform.x.support.home import run_home_mode, post_approved_home_mode_replies

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="X Replies CLI Tool")
    
    # Profile
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    # Mode
    parser.add_argument("mode", choices=["home", "profiles"], help="Reply mode: 'home' for home feed replies, 'profiles' for profile-based replies")

    # API
    parser.add_argument("--api", action="store_true", help="Use X API to post replies instead of browser automation. This is faster and more reliable than browser-based posting.")

    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve all generated replies and skip manual review.")
    parser.add_argument("--dry-run", action="store_true", help="Generate replies but do not actually post them.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        sys.exit(1)

    profile_name = PROFILES[profile]['name']
    custom_prompt = PROFILES[profile]['prompts']['reply_generation']

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    x_props = platform_props.get('x', {})
    reply_props = x_props.get('reply', {})

    count = reply_props.get('count', 17)
    ignore_video_tweets = reply_props.get('ignore_video_tweets', False)
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    if args.mode == "home":
        with Status(f'[white]Running Home Mode: Gemini reply to tweets for {profile_name}...[/white]', spinner="dots", console=console) as status:
            driver, _ = run_home_mode(profile_name, custom_prompt, max_tweets=count, status=status, ignore_video_tweets=ignore_video_tweets, post_via_api=args.api, verbose=verbose, headless=headless)
            status.stop()
            log("Home Mode Results:", verbose, status=status, api_info=None, log_caller_file="replies.py")

            if args.auto_approve:
                log("Auto-approving all generated replies...", verbose, log_caller_file="replies.py")
                replies_dir = os.path.join("tmp", "replies", profile_name)
                replies_path = os.path.join(replies_dir, 'replies.json')
                if os.path.exists(replies_path):
                    import json
                    with open(replies_path, 'r') as f:
                        items = json.load(f)
                    for item in items:
                        if item.get('status') == 'ready_for_approval':
                            item['status'] = 'approved'
                    with open(replies_path, 'w') as f:
                        json.dump(items, f, indent=2)
            else:
                log("Press Enter here when you are done reviewing the generated replies and want to post them.", verbose, status=None, api_info=None, log_caller_file="replies.py")
                input()

            if not args.dry_run:
                with Status(f"[white]Posting generated replies for {profile_name}...[/white]", spinner="dots", console=console) as status:
                    summary = post_approved_home_mode_replies(driver, profile_name, post_via_api=args.api, verbose=verbose)
                    status.stop()
                    log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", verbose, status=status, api_info=None, log_caller_file="replies.py")
            else:
                log("Dry run: Skipping posting replies.", verbose, log_caller_file="replies.py")

            if driver and not args.api:
                driver.quit()

    if args.mode == "profiles":
        target_profiles = PROFILES[profile].get('target_profiles', [])
        if not target_profiles:
            log(f"No target profiles found for {profile}. Add target_profiles to profiles.py", verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        query_parts = [f"from:{p}" for p in target_profiles]
        search_query = f"({' OR '.join(query_parts)})"
        encoded_query = quote(search_query)
        specific_search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

        with Status(f'[white]Running Profiles Mode: Gemini reply to tweets from {", ".join(target_profiles)} for {profile_name}...[/white]', spinner="dots", console=console) as status:
            driver, _ = run_home_mode(profile_name, custom_prompt, max_tweets=count, status=status, ignore_video_tweets=ignore_video_tweets, post_via_api=args.api, verbose=verbose, headless=headless, specific_search_url=specific_search_url)
            status.stop()
            log("Profiles Mode Results:", verbose, status=status, api_info=None, log_caller_file="replies.py")

            log("Press Enter here when you are done reviewing the generated replies and want to post them.", verbose, status=None, api_info=None, log_caller_file="replies.py")
            input()

            with Status(f"[white]Posting generated replies for {profile_name}...[/white]", spinner="dots", console=console) as status:
                summary = post_approved_home_mode_replies(driver, profile_name, post_via_api=args.api, verbose=verbose)
                status.stop()
                log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", verbose, status=status, api_info=None, log_caller_file="replies.py")

            if driver and not args.api:
                driver.quit()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
