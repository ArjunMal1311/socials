# socials x <profile> dm @username "message"
# socials x <profile> dm @username1, @username2 "Bulk Message"

# socials x <profile> dm queue add @username "message" --at "2025-01-15 10:00"
# socials x <profile> dm queue list
# socials x <profile> dm queue start

# add api if want to use api (will only work if api is available)

import sys
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.console import Console
from rich.status import Status
from services.support.logger_util import _log as log
from services.platform.x.support.home import setup_driver
from services.support.path_config import get_browser_data_dir, initialize_directories
from services.platform.x.support.x_dm_utils import check_dm_button, send_dm, send_dm_api

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="X DM CLI Tool")
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")

    # usernames 
    parser.add_argument("--x-usernames", type=str, required=True, help="Comma-separated list of X usernames.")

    # check if dm available
    parser.add_argument("--check", action="store_true", help="Check if the DM button is present on the profile.")
    parser.add_argument("--message", type=str, help="The message to send to the X user(s).")
    parser.add_argument("--method", type=str, choices=["api", "browser"], default="browser", help="Method to send DM: 'api' or 'browser'. Defaults to 'browser'.")
    
    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation.")
    
    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    usernames = [username.strip() for username in args.x_usernames.split(',') if username.strip()]
    if not usernames:
        log("No X usernames provided.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    if args.check and args.message:
        log("Cannot use --check and --message simultaneously. Please choose one.", verbose=True, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    user_data_dir = get_browser_data_dir(args.profile)
    driver = None
    try:
        if args.method == "browser":
            with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
                driver, setup_messages = setup_driver(user_data_dir, profile=args.profile, headless=not args.no_headless)
                for msg in setup_messages:
                    log(msg, args.verbose, status, log_caller_file="dm.py")
                status.update("[white]WebDriver setup complete.[/white]")

        if args.check:
            if args.method == "api":
                log("API method does not support --check. Please use --method browser for checking DM button presence.", verbose=True, is_error=True, log_caller_file="dm.py")
                sys.exit(1)
            for username in usernames:
                log(f"Processing DM button check for: {username}", args.verbose, log_caller_file="dm.py")
                dm_button_found = check_dm_button(driver, username, verbose=args.verbose, status=status)
                if dm_button_found:
                    log(f"DM button is present for {username}.", args.verbose, log_caller_file="dm.py")
                else:
                    log(f"DM button is NOT present for {username}.", args.verbose, log_caller_file="dm.py")
        elif args.message:
            for username in usernames:
                if args.method == "api":
                    log(f"Attempting to send DM to {username} via API with message: '{args.message}'", args.verbose, log_caller_file="dm.py")
                    recipient_id = username
                    send_dm_success = send_dm_api(args.profile, recipient_id, args.message, verbose=args.verbose)
                    if send_dm_success:
                        log(f"Successfully sent DM to {username} via API.", args.verbose, log_caller_file="dm.py")
                    else:
                        log(f"Failed to send DM to {username} via API.", args.verbose, is_error=True, log_caller_file="dm.py")
                else:
                    log(f"Attempting to send DM to {username} via browser with message: '{args.message}'", args.verbose, log_caller_file="dm.py")
                    send_dm_success = send_dm(driver, username, args.message, verbose=args.verbose, status=status)
                    if send_dm_success:
                        log(f"Successfully sent DM to {username}.", args.verbose, log_caller_file="dm.py")
                    else:
                        log(f"Failed to send DM to {username}.", args.verbose, is_error=True, log_caller_file="dm.py")
        else:
            log("No action specified. Use --check to check for DM button or --message to send a DM.", args.verbose, is_error=True, log_caller_file="dm.py")

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="dm.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
