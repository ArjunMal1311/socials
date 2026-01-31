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
from services.utils.connection.support.x_connector import process_x_connections, extract_usernames_from_x_urls
from services.utils.connection.support.connection_tracker import load_connection_tracking, save_connection_tracking, get_pending_urls, mark_as_processed, get_stats

console = Console()

def main():
    load_dotenv()
    initialize_directories()

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

    connection_storage: ConnectionStorage = get_storage("connections", profile_name, "connection", verbose)
    connection_limit = connection_props.get('count', 15)
    headless = global_props.get('headless', False)

    log(f"Starting LinkedIn and X connections/follows from Product Hunt and Y Combinator data for profile '{profile_name}'", verbose, log_caller_file="connection.py")

    ph_linkedin_urls = []
    ph_x_urls = []
    yc_linkedin_urls = []
    yc_x_urls = []

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
                                if isinstance(link_url, str):
                                    if "linkedin.com/in/" in link_url:
                                        ph_linkedin_urls.append(link_url)
                                    elif "twitter.com/" in link_url or "x.com/" in link_url:
                                        ph_x_urls.append(link_url)
                except Exception as e:
                    log(f"Error reading PH file {file_path}: {e}", verbose, is_error=True, log_caller_file="connection.py")

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
                                if isinstance(link_url, str):
                                    if "linkedin.com/in/" in link_url:
                                        yc_linkedin_urls.append(link_url)
                                    elif "twitter.com/" in link_url or "x.com/" in link_url:
                                        yc_x_urls.append(link_url)
                except Exception as e:
                    log(f"Error reading YC file {file_path}: {e}", verbose, is_error=True, log_caller_file="connection.py")

    linkedin_urls = ph_linkedin_urls + yc_linkedin_urls
    x_urls = ph_x_urls + yc_x_urls

    if not linkedin_urls and not x_urls:
        log("No LinkedIn or X URLs found in Product Hunt or Y Combinator data. Nothing to process.", verbose, is_error=True, log_caller_file="connection.py")
        return

    log(f"Found {len(linkedin_urls)} LinkedIn URLs ({len(ph_linkedin_urls)} from PH, {len(yc_linkedin_urls)} from YC)", verbose, log_caller_file="connection.py")
    log(f"Found {len(x_urls)} X URLs ({len(ph_x_urls)} from PH, {len(yc_x_urls)} from YC)", verbose, log_caller_file="connection.py")

    def process_platform_urls(platform_urls, platform_name, connection_type_name, source_name, source_tag, processor_func, username_extractor_func):
        if not platform_urls:
            return 0, 0

        tracking_data = load_connection_tracking(profile_name, platform_name.lower())
        initial_stats = get_stats(tracking_data, platform_name.lower())

        source_pending_urls = get_pending_urls(platform_urls, tracking_data, platform_name.lower())
        if not source_pending_urls:
            log(f"All {source_name} {platform_name} URLs have already been processed.", verbose, log_caller_file="connection.py")
            return 0, 0

        source_pending_usernames = username_extractor_func(source_pending_urls)
        source_limited_usernames = source_pending_usernames[:connection_limit] if len(source_pending_usernames) > connection_limit else source_pending_usernames

        if source_limited_usernames:
            log(f"Processing {len(source_limited_usernames)} {source_name} {connection_type_name} (max {connection_limit})", verbose, log_caller_file="connection.py")
            with Status(f"[white]Processing {platform_name} {connection_type_name} to {len(source_limited_usernames)} {source_name} profiles...[/white]", spinner="dots", console=console) as status:
                results = processor_func(source_limited_usernames, profile_name, verbose, status, limit=connection_limit, headless=headless)

            successful_count = results.get("successful", 0)
            processed_count = 0

            for i, username in enumerate(source_limited_usernames):
                url = None
                for pending_url in source_pending_urls:
                    extracted_username = username_extractor_func([pending_url])[0] if username_extractor_func([pending_url]) else None
                    if extracted_username == username:
                        url = pending_url
                        break

                if url:
                    success = i < successful_count
                    mark_as_processed(tracking_data, platform_name.lower(), url, success, source_tag, connection_type_name.lower())
                    processed_count += 1

                    if success:
                        try:
                            connection_storage.upsert_data({
                                "profile_name": profile_name,
                                "platform": platform_name.lower(),
                                "connection_type": connection_type_name.lower(),
                                "target_url": url,
                                "target_username": username,
                                "status": "sent",
                                "source": source_tag,
                                "sent_at": datetime.now().isoformat(),
                            })
                            log(f"Successfully saved {connection_type_name.lower()} request for {url} to database.", verbose, log_caller_file="connection.py")
                        except Exception as e:
                            log(f"Failed to save {connection_type_name.lower()} request for {url} to database: {e}", verbose, is_error=True, log_caller_file="connection.py")

            save_connection_tracking(profile_name, tracking_data, platform_name.lower())

            final_stats = get_stats(tracking_data, platform_name.lower())
            log(f"{platform_name} {source_name} processing complete!", verbose, log_caller_file="connection.py")
            log(f"Total processed: {final_stats['total_processed']} (+{final_stats['total_processed'] - initial_stats['total_processed']} new)", verbose, log_caller_file="connection.py")
            log(f"Successful: {final_stats['successful']} (+{final_stats['successful'] - initial_stats['successful']} new)", verbose, log_caller_file="connection.py")
            log(f"Failed: {final_stats['failed']} (+{final_stats['failed'] - initial_stats['failed']} new)", verbose, log_caller_file="connection.py")

            return processed_count, successful_count

        return 0, 0

    # Process LinkedIn connections
    process_platform_urls(ph_linkedin_urls, "LinkedIn", "Connection", "Product Hunt", "product_hunt", process_linkedin_connections, extract_usernames_from_linkedin_urls)
    process_platform_urls(yc_linkedin_urls, "LinkedIn", "Connection", "Y Combinator", "ycombinator", process_linkedin_connections, extract_usernames_from_linkedin_urls)

    # Process X follows
    process_platform_urls(ph_x_urls, "X", "Follow", "Product Hunt", "product_hunt", process_x_connections, extract_usernames_from_x_urls)
    process_platform_urls(yc_x_urls, "X", "Follow", "Y Combinator", "ycombinator", process_x_connections, extract_usernames_from_x_urls)

    log("All connection/follow processing complete!", verbose, log_caller_file="connection.py")

if __name__ == "__main__":
    main()
