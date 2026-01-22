# socials utils <profile> connection

import sys
import argparse

from profiles import PROFILES
from dotenv import load_dotenv

from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories

from services.utils.connection.support.linkedin_connector import process_linkedin_connections
from services.utils.connection.support.data_extractor import extract_linkedin_urls_from_data, extract_usernames_from_linkedin_urls
from services.utils.connection.support.connection_tracker import load_connection_tracking, save_connection_tracking, get_pending_urls, mark_as_processed, get_stats

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    # this util only supports linkedin for now X will be added next
    # rate limited to 15 connections right now
    parser = argparse.ArgumentParser(description="Connection Utility - Send connection requests from Product Hunt data")
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, log_caller_file="connection.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, log_caller_file="connection.py")
        sys.exit(1)

    profile_name = PROFILES[args.profile]['name']
    profile_props = PROFILES[args.profile].get('properties', {})
    global_props = profile_props.get('global', {})
    utils_props = profile_props.get('utils', {})
    connection_props = utils_props.get('connection', {})

    verbose = global_props.get('verbose', False)
    connection_limit = connection_props.get('count', 15)
    headless = global_props.get('headless', False)

    log(f"Starting connection requests from Product Hunt and Y Combinator data for profile '{profile_name}'", verbose, log_caller_file="connection.py")

    with Status("[white]Extracting LinkedIn URLs from Product Hunt and Y Combinator data...[/white]", spinner="dots", console=console) as status:
        linkedin_urls = extract_linkedin_urls_from_data(profile_name, verbose)

    if not linkedin_urls:
        log("No LinkedIn URLs found in Product Hunt or Y Combinator data. Nothing to process.", verbose, is_error=True, log_caller_file="connection.py")
        return

    log(f"Found {len(linkedin_urls)} LinkedIn URLs from all data sources", verbose, log_caller_file="connection.py")

    linkedin_usernames = extract_usernames_from_linkedin_urls(linkedin_urls)
    log(f"Extracted {len(linkedin_usernames)} unique LinkedIn usernames", verbose, log_caller_file="connection.py")

    tracking_data = load_connection_tracking(profile_name)
    initial_stats = get_stats(tracking_data)

    pending_urls = get_pending_urls(linkedin_urls, tracking_data)

    if not pending_urls:
        log("All LinkedIn URLs have already been processed. Nothing to do.", verbose, log_caller_file="connection.py")
        return

    log(f"Processing {len(pending_urls)} new LinkedIn URLs", verbose, log_caller_file="connection.py")

    pending_usernames = extract_usernames_from_linkedin_urls(pending_urls)

    limited_usernames = pending_usernames[:connection_limit] if len(pending_usernames) > connection_limit else pending_usernames
    with Status(f"[white]Sending LinkedIn connection requests to {len(limited_usernames)} profiles (max {connection_limit})...[/white]", spinner="dots", console=console) as status:
        results = process_linkedin_connections(limited_usernames, profile_name, verbose, status, limit=connection_limit, headless=headless)

    log("Updating connection tracking...", verbose, log_caller_file="connection.py")

    for i, url in enumerate(pending_urls):
        success = i < results.get("successful", 0)
        mark_as_processed(tracking_data, url, success, "product_hunt")

    save_connection_tracking(profile_name, tracking_data)

    final_stats = get_stats(tracking_data)

    log("Connection processing complete!", verbose, log_caller_file="connection.py")
    log(f"Total processed: {final_stats['total_processed']} (+{final_stats['total_processed'] - initial_stats['total_processed']} new)", verbose, log_caller_file="connection.py")
    log(f"Successful: {final_stats['successful']} (+{final_stats['successful'] - initial_stats['successful']} new)", verbose, log_caller_file="connection.py")
    log(f"Failed: {final_stats['failed']} (+{final_stats['failed'] - initial_stats['failed']} new)", verbose, log_caller_file="connection.py")

    if results.get("error"):
        log(f"Note: Process completed with errors: {results['error']}", verbose, is_error=True, log_caller_file="connection.py")

if __name__ == "__main__":
    main()
