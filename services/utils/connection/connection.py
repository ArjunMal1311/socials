# socials utils <profile> connection

import os
import sys
import json
import glob
import argparse

from profiles import PROFILES
from datetime import datetime
from dotenv import load_dotenv

from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.support.storage.storage_factory import get_storage
from services.support.storage.platforms.connections.connection_storage import ConnectionStorage

from services.utils.connection.support.linkedin_connector import process_linkedin_connections
from services.utils.connection.support.data_extractor import extract_usernames_from_linkedin_urls
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

    target_platform = "linkedin"
    connection_type = "connection"

    verbose = global_props.get('verbose', False)

    connection_storage: ConnectionStorage = get_storage("connections", profile_name, "connection", verbose)
    connection_limit = connection_props.get('count', 15)
    headless = global_props.get('headless', False)

    log(f"Starting LinkedIn connection requests from Product Hunt and Y Combinator data for profile '{profile_name}'", verbose, log_caller_file="connection.py")

    tracking_data = load_connection_tracking(profile_name, target_platform)
    initial_stats = get_stats(tracking_data, target_platform)

    ph_urls = []
    yc_urls = []

    ph_data_dir = f"tmp/product-hunt/{profile_name}"
    if os.path.exists(ph_data_dir):
        ph_files = glob.glob(os.path.join(ph_data_dir, "product_hunt_*.json"))
        if ph_files:
            log(f"Found {len(ph_files)} Product Hunt data files", verbose, log_caller_file="connection.py")
            for file_path in ph_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        companies = json.load(f)
                    for company in companies:
                        founders = company.get("founders", [])
                        for founder in founders:
                            links = founder.get("links", [])
                            for link_url in links:
                                if isinstance(link_url, str) and "linkedin.com/in/" in link_url:
                                    ph_urls.append(link_url)
                except Exception as e:
                    log(f"Error reading PH file {file_path}: {e}", verbose, is_error=True, log_caller_file="data_extractor.py")

    yc_data_dir = f"tmp/ycombinator/{profile_name}"
    if os.path.exists(yc_data_dir):
        yc_files = glob.glob(os.path.join(yc_data_dir, "ycombinator_*.json"))
        if yc_files:
            log(f"Found {len(yc_files)} Y Combinator data files", verbose, log_caller_file="connection.py")
            for file_path in yc_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        companies = json.load(f)
                    for company in companies:
                        founders = company.get("founders", [])
                        for founder in founders:
                            links = founder.get("links", [])
                            for link_url in links:
                                if isinstance(link_url, str) and "linkedin.com/in/" in link_url:
                                    yc_urls.append(link_url)
                except Exception as e:
                    log(f"Error reading YC file {file_path}: {e}", verbose, is_error=True, log_caller_file="data_extractor.py")

    all_urls = ph_urls + yc_urls
    if not all_urls:
        log("No LinkedIn URLs found in Product Hunt or Y Combinator data. Nothing to process.", verbose, is_error=True, log_caller_file="connection.py")
        return

    unique_urls = []
    seen = set()
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    log(f"Found {len(unique_urls)} total unique LinkedIn URLs ({len(ph_urls)} from PH, {len(yc_urls)} from YC)", verbose, log_caller_file="connection.py")

    def process_source_urls(source_urls, source_name, source_tag):
        if not source_urls:
            return 0, 0

        source_pending_urls = get_pending_urls(source_urls, tracking_data, target_platform)
        if not source_pending_urls:
            log(f"All {source_name} URLs have already been processed.", verbose, log_caller_file="connection.py")
            return 0, 0

        source_pending_usernames = extract_usernames_from_linkedin_urls(source_pending_urls)
        source_limited_usernames = source_pending_usernames[:connection_limit] if len(source_pending_usernames) > connection_limit else source_pending_usernames

        if source_limited_usernames:
            log(f"Processing {len(source_limited_usernames)} {source_name} connections (max {connection_limit})", verbose, log_caller_file="connection.py")
            with Status(f"[white]Sending LinkedIn connection requests to {len(source_limited_usernames)} {source_name} profiles...[/white]", spinner="dots", console=console) as status:
                results = process_linkedin_connections(source_limited_usernames, profile_name, verbose, status, limit=connection_limit, headless=headless)

            successful_count = results.get("successful", 0)
            processed_count = 0

            for i, username in enumerate(source_limited_usernames):
                url = None
                for pending_url in source_pending_urls:
                    if extract_usernames_from_linkedin_urls([pending_url])[0] == username:
                        url = pending_url
                        break

                if url:
                    success = i < successful_count
                    mark_as_processed(tracking_data, target_platform, url, success, source_tag, connection_type)
                    processed_count += 1

                    if success:
                        try:
                            connection_storage.upsert_data({
                                "profile_name": profile_name,
                                "platform": target_platform,
                                "connection_type": connection_type,
                                "target_url": url,
                                "target_username": username,
                                "status": "sent",
                                "source": source_tag,
                                "sent_at": datetime.now().isoformat(),
                            })
                            log(f"Successfully saved connection request for {url} to database.", verbose, log_caller_file="connection.py")
                        except Exception as e:
                            log(f"Failed to save connection request for {url} to database: {e}", verbose, is_error=True, log_caller_file="connection.py")

            return processed_count, successful_count

        return 0, 0

    process_source_urls(ph_urls, "Product Hunt", "product_hunt")
    process_source_urls(yc_urls, "Y Combinator", "ycombinator")

    save_connection_tracking(profile_name, tracking_data, target_platform)

    final_stats = get_stats(tracking_data, target_platform)

    log("Connection processing complete!", verbose, log_caller_file="connection.py")
    log(f"Total processed: {final_stats['total_processed']} (+{final_stats['total_processed'] - initial_stats['total_processed']} new)", verbose, log_caller_file="connection.py")
    log(f"Successful: {final_stats['successful']} (+{final_stats['successful'] - initial_stats['successful']} new)", verbose, log_caller_file="connection.py")
    log(f"Failed: {final_stats['failed']} (+{final_stats['failed'] - initial_stats['failed']} new)", verbose, log_caller_file="connection.py")

if __name__ == "__main__":
    main()
