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
    parser.add_argument("--platforms", "--platform", nargs='+', type=str, default=['x'], help="Platform names to use (space-separated for multiple platforms, default: x)")

    args = parser.parse_args()

    profile_names = args.profiles
    platforms = args.platforms

    invalid_profiles = [p for p in profile_names if p not in PROFILES]
    if invalid_profiles:
        log(f"Profiles not found in PROFILES: {', '.join(invalid_profiles)}", is_error=True, log_caller_file="action.py")
        log(f"Available profiles: {', '.join(PROFILES.keys())}", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    invalid_platforms = [p for p in platforms if not validate_platform(p)]
    if invalid_platforms:
        log(f"Unsupported platforms: {', '.join(invalid_platforms)}", is_error=True, log_caller_file="action.py")
        log(f"Supported platforms: {', '.join(['x', 'linkedin'])}", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    for profile_name in profile_names:
        profile_config = PROFILES[profile_name]
        profile_props = profile_config.get('properties', {})
        platform_props = profile_props.get('platform', {})

        for platform in platforms:
            if platform not in platform_props:
                log(f"Profile '{profile_name}' does not have configuration for platform '{platform}'", is_error=True, log_caller_file="action.py")
                log(f"Available platforms for profile '{profile_name}': {', '.join(platform_props.keys())}", is_error=True, log_caller_file="action.py")
                sys.exit(1)

    profile_config = PROFILES[profile_names[0]]
    profile_props = profile_config.get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)

    storages = {}
    for profile_name in profile_names:
        storages[profile_name] = {}
        for platform in platforms:
            storage = get_storage(platform, profile_name, 'action', verbose)
            if not storage:
                log(f"Failed to initialize storage for profile {profile_name} on platform {platform}", verbose, is_error=True, log_caller_file="action.py")
                sys.exit(1)
            storages[profile_name][platform] = storage

    drivers = {}
    try:
        log(f"Starting Multi-Platform Action System for platforms: {', '.join(platforms)} and profiles: {', '.join(profile_names)}", verbose, log_caller_file="action.py")

        log("Scraping and storing content for all profiles and platforms...", verbose, log_caller_file="action.py")
        batch_id, drivers = scrape_and_store(profile_names, platforms, storages, verbose)

        log("Waiting for approval...", verbose, log_caller_file="action.py")
        wait_for_approval(batch_id, verbose)

        log("Posting approved content...", verbose, log_caller_file="action.py")
        post_approved_content(profile_names, platforms, storages, batch_id, drivers, verbose)

        log("Multi-profile action system completed successfully!", verbose, log_caller_file="action.py")

    except KeyboardInterrupt:
        log("Multi-profile action system interrupted by user", verbose, log_caller_file="action.py")
    except Exception as e:
        log(f"Multi-profile action system failed: {e}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)
    finally:
        for profile_name, platform_drivers in drivers.items():
            if platform_drivers:
                for platform, driver in platform_drivers.items():
                    if driver:
                        try:
                            driver.quit()
                            log(f"Closed browser for profile: {profile_name}, platform: {platform}", verbose, log_caller_file="action.py")
                        except Exception as e:
                            log(f"Error closing browser for profile {profile_name}, platform {platform}: {e}", verbose, is_error=True, log_caller_file="action.py")


if __name__ == "__main__":
    main()
