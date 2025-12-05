import os
import sys
import argparse
import time

from profiles import PROFILES

from dotenv import load_dotenv
from rich.console import Console
from rich.status import Status
from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.platform.linkedin.support.connection_utils import send_connection_request
from services.support.path_config import get_browser_data_dir, initialize_directories

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="LinkedIn Connection CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")
    parser.add_argument("--linkedin-usernames", type=str, required=True, help="Comma-separated list of LinkedIn usernames.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation.")
    
    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True, log_caller_file="connection.py")
        sys.exit(1)

    usernames = [username.strip() for username in args.linkedin_usernames.split(',') if username.strip()]
    if not usernames:
        log("No LinkedIn usernames provided.", verbose=True, is_error=True, log_caller_file="connection.py")
        sys.exit(1)

    user_data_dir = get_browser_data_dir(args.profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=args.profile, headless=not args.no_headless)
            for msg in setup_messages:
                log(msg, args.verbose, status, log_caller_file="connection.py")
            status.update("[white]WebDriver setup complete.[/white]")

        for username in usernames:
            profile_url = f"https://www.linkedin.com/in/{username}/"
            log(f"Processing connection for: {profile_url}", args.verbose, log_caller_file="connection.py")
            success = send_connection_request(driver, profile_url, verbose=args.verbose, status=status)
            if success:
                log(f"Connection request sent successfully to {username}.", args.verbose, log_caller_file="connection.py")
            else:
                log(f"Failed to send connection request to {username}.", args.verbose, is_error=True, log_caller_file="connection.py")
            
            if username != usernames[-1]: # Don't wait after the last profile
                log(f"Waiting for 25 seconds before proceeding to the next profile...", args.verbose, log_caller_file="connection.py")
                time.sleep(25)

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="connection.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
