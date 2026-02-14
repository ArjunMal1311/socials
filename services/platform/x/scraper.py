# socials x <profile> scraper home
# socials x <profile> scraper community "startup"
# socials x <profile> scraper profiles
# socials x <profile> scraper url

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
from services.platform.x.support.scraper_utils import scrape_tweets

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="X Scraper CLI Tool")

    # Profile
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    # Mode and target
    parser.add_argument("mode", choices=["home", "community", "profiles", "url"], help="Scrape mode: 'home' for home feed, 'community' for community scraping, 'profiles' for target profiles, 'url' for specific URL")
    parser.add_argument("target", nargs='?', help="Target for scraping (community name, or optional for other modes)")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        sys.exit(1)

    profile_name = PROFILES[profile]['name']

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    x_props = platform_props.get('x', {})
    scraper_props = x_props.get('scraper', {})

    browser_profile = global_props.get('browser_profile')
    max_tweets = scraper_props.get('max_tweets', 500)
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    if args.mode == "home":
        with Status(f"[white]Scraping home feed for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_tweets = scrape_tweets(scrape_type="home", target_name="feed", profile_name=profile_name, browser_profile=None, max_tweets=max_tweets, headless=headless, status=status, verbose=verbose)
            status.stop()
            log(f"Home feed scraping complete. Scraped {len(scraped_tweets)} tweets.", verbose, log_caller_file="scraper.py")

    elif args.mode == "community":
        community_name = args.target
        if not community_name:
            log("Community name is required for community scraping.", verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Scraping community '{community_name}' for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            log(f"DEBUG: Using max_tweets = {max_tweets}", verbose, log_caller_file="scraper.py")
            scraped_tweets = scrape_tweets(scrape_type="community", target_name=community_name, profile_name=profile_name, browser_profile=browser_profile, max_tweets=max_tweets, headless=headless, status=status, verbose=verbose)
            status.stop()
            log(f"Community scraping complete. Scraped {len(scraped_tweets)} tweets.", verbose, log_caller_file="scraper.py")

    elif args.mode == "profiles":
        target_profiles = PROFILES[profile].get('target_profiles', [])
        if not target_profiles:
            log(f"No target profiles found for {profile}. Add target_profiles to profiles.py", verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        query_parts = [f"from:{p}" for p in target_profiles]
        search_query = f"({' OR '.join(query_parts)})"
        encoded_query = quote(search_query)
        specific_search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

        with Status(f"[white]Scraping profiles {', '.join(target_profiles)} for {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_tweets = scrape_tweets(scrape_type="profiles", target_name="search", profile_name=profile_name, browser_profile=browser_profile, max_tweets=max_tweets, headless=headless, status=status, verbose=verbose, specific_search_url=specific_search_url)
            status.stop()
            log(f"Profiles scraping complete. Scraped {len(scraped_tweets)} tweets.", verbose, log_caller_file="scraper.py")

    elif args.mode == "url":
        specific_url = profile_props.get('specific_url')
        if not specific_url:
            log(f"No specific_url found in properties for profile {profile}. Add specific_url to profiles.py", verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Scraping specific URL for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_tweets = scrape_tweets(scrape_type="url", target_name="custom", profile_name=profile_name, browser_profile=browser_profile, max_tweets=max_tweets, headless=headless, status=status, verbose=verbose, specific_search_url=specific_url)
            status.stop()
            log(f"URL scraping complete. Scraped {len(scraped_tweets)} tweets.", verbose, log_caller_file="scraper.py")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
