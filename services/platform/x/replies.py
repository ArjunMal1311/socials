import re
import os
import sys
import time
import argparse
import threading
from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console
from typing import Optional, Dict, Any

from profiles import PROFILES, SPECIFIC_TARGET_PROFILES
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from services.platform.x.support.action import setup_driver
from services.platform.x.support.profile_analyzer import analyze_profile
from services.platform.x.support.post_to_community import post_to_community_tweet
from services.platform.x.support.eternity_server import start_eternity_review_server 
from services.support.path_config import get_browser_data_dir, initialize_directories
from services.platform.x.support.action_server import start_action_mode_review_server
from services.platform.x.support.community_scraper_utils import scrape_community_tweets
from services.platform.x.support.eternity import run_eternity_mode, clear_eternity_files 
from services.platform.x.support.tweet_analyzer import analyze_community_tweets_for_engagement
from services.platform.x.support.turbin import run_turbin_mode, clear_turbin_files, serve_turbin_review
from services.platform.x.support.post_approved_tweets import post_approved_replies, check_profile_credentials
from services.platform.x.support.action import run_action_mode, run_action_mode_with_review, post_approved_action_mode_replies, run_action_mode_online, post_approved_action_mode_replies_online

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
        console.print(f"[x-replies.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[x-replies.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="X Replies CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")
    parser.add_argument("--action-mode", action="store_true", help="Activate action mode to automatically generate and post replies to tweets using AI analysis. This mode will scrape recent tweets, analyze them with Gemini AI, and generate contextual replies.")
    parser.add_argument("--turbin-mode", action="store_true", help="Activate Turbin mode to collect and analyze tweets, then save generated replies for manual review and approval. This mode processes up to 17 tweets and generates AI-powered responses.")
    parser.add_argument("--clear", action="store_true", help="Clear all Turbin schedule files and associated media files for the specified profile. This removes all pending replies and media from the Turbin workflow.")
    parser.add_argument("--review", action="store_true", help="Start a local web server for reviewing and editing Turbin schedule files. Opens a web interface where you can approve, edit, or reject generated replies before posting.")
    parser.add_argument("--port", type=int, default=8765, help="Port number for the review server. Default is 8765 for Turbin mode, 8766 for Eternity mode. Other mode-specific flags will override this default.")
    parser.add_argument("--post-approved", action="store_true", help="Post all previously approved replies from the schedule. This will automatically post all replies that have been marked as approved in the review interface.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of approved replies to post. Useful for testing or controlling the volume of posts. Set to 0 for no limit.")
    parser.add_argument("--post-mode", type=str, choices=["turbin", "eternity"], default="turbin", help="Specify which schedule to post from: 'turbin' for Turbin-generated replies or 'eternity' for Eternity-generated replies. Default is 'turbin'.")
    parser.add_argument("--check", action="store_true", help="Verify that all required API keys and credentials exist in the environment for the specified profile. Checks for authentication tokens and API access.")
    parser.add_argument("--api-key", type=str, default=None, help="Override the default Gemini API key from environment variables. Provide a specific API key for this session only.")
    parser.add_argument("--eternity-mode", action="store_true", help="Activate Eternity mode to collect tweets from specific target profiles, analyze them with Gemini AI, and save generated replies for approval. This mode focuses on targeted profile monitoring.")
    parser.add_argument("--eternity-browser", type=str, default=None, help="Specify a custom browser profile to use for Eternity mode scraping. Useful for different authentication contexts. Defaults to the main profile if not specified.")
    parser.add_argument("--eternity-max-tweets", type=int, default=17, help="Maximum number of tweets to collect and process in Eternity mode. Set to 0 for no limit. Default is 17 tweets.")
    parser.add_argument("--clear-eternity", action="store_true", help="Clear all Eternity schedule files and associated media files for the specified profile. This removes all pending replies and media from the Eternity workflow.")
    parser.add_argument("--eternity-review", action="store_true", help="Start a local web server specifically for reviewing and editing Eternity schedule files. This overrides the general --review flag and uses Eternity-specific settings.")
    parser.add_argument("--community-scrape", action="store_true", help="Activate community scraping mode to collect tweets from specific X communities. Requires --community-name to be specified.")
    parser.add_argument("--community-name", type=str, help="Name of the X community to scrape tweets from. This is required when using --community-scrape mode.")
    parser.add_argument("--max-tweets", type=int, default=1000, help="Maximum number of tweets to scrape in community mode. Set to 0 for no limit. Default is 1000 tweets.")
    parser.add_argument("--browser-profile", type=str, default=None, help="Browser profile to use for community scraping. Useful for different authentication contexts. Defaults to the main profile if not specified.")
    parser.add_argument("--suggest-engaging-tweets", action="store_true", help="Analyze scraped community tweets using AI to identify the most engaging content and suggest optimal tweets for interaction. Requires --community-name.")
    parser.add_argument("--action-review", action="store_true", help="Activate action mode with integrated review workflow. Generates replies, saves them for approval, and opens a review server for manual approval before posting.")
    parser.add_argument("--action-generate", action="store_true", help="Activate action mode to generate replies and save them for approval without opening a review server or posting. Useful for batch generation.")
    parser.add_argument("--post-action-approved", action="store_true", help="Post all approved replies from the action mode schedule. This will post all replies that have been marked as approved in the action mode workflow.")
    parser.add_argument("--post-action-approved-sequential", action="store_true", help="Post all approved replies from the action mode schedule in sequential order. Designed for automated execution workflows where replies should be posted one after another.")
    parser.add_argument("--online", action="store_true", help="Use Google Sheets integration for review and posting in action mode. This enables cloud-based collaboration and review workflows.")
    parser.add_argument("--ignore-video-tweets", action="store_true", help="Skip processing of tweets that contain video content during analysis and reply generation. Useful for focusing on text-based interactions.")
    parser.add_argument("--run-number", type=int, default=1, help="Specify the run number for the current day. Useful for multiple daily runs (e.g., 1 for first run, 2 for second run). Default is 1.")
    parser.add_argument("--action-port", type=int, default=8765, help="Port number for the action mode review server. Default is 8765. This is separate from the general --port setting.")
    parser.add_argument("--post-to-community", action="store_true", help="Activate mode to post a tweet directly to a specified community. Requires --post-to-community-tweet and --community-name to be specified.")
    parser.add_argument("--post-to-community-tweet", type=str, default=None, help="The exact tweet text to post to the community. This is required when using --post-to-community mode.")
    parser.add_argument("--post-via-api", action="store_true", help="Use X API to post replies instead of browser automation in action mode. This is faster and more reliable than browser-based posting.")
    parser.add_argument("--specific-target-profiles", type=str, default=None, help="Target specific profiles for scraping and analysis. Must match a profile name from the SPECIFIC_TARGET_PROFILES configuration.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")
    parser.add_argument("--analyze-account", type=str, help="Analyze a specific X account by scraping their tweets and storing them in a Google Sheet. Requires the target profile's username.")

    args = parser.parse_args()

    if args.clear:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Clearing Turbin files for {profile_name}...[/white]", spinner="dots", console=console) as status:
            deleted = clear_turbin_files(profile_name, status=status)
            status.stop()
            _log(f"Done. Deleted items: {deleted}", args.verbose, status=status, api_info=None)
        return

    if args.clear_eternity:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Clearing Eternity files for {profile_name}...[/white]", spinner="dots", console=console) as status:
            deleted = clear_eternity_files(profile_name, status=status)
            status.stop()
            _log(f"Done. Deleted items: {deleted}", args.verbose, status=status, api_info=None)
        return

    if args.eternity_review:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        port = args.port if args.port != 8765 else 8766
        start_eternity_review_server(profile_name, port=port)
        return

    if args.review:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        
        serve_turbin_review(profile_name, port=args.port)
        return

    if args.post_approved:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        with Status(f"[white]Posting approved replies for {profile_name} from {args.post_mode} schedule...[/white]", spinner="dots", console=console) as status:
            summary = post_approved_replies(profile_name, limit=args.limit, mode=args.post_mode)
            status.stop()
            _log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None)
        return

    if args.check:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']
        result = check_profile_credentials(profile_name)
        _log(f"Profile: {result['profile']}", args.verbose, status=None, api_info=None)
        for var, info in result['vars'].items():
            status_text = 'OK' if info['present'] else 'MISSING'
            tail = f" (…{info['last4']})" if info['present'] and info['last4'] else ''
            _log(f"- {var}: {status_text}{tail}", args.verbose, status=None, api_info=None)
        _log(f"All present: {result['ok']}", args.verbose, status=None, api_info=None)
        return
    
    if args.community_scrape:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']

        if not args.community_name:
            _log("--community-name is required for community scraping.", args.verbose, is_error=True, status=None, api_info=None)
            parser.print_help()
            sys.exit(1)

        with Status(f"[white]Scraping community '{args.community_name}' for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_tweets = scrape_community_tweets(
                community_name=args.community_name,
                profile_name=profile_name,
                browser_profile=args.browser_profile,
                max_tweets=args.max_tweets
            )
            status.stop()
            _log(f"Community scraping complete. Scraped {len(scraped_tweets)} tweets.", args.verbose, status=status, api_info=None)
        return

    if args.suggest_engaging_tweets:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        profile_name = PROFILES[profile]['name']

        if not args.community_name:
            _log("--community-name is required for suggesting engaging tweets.", args.verbose, is_error=True, status=None, api_info=None)
            parser.print_help()
            sys.exit(1)
        
        with Status(f"[white]Analyzing tweets from '{args.community_name}' for engagement for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            suggestions = analyze_community_tweets_for_engagement(
                profile_key=args.profile,
                community_name=args.community_name,
                api_key=args.api_key
            )
            status.stop()

            if suggestions:
                _log("Engagement Suggestions:", args.verbose, status=status, api_info=None)
                for suggestion in suggestions:
                    _log(f"- {suggestion.get('suggestion', 'N/A')}", args.verbose, status=status, api_info=None)
            else:
                _log("No engagement suggestions generated.", args.verbose, is_error=False, status=status, api_info=None)
        return

    if args.eternity_mode:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompt']

        with Status(f"[white]Running Eternity Mode: Scraping and analyzing tweets for {profile_name}...[/white]", spinner="dots", console=console) as status:
            results = run_eternity_mode(profile_name, custom_prompt, args.eternity_browser, max_tweets=args.eternity_max_tweets, status=status)
            status.stop()
            _log("Eternity Mode Summary:", args.verbose, status=status, api_info=None)
            _log(f"  Processed: {len(results)}", args.verbose, status=status, api_info=None)
            ready = sum(1 for r in results if r.get('status') == 'ready_for_approval')
            _log(f"  Ready for approval: {ready}", args.verbose, status=status, api_info=None)
            if results:
                _log("  Sample:", args.verbose, status=status, api_info=None)
                sample = results[0]
                _log(f"Tweet: {sample.get('tweet_text', '')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Reply: {sample.get('generated_reply', '')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Media: {', '.join(sample.get('media_files', []))}", args.verbose, status=status, api_info=None)
        return

    if args.analyze_account:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        target_profile_name = args.analyze_account
        user_data_dir = get_browser_data_dir(profile_name)

        driver = None
        try:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=not args.no_headless)
            for msg in setup_messages:
                _log(msg, args.verbose, status=None, api_info=None)
            analyze_profile(driver, profile_name, target_profile_name, verbose=args.verbose)
        except Exception as e:
            _log(f"Error during profile analysis: {e}", args.verbose, is_error=True, status=None, api_info=None)
        finally:
            if driver:
                driver.quit()
        return

    if args.action_generate:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompt']

        with Status(f"[white]Running Action Mode Generation: Scraping and analyzing tweets for {profile_name}...[/white]", spinner="dots", console=console) as status:
            driver = run_action_mode_online(profile_name, custom_prompt, max_tweets=17, status=status, api_key=args.api_key, ignore_video_tweets=args.ignore_video_tweets, run_number=args.run_number, community_name=args.community_name, post_via_api=args.post_via_api, verbose=args.verbose)
            status.stop()
            if driver:
                driver.quit()
            _log(f"Action mode generation finished for {profile_name}. Replies saved to Google Sheet: {profile_name}_online_replies", args.verbose, status=None, api_info=None)
        return

    if args.action_review:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompt']
        
        specific_search_url = None
        target_profile_name = None
        if args.specific_target_profiles:
            profile_key = args.specific_target_profiles
            if profile_key not in SPECIFIC_TARGET_PROFILES:
                _log(f"Specific target profile '{profile_key}' not found in SPECIFIC_TARGET_PROFILES. Available profiles: {', '.join(SPECIFIC_TARGET_PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
                _log("Please create a profiles.py file based on profiles.sample.py to define your specific target profiles.", args.verbose, is_error=True, status=None, api_info=None)
                sys.exit(1)
            
            target_profiles_list = SPECIFIC_TARGET_PROFILES[profile_key]
            profile_names_for_query = [url.split('/')[-1] for url in target_profiles_list]
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            until_date = today.strftime('%Y-%m-%d')
            since_date = yesterday.strftime('%Y-%m-%d')
            
            from_queries = [f"from%3A{name}" for name in profile_names_for_query]
            query_string = "%20OR%20".join(from_queries)
            specific_search_url = f"https://x.com/search?q=(({query_string}))%20until%3A{until_date}%20since%3A{since_date}&src=typed_query"
            target_profile_name = profile_key

        with Status(f"[white]Running Action Mode with review: Scraping and analyzing tweets for {profile_name}...[/white]", spinner="dots", console=console) as status:
            if args.online:
                driver = run_action_mode_online(profile_name, custom_prompt, max_tweets=17, status=status, api_key=args.api_key, ignore_video_tweets=args.ignore_video_tweets, run_number=args.run_number, community_name=args.community_name, post_via_api=args.post_via_api, specific_search_url=specific_search_url, target_profile_name=target_profile_name, verbose=args.verbose)
                status.stop()
                _log(f"Action mode with online review finished. Review generated replies in Google Sheet: {profile_name}_online_replies", args.verbose, status=None, api_info=None)
                _log("Press Enter here when you are done reviewing and want to post approved replies.", args.verbose, status=None, api_info=None)
                input()
            else:
                driver = run_action_mode_with_review(profile_name, custom_prompt, max_tweets=17, status=status, api_key=args.api_key, ignore_video_tweets=args.ignore_video_tweets, run_number=args.run_number, community_name=args.community_name, post_via_api=args.post_via_api, verbose=args.verbose, headless=not args.no_headless)
                status.stop()
                
        if driver:
            if not args.online:                
                httpd_server = None
                def run_server():
                    nonlocal httpd_server
                    httpd_server = start_action_mode_review_server(profile_name, port=args.action_port)
                
                server_thread = threading.Thread(target=run_server)
                server_thread.daemon = True
                server_thread.start()
                time.sleep(1)

                _log("Press Enter here when you are done reviewing and want to post approved replies.", args.verbose, status=None, api_info=None)
                input()
            
                if httpd_server and hasattr(httpd_server, 'shutdown_server'):
                    httpd_server.shutdown_server()
                    server_thread.join()

            with Status(f"[white]Posting approved replies for {profile_name} from action mode schedule...[/white]", spinner="dots", console=console) as status:
                if args.online:
                    if args.post_via_api:
                        driver.quit()
                        driver = None
                    summary = post_approved_action_mode_replies_online(driver, profile_name, run_number=args.run_number, post_via_api=args.post_via_api, verbose=args.verbose)
                else:
                    summary = post_approved_action_mode_replies(driver, profile_name, verbose=args.verbose)
                status.stop()
                _log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None)
            
            if driver:
                driver.quit()
        return

    if args.post_action_approved_sequential:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        user_data_dir = get_browser_data_dir(profile_name)

        driver = None
        if not args.post_via_api:
            try:
                driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=not args.no_headless)
                for msg in setup_messages:
                    _log(msg, args.verbose, status=None, api_info=None)
            except Exception as e:
                _log(f"Error setting up WebDriver: {e}", args.verbose, is_error=True, status=None, api_info=None)
                sys.exit(1)

        with Status(f"[white]Posting approved replies for {profile_name} from action mode schedule...[/white]", spinner="dots", console=console) as status:
            summary = post_approved_action_mode_replies_online(driver, profile_name, run_number=args.run_number, post_via_api=args.post_via_api, verbose=args.verbose)
            status.stop()
            _log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None)
        
        if driver:
            driver.quit()
        return

    if args.post_action_approved:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        user_data_dir = get_browser_data_dir(profile_name)

        try:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=not args.no_headless)
            for msg in setup_messages:
                _log(msg, args.verbose, status=None, api_info=None)
        except Exception as e:
            _log(f"Error setting up WebDriver: {e}", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        with Status(f"[white]Posting approved replies for {profile_name} from action mode schedule...[/white]", spinner="dots", console=console) as status:
            summary = post_approved_action_mode_replies(driver, profile_name, verbose=args.verbose)
            status.stop()
            _log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", args.verbose, status=status, api_info=None)
        driver.quit()
        return

    if args.post_to_community:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        tweet_text = args.post_to_community_tweet
        community_name = args.community_name

        if not tweet_text:
            _log("--post-to-community-tweet is required when --post-to-community is active.", args.verbose, is_error=True, status=None, api_info=None)
            parser.print_help()
            sys.exit(1)

        if not community_name:
            _log("--community-name is required when --post-to-community is active.", args.verbose, is_error=True, status=None, api_info=None)
            parser.print_help()
            sys.exit(1)
        
        user_data_dir = get_browser_data_dir(profile_name)

        try:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=False)
            for msg in setup_messages:
                _log(msg, args.verbose, status=None, api_info=None)
        except Exception as e:
            _log(f"Error setting up WebDriver: {e}", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        with Status(f"[white]Posting tweet to community '{community_name}' for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            success = post_to_community_tweet(driver, tweet_text, community_name, status=status)
            status.stop()
            if success:
                _log(f"Successfully posted tweet to community '{community_name}'.", args.verbose, status=status, api_info=None)
            else:
                _log(f"Failed to post tweet to community '{community_name}'.", args.verbose, is_error=True, status=status, api_info=None)
        driver.quit()
        return

    if args.specific_target_profiles:
        profile_key = args.specific_target_profiles
        if profile_key not in SPECIFIC_TARGET_PROFILES:
            _log(f"Specific target profile '{profile_key}' not found in SPECIFIC_TARGET_PROFILES. Available profiles: {', '.join(SPECIFIC_TARGET_PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your specific target profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)
        
        target_profiles_list = SPECIFIC_TARGET_PROFILES[profile_key]
        profile_names_for_query = [url.split('/')[-1] for url in target_profiles_list]
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        until_date = today.strftime('%Y-%m-%d')
        since_date = yesterday.strftime('%Y-%m-%d')
        
        from_queries = [f"from%3A{name}" for name in profile_names_for_query]
        query_string = "%20OR%20".join(from_queries)
        search_url = f"https://x.com/search?q=(({query_string}))%20until%3A{until_date}%20since%3A{since_date}&src=typed_query"
        
        login_profile_name = args.profile
        custom_prompt = PROFILES[login_profile_name]['prompt']
        
        with Status(f"[white]Running Action Mode for specific profiles: Scraping and analyzing tweets for {profile_names_for_query} using login profile {login_profile_name}...[/white]", spinner="dots", console=console) as status:
            driver = run_action_mode_online(
                login_profile_name, custom_prompt, max_tweets=17, status=status,
                api_key=args.api_key, ignore_video_tweets=args.ignore_video_tweets,
                run_number=args.run_number, specific_search_url=search_url, target_profile_name=profile_key, verbose=args.verbose
            )
            status.stop()
            if driver:
                driver.quit()
            _log(f"Action mode generation for specific profiles finished. Replies saved to Google Sheet: {login_profile_name}_online_replies", args.verbose, status=None, api_info=None)
        return

    if args.action_mode:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompt']
        
        with Status(f'[white]Running Action Mode: Gemini reply to tweets for {profile_name}...[/white]', spinner="dots", console=console) as status:
            result = run_action_mode(profile_name, custom_prompt, status=status, ignore_video_tweets=args.ignore_video_tweets, run_number=args.run_number, community_name=args.community_name, post_via_api=args.post_via_api, verbose=args.verbose, headless=not args.no_headless)
            status.stop()
            _log("Action Mode Results:", args.verbose, status=status, api_info=None)
            for res in result:
                _log(f"Tweet: {res.get('tweet_text', 'N/A')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Reply: {res.get('generated_reply', 'N/A')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Status: {res.get('status', 'N/A')}", args.verbose, status=status, api_info=None)
                _log("\n", args.verbose, status=status, api_info=None)

    elif args.turbin_mode:
        profile = args.profile
        if profile not in PROFILES:
            _log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, status=None, api_info=None)
            _log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, status=None, api_info=None)
            sys.exit(1)

        profile_name = PROFILES[profile]['name']
        custom_prompt = PROFILES[profile]['prompt']

        with Status(f"[white]Running Turbin Mode: Collect + Analyze 10 tweets for {profile_name}...[/white]", spinner="dots", console=console) as status:
            results = run_turbin_mode(profile_name, custom_prompt, max_tweets=17, status=status, api_key=args.api_key)
            status.stop()
            _log("Turbin Mode Summary:", args.verbose, status=status, api_info=None)
            _log(f"  Processed: {len(results)}", args.verbose, status=status, api_info=None)
            ready = sum(1 for r in results if r.get('status') == 'ready_for_approval')
            _log(f"  Ready for approval: {ready}", args.verbose, status=status, api_info=None)
            if results:
                _log("  Sample:", args.verbose, status=status, api_info=None)
                sample = results[0]
                _log(f"Tweet: {sample.get('tweet_text', '')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Reply: {sample.get('generated_reply', '')[:70]}...", args.verbose, status=status, api_info=None)
                _log(f"Media: {', '.join(sample.get('media_files', []))}", args.verbose, status=status, api_info=None)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
