# socials reddit <profile> scraper subreddits

import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.reddit.support.scraper_utils import run_reddit_scraper

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Reddit Scraper CLI Tool")

    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use from profiles.py")
    parser.add_argument("mode", choices=["subreddits"], help="Scrape mode: 'subreddits' for scraping configured subreddits")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, log_caller_file="scraper.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)

    if args.mode == "subreddits":
        with Status(f"[white]Running Reddit Scraper for profile '{args.profile}' ...[/white]", spinner="dots", console=console) as status:
            scraped_data = run_reddit_scraper(args.profile, status=status, verbose=verbose)
            if scraped_data:
                log(f"Successfully scraped {len(scraped_data)} Reddit posts.", verbose, status=status, log_caller_file="scraper.py")
            else:
                log("No Reddit data scraped.", verbose, is_error=True, status=status, log_caller_file="scraper.py")

if __name__ == "__main__":
    main()
