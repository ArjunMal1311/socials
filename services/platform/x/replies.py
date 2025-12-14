import os
import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.platform.x.support.action import setup_driver
from services.platform.x.support.profile_analyzer import analyze_profile
from services.platform.x.support.eternity_server import start_eternity_review_server
from services.support.path_config import get_browser_data_dir, initialize_directories
from services.platform.x.support.eternity import run_eternity_mode, clear_eternity_files 
from services.platform.x.support.post_to_community import post_to_community_tweet, post_regular_tweet
from services.platform.x.support.post_approved_tweets import post_approved_replies, check_profile_credentials
from services.platform.x.support.action import run_action_mode_online, post_approved_action_mode_replies_online

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="X Replies CLI Tool")
    
    # Profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    # Action Mode
    # parser.add_argument("--action-review", action="store_true", help="Activate action mode with integrated review workflow. Generates replies, saves them for approval, and opens a review server for manual approval before posting.")
    parser.add_argument("--action-mode", action="store_true", help="Activate action mode to generate replies. In this mode, the system scrapes tweets, generates replies using Gemini AI, and saves them to a Google Sheet for review.")
    parser.add_argument("--action-port", type=int, default=8765, help="Port number for the action mode review server. Default is 8765. This is separate from the general --port setting.")
    # Action Mode (Online)
    parser.add_argument("--run-number", type=int, default=1, help="Specify the run number for the current day. Useful for multiple daily runs (e.g., 1 for first run, 2 for second run). Default is 1.")
    # Action Mode (Additional)
    parser.add_argument("--ignore-video-tweets", action="store_true", help="Skip processing of tweets that contain video content during analysis and reply generation. Useful for focusing on text-based interactions.")
    # Action Generate & Post later via API
    # parser.add_argument("--action-generate", action="store_true", help="Activate action mode to generate replies and save them for approval without opening a review server or posting. Useful for batch generation.")
    
    # Eternity Mode
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of approved replies to post. Useful for testing or controlling the volume of posts. Set to 0 for no limit.")
    parser.add_argument("--eternity-mode", action="store_true", help="Activate Eternity mode to collect tweets from specific target profiles, analyze them with Gemini AI, and save generated replies for approval. This mode focuses on targeted profile monitoring.")
    parser.add_argument("--post-approved", action="store_true", help="Post all previously approved replies from the schedule. This will automatically post all replies that have been marked as approved in the review interface.")
    parser.add_argument("--clear-eternity", action="store_true", help="Clear all Eternity schedule files and associated media files for the specified profile. This removes all pending replies and media from the Eternity workflow.")
    parser.add_argument("--eternity-review", action="store_true", help="Start a local web server specifically for reviewing and editing Eternity schedule files. This overrides the general --review flag and uses Eternity-specific settings.")
    parser.add_argument("--post-mode", type=str, default="eternity", help="Specify the posting mode for approved replies. Options: 'eternity' (default), 'action'.")
    parser.add_argument("--eternity-browser", type=str, default=None, help="Specify a custom browser profile to use for Eternity mode scraping. Useful for different authentication contexts. Defaults to the main profile if not specified.")
    parser.add_argument("--eternity-max-tweets", type=int, default=17, help="Maximum number of tweets to collect and process in Eternity mode. Set to 0 for no limit. Default is 17 tweets.")
    
    # Posting to a community
    parser.add_argument("--post-to-community", action="store_true", help="Activate mode to post a tweet directly to a specified community. Requires --post-to-community-tweet and --community-name to be specified.")
    parser.add_argument("--post-to-community-tweet", type=str, default=None, help="The exact tweet text to post to the community. This is required when using --post-to-community mode.")
    # use the --community-name from the community scrape mode
    
    # Normal posting
    parser.add_argument("--post-tweet", type=str, default=None, help="The exact tweet text to post as a regular tweet. Use this instead of --post-to-community-tweet when not posting to a community.")
    
    # Analyze Accounts
    parser.add_argument("--analyze-account", type=str, help="Analyze a specific X account by scraping their tweets and storing them in a Google Sheet. Requires the target profile's username.")

    # Specific Target Profiles
    parser.add_argument("--specific-target-profiles", type=str, default=None, help="Target specific profiles for scraping and analysis. Must match a profile name from the SPECIFIC_TARGET_PROFILES configuration.")
    
    # Community
    parser.add_argument("--community-name", type=str, help="Name of the X community to scrape tweets from. This is required when using --community-scrape mode.")
    
    # Additional
    parser.add_argument("--check", action="store_true", help="Verify that all required API keys and credentials exist in the environment for the specified profile. Checks for authentication tokens and API access.")
    parser.add_argument("--api-key", type=str, default=None, help="Override the default Gemini API key from environment variables. Provide a specific API key for this session only.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")
    parser.add_argument("--post-via-api", action="store_true", help="Use X API to post replies instead of browser automation in action mode. This is faster and more reliable than browser-based posting.")
    parser.add_argument("--reply-max-tweets", type=int, default=17, help="Maximum number of tweets to collect and process in Turbin and Action modes. Set to 0 for no limit. Default is 17 tweets.")
    parser.add_argument("--port", type=int, default=8765, help="Port number for the local web server. Default is 8765.")

    args = parser.parse_args()

    if args.clear_eternity:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Clearing Eternity files for {profile_name}...[/white]", spinner="dots", console=console) as status:
            deleted = clear_eternity_files(profile_name, status=status, verbose=args.verbose)
            status.stop()
            log(f"Done. Deleted items: {deleted}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
        return

    if args.eternity_review:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        port = args.port if args.port != 8765 else 8766
        with Status(f"[white]Starting Eternity Review Server on port {port} for {profile_name}...[/white]", spinner="dots", console=console) as status:
            start_eternity_review_server(profile_name, port=port, verbose=args.verbose, status=status)
        return

    if args.post_approved:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Posting approved replies for {profile_name} from {args.post_mode} schedule...[/white]", spinner="dots", console=console) as status:
            summary = post_approved_replies(profile_name, limit=args.limit, mode=args.post_mode, verbose=args.verbose)
            status.stop()
            log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
        return

    if args.check:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        result = check_profile_credentials(profile_name)
        log(f"Profile: {result['profile']}", args.verbose, status=None, api_info=None, log_caller_file="replies.py")
        for var, info in result['vars'].items():
            status_text = 'OK' if info['present'] else 'MISSING'
            tail = f" (…{info['last4']})" if info['present'] and info['last4'] else ''
            log(f"- {var}: {status_text}{tail}", args.verbose, status=None, api_info=None, log_caller_file="replies.py")
        log(f"All present: {result['ok']}", args.verbose, status=None, api_info=None, log_caller_file="replies.py")
        return
    
    if args.eternity_mode:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompts']['reply_generation']

        with Status(f"[white]Running Eternity Mode: Scraping and analyzing tweets for {profile_name}...[/white]", spinner="dots", console=console) as status:
            results = run_eternity_mode(profile_name, custom_prompt, args.eternity_browser, max_tweets=args.eternity_max_tweets, status=status, headless=not args.no_headless, verbose=args.verbose, ignore_video_tweets=args.ignore_video_tweets)
            status.stop()
            log("Eternity Mode Summary:", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
            log(f"Processed: {len(results)}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
            ready = sum(1 for r in results if r.get('status') == 'ready_for_approval')
            log(f"Ready for approval: {ready}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
            if results:
                log("  Sample:", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
                sample = results[0]
                log(f"Tweet: {sample.get('tweet_text', '')[:70]}...", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
                log(f"Reply: {sample.get('generated_reply', '')[:70]}...", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
                log(f"Media: {', '.join(sample.get('media_files', []))}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
        return

    if args.analyze_account:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        target_profile_name = args.analyze_account
        user_data_dir = get_browser_data_dir(profile_name)

        driver = None
        try:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=not args.no_headless)
            for msg in setup_messages:
                log(msg, args.verbose, status=None, api_info=None, log_caller_file="replies.py")
            with Status(f"[white]Analyzing profile {target_profile_name}...[/white]", spinner="dots", console=console) as status:
                analyze_profile(driver, profile_name, target_profile_name, verbose=args.verbose, status=status)
            status.stop()
        except Exception as e:
            log(f"Error during profile analysis: {e}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        finally:
            if driver:
                driver.quit()
        return

    if args.post_to_community:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        if not args.post_to_community_tweet:
            log("Error: --post-to-community-tweet must be specified when using --post-to-community mode.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        with Status(f"[white]Posting to community {args.community_name} for {profile_name}...[/white]", spinner="dots", console=console) as status:
            post_to_community_tweet(profile_name, args.post_to_community_tweet, args.community_name, verbose=args.verbose, status=status)
        return

    if args.post_tweet:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Posting regular tweet for {profile_name}...[/white]", spinner="dots", console=console) as status:
            post_regular_tweet(profile_name, args.post_tweet, verbose=args.verbose, status=status)
        return

    if args.action_mode:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompts']['reply_generation']
        
        with Status(f'[white]Running Action Mode: Gemini reply to tweets for {profile_name}...[/white]', spinner="dots", console=console) as status:
            driver = run_action_mode_online(profile_name, custom_prompt, max_tweets=args.reply_max_tweets, status=status, ignore_video_tweets=args.ignore_video_tweets, run_number=args.run_number, community_name=args.community_name, post_via_api=args.post_via_api, verbose=args.verbose, headless=not args.no_headless)
            status.stop()
            log("Action Mode Results:", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
            
            log("Press Enter here when you are done reviewing the generated replies in Google Sheet and want to post approved replies.", args.verbose, status=None, api_info=None, log_caller_file="replies.py")
            input()

            with Status(f"[white]Posting approved replies for {profile_name} from action mode schedule...[/white]", spinner="dots", console=console) as status:
                summary = post_approved_action_mode_replies_online(driver, profile_name, run_number=args.run_number, post_via_api=args.post_via_api, verbose=args.verbose)
                status.stop()
                log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None, log_caller_file="replies.py")
            
            if driver and not args.post_via_api:
                driver.quit()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
