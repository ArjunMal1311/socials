import sys
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.path_config import get_browser_data_dir, initialize_directories

from services.platform.x.support.home import setup_driver
from services.platform.x.support.x_follow_utils import check_follow_status, follow_user, unfollow_user

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="X Follow CLI Tool")
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")
    parser.add_argument("mode", choices=["follow", "unfollow", "check", "bulk"], help="Follow mode: 'follow' to follow user, 'unfollow' to unfollow user, 'check' to check follow status, 'bulk' to follow multiple users")
    parser.add_argument("target", help="Target username(s) - single @username for follow/unfollow/check, comma-separated for bulk")

    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without actually following/unfollowing.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES.", verbose=False, is_error=True, log_caller_file="follow.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    if args.mode == "bulk":
        usernames = [username.strip().lstrip('@') for username in args.target.split(',') if username.strip()]
        if len(usernames) < 2:
            log("Bulk mode requires at least 2 usernames separated by commas.", verbose, is_error=True, log_caller_file="follow.py")
            sys.exit(1)
    else:
        usernames = [args.target.strip().lstrip('@')]
        if not usernames[0]:
            log("Username is required.", verbose, is_error=True, log_caller_file="follow.py")
            sys.exit(1)

    user_data_dir = get_browser_data_dir(profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile, headless=headless)
            for msg in setup_messages:
                log(msg, verbose, status, log_caller_file="follow.py")
            status.update("[white]WebDriver setup complete.[/white]")

        if args.mode == "check":
            for username in usernames:
                log(f"Checking follow status for: {username}", verbose, log_caller_file="follow.py")
                status_result = check_follow_status(driver, username, verbose=verbose, status=status)
                if status_result == "following":
                    log(f"You are following {username}.", verbose, log_caller_file="follow.py")
                elif status_result == "not_following":
                    log(f"You are not following {username}.", verbose, log_caller_file="follow.py")
                else:
                    log(f"Unable to determine follow status for {username}.", verbose, is_error=True, log_caller_file="follow.py")

        elif args.mode in ["follow", "bulk"]:
            for username in usernames:
                if not args.dry_run:
                    log(f"Attempting to follow {username}...", verbose, log_caller_file="follow.py")
                    success, result = follow_user(driver, username, verbose=verbose, status=status)
                    if success:
                        log(f"Successfully followed {username}.", verbose, log_caller_file="follow.py")
                    elif result == "already_following":
                        log(f"Already following {username}.", verbose, log_caller_file="follow.py")
                    else:
                        log(f"Failed to follow {username}: {result}", verbose, is_error=True, log_caller_file="follow.py")
                else:
                    log(f"Dry run: Skipping follow for {username}.", verbose, log_caller_file="follow.py")

        elif args.mode == "unfollow":
            for username in usernames:
                if not args.dry_run:
                    log(f"Attempting to unfollow {username}...", verbose, log_caller_file="follow.py")
                    success, result = unfollow_user(driver, username, verbose=verbose, status=status)
                    if success:
                        log(f"Successfully unfollowed {username}.", verbose, log_caller_file="follow.py")
                    else:
                        log(f"Failed to unfollow {username}: {result}", verbose, is_error=True, log_caller_file="follow.py")
                else:
                    log(f"Dry run: Skipping unfollow for {username}.", verbose, log_caller_file="follow.py")

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="follow.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
