# socials ycombinator <profile> scout

import os
import sys
import json
import argparse

from datetime import datetime
from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.storage.storage_factory import get_storage
from services.platform.ycombinator.support.scout_utils import get_yc_companies
from services.support.path_config import initialize_directories, get_ycombinator_output_file_path

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="Y Combinator scout CLI Tool")

    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True)
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True)
        sys.exit(1)

    profile_name = PROFILES[profile]['name']

    # profile properties
    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    ycombinator_props = platform_props.get('ycombinator', {})
    scout_props = ycombinator_props.get('scout', {})

    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)
    limit = scout_props.get('count', 50)
    scroll_attempts = scout_props.get('scroll_attempts', 5)
    push_to_db = global_props.get('push_to_db', False)

    today = datetime.now()
    # checking if some output is already present for today's date to prevent the process again
    existing_file_path = get_ycombinator_output_file_path(profile_name, today.strftime("%Y%m%d"))

    companies = []
    
    # if companies exist
    if os.path.exists(existing_file_path):
        log(f"Found existing Y Combinator data for {today.strftime('%Y-%m-%d')} at {existing_file_path}", verbose)
        try:
            with open(existing_file_path, 'r', encoding='utf-8') as f:
                companies = json.load(f)
            log(f"Loaded {len(companies)} existing companies from file.", verbose)
        except Exception as e:
            log(f"Error loading existing data: {e}. Will Scout fresh data.", verbose, is_error=True)
            companies = []

    if not companies:
        with Status(f"[white]Scraping Y Combinator companies for profile {profile_name}...[/white]", spinner="dots", console=console) as status:
            print(limit)
            companies = get_yc_companies(profile_name=profile_name, verbose=verbose, status=status, limit=limit, scroll_attempts=scroll_attempts, headless=headless)
            status.stop()
            log(f"Y Combinator scraping complete. Scouted {len(companies)} companies.", verbose)

    if push_to_db and companies:
        storage = get_storage('ycombinator', profile_name, 'action', verbose)
        if storage:
            batch_id = datetime.now().strftime("%d%m%y%H%M")
            success = storage.push_content(companies, batch_id, verbose)
            if success:
                log(f"Successfully pushed {len(companies)} companies to database with batch ID: {batch_id}", verbose)
            else:
                log("Failed to push companies to database", verbose, is_error=True)
        else:
            log("Failed to initialize storage for database push", verbose, is_error=True)

if __name__ == "__main__":
    main()
