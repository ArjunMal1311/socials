import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.x.support.community_scraper_utils import scrape_community_tweets
from services.platform.x.support.tweet_analyzer import analyze_community_tweets_for_engagement

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="X Scraper CLI Tool")

    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    # community
    parser.add_argument("--community-name", type=str, help="Name of the X community to scrape tweets from. This is required when using --community-scrape mode.")
    # use other browser profile for scraping (will use different account but data will be saved under --profile mentioned)
    parser.add_argument("--browser-profile", type=str, default=None, help="Browser profile to use for community scraping. Useful for different authentication contexts. Defaults to the main profile if not specified.")
    parser.add_argument("--max-tweets", type=int, default=500, help="Maximum number of tweets to scrape in community mode. Set to 0 for no limit. Default is 1000 tweets.")
    parser.add_argument("--community-scrape", action="store_true", help="Activate community scraping mode to collect tweets from specific X communities. Requires --community-name to be specified.")

    # analysis
    parser.add_argument("--suggest-engaging-tweets", action="store_true", help="Analyze scraped community tweets using AI to identify the most engaging content and suggest optimal tweets for interaction. Requires --community-name.")

    # additional
    parser.add_argument("--api-key", type=str, default=None, help="Override the default Gemini API key from environment variables. Provide a specific API key for this session only.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    if args.community_scrape:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, log_caller_file="scraper.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']

        if not args.community_name:
            log("--community-name is required for community scraping.", args.verbose, is_error=True, log_caller_file="scraper.py")
            parser.print_help()
            sys.exit(1)

        with Status(f"[white]Scraping community '{args.community_name}' for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_tweets = scrape_community_tweets(community_name=args.community_name, profile_name=profile_name, browser_profile=args.browser_profile, max_tweets=args.max_tweets, headless=not args.no_headless, status=status, verbose=args.verbose)
            status.stop()
            log(f"Community scraping complete. Scraped {len(scraped_tweets)} tweets.", args.verbose, log_caller_file="scraper.py")
        return

    if args.suggest_engaging_tweets:
        profile = args.profile
        if profile not in PROFILES:
            log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, log_caller_file="scraper.py")
            log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        profile_name = PROFILES[profile]['name']

        if not args.community_name:
            log("--community-name is required for suggesting engaging tweets.", args.verbose, is_error=True, log_caller_file="scraper.py")
            parser.print_help()
            sys.exit(1)
        
        with Status(f"[white]Analyzing tweets from '{args.community_name}' for engagement for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            suggestions = analyze_community_tweets_for_engagement(profile_key=args.profile, community_name=args.community_name, api_key=args.api_key, verbose=args.verbose)
            status.stop()

            if suggestions:
                log("Engagement Suggestions:", args.verbose, log_caller_file="scraper.py")
                for suggestion in suggestions:
                    log(f"- {suggestion.get('suggestion', 'N/A')}", args.verbose, log_caller_file="scraper.py")
            else:
                log("No engagement suggestions generated.", args.verbose, is_error=False, log_caller_file="scraper.py")
        return

    parser.print_help()

if __name__ == "__main__":
    main()
