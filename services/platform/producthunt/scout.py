# socials producthunt <profile> scout

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

from services.platform.producthunt.support.scout_utils import scout_product_hunt_products

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="Product Hunt Scout CLI Tool")

    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None)
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None)
        sys.exit(1)

    profile_name = PROFILES[profile]['name']

    # profile properties
    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    producthunt_props = platform_props.get('producthunt', {})
    scout_props = producthunt_props.get('scout', {})

    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)
    limit = scout_props.get('count', 10)
    push_to_db = global_props.get('push_to_db', False)

    from datetime import datetime, timedelta
    today = datetime.now()
    target_date_for_scout = today - timedelta(days=1)

    products = []
    
    # checking if some output is already present for today's date to prevent the process again
    existing_file_path = get_product_hunt_output_file_path(profile_name, target_date_for_scout.strftime("%Y%m%d"))
    
    # if products exist for the previous date
    if os.path.exists(existing_file_path):
        log(f"Found existing Product Hunt data for {target_date_for_scout.strftime('%Y-%m-%d')} at {existing_file_path}", verbose)
        try:
            import json
            with open(existing_file_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            log(f"Loaded {len(products)} existing products from file.", verbose)
        except Exception as e:
            log(f"Error loading existing data for {target_date_for_scout.strftime('%Y-%m-%d')}: {e}. Will scout fresh data.", verbose, is_error=True)
            products = []

    if not products:
        with Status(f"[white]Scouting Product Hunt leaderboard for {target_date_for_scout.strftime('%Y-%m-%d')} for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            products = scout_product_hunt_products(profile_name=profile_name, verbose=verbose, status=status, limit=limit, headless=headless)
            status.stop()
            log(f"Product Hunt leaderboard Scouting complete for {target_date_for_scout.strftime('%Y-%m-%d')}. scoutd {len(products)} products.", verbose)

    if push_to_db and products:
        storage = get_storage('producthunt', profile_name, 'action', verbose)
        if storage:
            batch_id = datetime.now().strftime("%d%m%y%H%M")
            success = storage.push_content(products, batch_id, verbose)
            if success:
                log(f"Successfully pushed {len(products)} products to database with batch ID: {batch_id}", verbose)
            else:
                log("Failed to push products to database", verbose, is_error=True)
        else:
            log("Failed to initialize storage for database push", verbose, is_error=True)

if __name__ == "__main__":
    main()
