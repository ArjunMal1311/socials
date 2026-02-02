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
from services.support.storage.storage_factory import get_storage
from services.support.path_config import initialize_directories, get_product_hunt_output_file_path

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
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    producthunt_props = platform_props.get('producthunt', {})
    scraper_props = producthunt_props.get('scraper', {})

    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)
    limit = scraper_props.get('count', 10)
    push_to_db = global_props.get('push_to_db', False)

    from datetime import datetime, timedelta
    today = datetime.now()
    target_date_for_scrape = today - timedelta(days=1)

    scraped_products = []

    target_file_path = get_product_hunt_output_file_path(profile_name, target_date_for_scrape.strftime("%Y%m%d"))
    if os.path.exists(target_file_path):
        log(f"Found existing Product Hunt data for {target_date_for_scrape.strftime('%Y-%m-%d')} at {target_file_path}", verbose, log_caller_file="scraper.py")
        try:
            import json
            with open(target_file_path, 'r', encoding='utf-8') as f:
                scraped_products = json.load(f)
            log(f"Loaded {len(scraped_products)} existing products from file.", verbose, log_caller_file="scraper.py")
        except Exception as e:
            log(f"Error loading existing data for {target_date_for_scrape.strftime('%Y-%m-%d')}: {e}. Will scrape fresh data.", verbose, is_error=True, log_caller_file="scraper.py")
            scraped_products = []

    if not scraped_products:
        with Status(f"[white]Scraping Product Hunt leaderboard for {target_date_for_scrape.strftime('%Y-%m-%d')} for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            scraped_products = scrape_product_hunt_products(profile_name=profile_name, verbose=verbose, status=status, limit=limit, headless=headless)
            status.stop()
            log(f"Product Hunt leaderboard scraping complete for {target_date_for_scrape.strftime('%Y-%m-%d')}. Scraped {len(scraped_products)} products.", verbose, log_caller_file="scraper.py")

    if push_to_db and scraped_products:
        storage = get_storage('producthunt', profile_name, 'action', verbose)
        if storage:
            batch_id = datetime.now().strftime("%d%m%y%H%M")
            success = storage.push_content(scraped_products, batch_id, verbose)
            if success:
                log(f"Successfully pushed {len(scraped_products)} products to database with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")
            else:
                log("Failed to push products to database", verbose, is_error=True, log_caller_file="scraper.py")
        else:
            log("Failed to initialize storage for database push", verbose, is_error=True, log_caller_file="scraper.py")

if __name__ == "__main__":
    main()
