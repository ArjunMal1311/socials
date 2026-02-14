# socials linkedin <profile> connection "user1,user2,user3"

import sys
import time
import argparse

from profiles import PROFILES
from dotenv import load_dotenv

from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, initialize_directories

from services.platform.linkedin.support.connection_utils import send_connection_request

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="LinkedIn Connection CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")
    parser.add_argument("usernames", nargs='?', help="Comma-separated list of LinkedIn usernames.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True)
        sys.exit(1)

    # profile parameters
    profile_props = PROFILES[args.profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    browser_profile = args.profile

    if not args.usernames:
        log("No LinkedIn usernames provided.", verbose=verbose, is_error=True)
        sys.exit(1)

    usernames = [username.strip() for username in args.usernames.split(',') if username.strip()]
    if not usernames:
        log("No LinkedIn usernames provided.", verbose=verbose, is_error=True)
        sys.exit(1)

    user_data_dir = get_browser_data_dir(browser_profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile, headless=headless)
            for msg in setup_messages:
                log(msg, verbose, status)
            status.update("[white]WebDriver setup complete.[/white]")

        for username in usernames:
            profile_url = f"https://www.linkedin.com/in/{username}/"
            log(f"Processing connection for: {profile_url}", verbose)
            success = send_connection_request(driver, profile_url, verbose=verbose, status=status)
            if success:
                log(f"Connection request sent successfully to {username}.", verbose)
            else:
                log(f"Failed to send connection request to {username}.", verbose, is_error=True)

            if username != usernames[-1]:
                log(f"Waiting for 25 seconds before proceeding to the next profile...", verbose)
                time.sleep(25)

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
