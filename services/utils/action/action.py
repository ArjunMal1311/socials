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
    parser.add_argument("profile", type=str, help="Profile name to use")

    args = parser.parse_args()

    profile_name = args.profile

    if profile_name not in PROFILES:
        log(f"Profile '{profile_name}' not found in PROFILES", is_error=True, log_caller_file="action.py")
        sys.exit(1)

    profile_config = PROFILES[profile_name]
    profile_props = profile_config.get('properties', {})
    platform = 'x'
    verbose = profile_props.get('verbose', False)

    if not validate_platform(platform):
        log(f"Unsupported platform: {platform}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)

    storage = get_storage(platform, profile_name, 'action', verbose)
    if not storage:
        log(f"Failed to initialize storage for platform {platform}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)

    driver = None
    try:
        log(f"Starting Action System for {platform} profile: {profile_name}", verbose, log_caller_file="action.py")

        log("Scraping and storing content...", verbose, log_caller_file="action.py")
        batch_id, driver = scrape_and_store(profile_name, storage, verbose)

        log("Waiting for approval...", verbose, log_caller_file="action.py")
        wait_for_approval(batch_id, verbose)

        log("Posting approved content...", verbose, log_caller_file="action.py")
        post_approved_content(profile_name, storage, batch_id, driver, verbose)

        log("Action system completed successfully!", verbose, log_caller_file="action.py")

    except KeyboardInterrupt:
        log("Action system interrupted by user", verbose, log_caller_file="action.py")
    except Exception as e:
        log(f"Action system failed: {e}", verbose, is_error=True, log_caller_file="action.py")
        sys.exit(1)
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
