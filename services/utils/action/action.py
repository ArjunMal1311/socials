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
    parser.add_argument("profiles", nargs='*', type=str, help="Profile names to use (optional - if not specified, uses all profiles with platform assignments from profiles.py)")

    args = parser.parse_args()

    profile_names = args.profiles

    verbose = False
    if profile_names and profile_names[0] in PROFILES:
        profile_config = PROFILES[profile_names[0]]
        profile_props = profile_config.get('properties', {})
        global_props = profile_props.get('global', {})
        verbose = global_props.get('verbose', False)

    profile_platform_map = {}
    profiles_to_check = profile_names if profile_names else PROFILES.keys()

    for profile_name in profiles_to_check:
        if profile_name in PROFILES:
            profile_config = PROFILES[profile_name]
            action_config = profile_config.get('properties', {}).get('utils', {}).get('action', {})
            platforms_config = action_config.get('platforms', {})

            for platform, assigned_profiles in platforms_config.items():
                if isinstance(assigned_profiles, list):
                    if platform not in profile_platform_map:
                        profile_platform_map[platform] = []
                    profile_platform_map[platform].extend(assigned_profiles)

    for platform in profile_platform_map:
        profile_platform_map[platform] = list(set(profile_platform_map[platform]))

    if not profile_platform_map:
        if profile_names:
            log(f"No platform assignments found for specified profiles: {', '.join(profile_names)}", is_error=True, log_caller_file="action.py")
        else:
            log("No platform assignments found in any profiles. Configure 'utils.action.platforms' in profile configurations", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    log(f"Using platform assignments from profile configurations: {profile_platform_map}", verbose, log_caller_file="action.py")

    all_profiles = set()
    for profiles in profile_platform_map.values():
        all_profiles.update(profiles)
    profile_names = list(all_profiles)

    all_assigned_profiles = set()
    for profiles in profile_platform_map.values():
        all_assigned_profiles.update(profiles)

    invalid_profiles = [p for p in all_assigned_profiles if p not in PROFILES]
    if invalid_profiles:
        log(f"Profiles not found in PROFILES: {', '.join(invalid_profiles)}", is_error=True, log_caller_file="action.py")
        log(f"Available profiles: {', '.join(PROFILES.keys())}", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    invalid_platforms = [p for p in profile_platform_map.keys() if not validate_platform(p)]
    if invalid_platforms:
        log(f"Unsupported platforms: {', '.join(invalid_platforms)}", is_error=True, log_caller_file="action.py")
        log(f"Supported platforms: {', '.join(['x', 'linkedin'])}", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    for platform, profiles in profile_platform_map.items():
        for profile_name in profiles:
            profile_config = PROFILES[profile_name]
            profile_props = profile_config.get('properties', {})
            platform_props = profile_props.get('platform', {})

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

    for platform, profiles in profile_platform_map.items():
        for profile_name in profiles:
            storage = get_storage(platform, profile_name, 'action', verbose)
            if not storage:
                log(f"Failed to initialize storage for profile {profile_name} on platform {platform}", verbose, is_error=True, log_caller_file="action.py")
                sys.exit(1)
            storages[profile_name][platform] = storage

    drivers = {}
    try:
        platform_profile_str = []
        for platform, profiles in profile_platform_map.items():
            platform_profile_str.append(f"{platform}: {', '.join(profiles)}")
        log(f"Starting Multi-Platform Action System: {', '.join(platform_profile_str)}", verbose, log_caller_file="action.py")

        log("Scraping and storing content for specified profile-platform combinations...", verbose, log_caller_file="action.py")
        batch_id, drivers = scrape_and_store(profile_platform_map, storages, verbose)

        log("Waiting for approval...", verbose, log_caller_file="action.py")
        wait_for_approval(batch_id, verbose)

        log("Posting approved content...", verbose, log_caller_file="action.py")
        post_approved_content(profile_platform_map, storages, batch_id, drivers, verbose)

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