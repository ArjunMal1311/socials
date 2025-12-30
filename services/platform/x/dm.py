# socials x <profile> dm send @username "message"
# socials x <profile> dm check @username
# socials x <profile> dm bulk "@user1,@user2" "Bulk Message"

# add --method api if want to use api (will only work if api is available)

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

    # mode
    parser.add_argument("mode", choices=["send", "check", "bulk"], help="DM mode: 'send' to send DM, 'check' to check DM availability, 'bulk' to send to multiple users")

    # target and message
    parser.add_argument("target", help="Target username(s) - single @username for send/check, comma-separated for bulk")
    parser.add_argument("message", nargs='?', help="Message to send (required for send/bulk modes)")

    # method override
    parser.add_argument("--method", type=str, choices=["api", "browser"], default="browser", help="Method to send DM: 'api' or 'browser'. Defaults to 'browser'.")
    
    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES.", verbose=False, is_error=True, log_caller_file="dm.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    verbose = profile_props.get('verbose', False)
    headless = profile_props.get('headless', True)

    if args.mode in ["send", "bulk"]:
        if not args.message:
            log("Message is required for send/bulk modes.", verbose, is_error=True, log_caller_file="dm.py")
            sys.exit(1)
    elif args.mode == "check":
        if args.message:
            log("Message not allowed for check mode.", verbose, is_error=True, log_caller_file="dm.py")
            sys.exit(1)

    if args.mode == "bulk":
        usernames = [username.strip() for username in args.target.split(',') if username.strip()]
        if len(usernames) < 2:
            log("Bulk mode requires at least 2 usernames separated by commas.", verbose, is_error=True, log_caller_file="dm.py")
            sys.exit(1)
    else:
        usernames = [args.target.strip()]
        if not usernames[0]:
            log("Username is required.", verbose, is_error=True, log_caller_file="dm.py")
            sys.exit(1)

    user_data_dir = get_browser_data_dir(profile)
    driver = None
    try:
        if args.method == "browser":
            with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
                driver, setup_messages = setup_driver(user_data_dir, profile=profile, headless=headless)
                for msg in setup_messages:
                    log(msg, verbose, status, log_caller_file="dm.py")
                status.update("[white]WebDriver setup complete.[/white]")

        if args.mode == "check":
            if args.method == "api":
                log("API method does not support check mode. Please use --method browser for checking DM button presence.", verbose, is_error=True, log_caller_file="dm.py")
                sys.exit(1)
            for username in usernames:
                log(f"Processing DM button check for: {username}", verbose, log_caller_file="dm.py")
                dm_button_found = check_dm_button(driver, username, verbose=verbose, status=status)
                if dm_button_found:
                    log(f"DM button is present for {username}.", verbose, log_caller_file="dm.py")
                else:
                    log(f"DM button is NOT present for {username}.", verbose, log_caller_file="dm.py")

        elif args.mode in ["send", "bulk"]:
            for username in usernames:
                if args.method == "browser":
                    log(f"Checking DM availability for {username}...", verbose, log_caller_file="dm.py")
                    dm_available = check_dm_button(driver, username, verbose=verbose, status=status)
                    if not dm_available:
                        log(f"DM not available for {username}. Skipping.", verbose, is_error=True, log_caller_file="dm.py")
                        continue

                if args.method == "api":
                    log(f"Attempting to send DM to {username} via API with message: '{args.message}'", verbose, log_caller_file="dm.py")
                    recipient_id = username
                    send_dm_success = send_dm_api(profile, recipient_id, args.message, verbose=verbose)
                    if send_dm_success:
                        log(f"Successfully sent DM to {username} via API.", verbose, log_caller_file="dm.py")
                    else:
                        log(f"Failed to send DM to {username} via API.", verbose, is_error=True, log_caller_file="dm.py")
                else:
                    log(f"Attempting to send DM to {username} via browser with message: '{args.message}'", verbose, log_caller_file="dm.py")
                    send_dm_success = send_dm(driver, username, args.message, verbose=verbose, status=status)
                    if send_dm_success:
                        log(f"Successfully sent DM to {username}.", verbose, log_caller_file="dm.py")
                    else:
                        log(f"Failed to send DM to {username}.", verbose, is_error=True, log_caller_file="dm.py")

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="dm.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
