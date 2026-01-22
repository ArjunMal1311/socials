# socials utils <profile1> <profile2> action

import os
import sys
import argparse

from dotenv import load_dotenv

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.support.storage.storage_factory import get_storage, validate_platform

from services.utils.action.support import scrape_and_store, wait_for_approval, post_approved_content

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Social Media Action System")
    parser.add_argument("profiles", nargs='+', type=str, help="Profile names to use (space-separated for multiple profiles)")

    args = parser.parse_args()

    profile_names = args.profiles

    invalid_profiles = [p for p in profile_names if p not in PROFILES]
    if invalid_profiles:
        log(f"Profiles not found in PROFILES: {', '.join(invalid_profiles)}", is_error=True, log_caller_file="action.py")
        log(f"Available profiles: {', '.join(PROFILES.keys())}", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    platform = 'x'
    profile_config = PROFILES[profile_names[0]]
    profile_props = profile_config.get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)

    if not validate_platform(platform):
        log(f"Unsupported platform: {platform}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)

    storages = {}
    for profile_name in profile_names:
        storage = get_storage(platform, profile_name, 'action', verbose)
        if not storage:
            log(f"Failed to initialize storage for profile {profile_name}", verbose, is_error=True, log_caller_file="action.py")
            sys.exit(1)
        storages[profile_name] = storage

    drivers = {}
    try:
        log(f"Starting Multi-Profile Action System for {platform} profiles: {', '.join(profile_names)}", verbose, log_caller_file="action.py")

        log("Scraping and storing content for all profiles...", verbose, log_caller_file="action.py")
        batch_id, drivers = scrape_and_store(profile_names, storages, verbose)

        log("Waiting for approval...", verbose, log_caller_file="action.py")
        wait_for_approval(batch_id, verbose)

        log("Posting approved content...", verbose, log_caller_file="action.py")
        post_approved_content(profile_names, storages, batch_id, drivers, verbose)

        log("Multi-profile action system completed successfully!", verbose, log_caller_file="action.py")

    except KeyboardInterrupt:
        log("Multi-profile action system interrupted by user", verbose, log_caller_file="action.py")
    except Exception as e:
        log(f"Multi-profile action system failed: {e}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)
    finally:
        # Clean up all drivers
        for profile_name, driver in drivers.items():
            if driver:
                try:
                    driver.quit()
                    log(f"Closed browser for profile: {profile_name}", verbose, log_caller_file="action.py")
                except Exception as e:
                    log(f"Error closing browser for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="action.py")


if __name__ == "__main__":
    main()
