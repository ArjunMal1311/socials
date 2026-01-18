# socials producthunt <profile> scraper

import os
import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.platform.producthunt.support.scraper_utils import scrape_product_hunt_products

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="Product Hunt Scraper CLI Tool")

    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        sys.exit(1)

    profile_name = PROFILES[profile]['name']

    profile_props = PROFILES[profile].get('properties', {})
    verbose = profile_props.get('verbose', False)
    headless = profile_props.get('headless', True)
    limit = profile_props.get('producthunt_limit', 10)

    with Status(f"[white]Scraping Product Hunt previous day leaderboard for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
        scraped_products = scrape_product_hunt_products(profile_name=profile_name, verbose=verbose, status=status, limit=limit, headless=headless)
        status.stop()
        log(f"Previous day leaderboard scraping complete. Scraped {len(scraped_products)} products.", verbose, log_caller_file="scraper.py")

if __name__ == "__main__":
    main()
