# socials x <profile> global init
# socials x <profile> global delete
# socials x <profile> global login
# socials x <profile> global check-credentials

import sys
import argparse

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories

from services.platform.x.support.post_approved_tweets import check_profile_credentials
from services.platform.x.support.global_support import delete_profile, init_profile, login_profile

def main():
    initialize_directories()

    parser = argparse.ArgumentParser(description="X Global Commands")
    parser.add_argument("command", choices=["init", "delete", "login", "check-credentials"], help="Global command to execute")
    parser.add_argument("--profile", type=str, help="Profile name (required for init, delete)")

    args = parser.parse_args()

    if args.command in ["init", "delete", "login", "check-credentials"] and not args.profile:
        log(f"Profile is required for '{args.command}' command. Use --profile PROFILE", verbose=True, is_error=True, log_caller_file="global.py")
        sys.exit(1)

    if args.command == "init":
        if not init_profile(args.profile):
            sys.exit(1)
    elif args.command == "delete":
        if not delete_profile(args.profile):
            sys.exit(1)
    elif args.command == "login":
        if not login_profile(args.profile):
            sys.exit(1)
    elif args.command == "check-credentials":
        result = check_profile_credentials(args.profile)
        if result["ok"]:
            log(f"All X API credentials found for profile '{args.profile}'", verbose=True, log_caller_file="global.py")
        else:
            log(f"Missing X API credentials for profile '{args.profile}':", verbose=True, is_error=True, log_caller_file="global.py")
            for var_name, var_info in result["vars"].items():
                last4 = f" (ends with: {var_info['last4']})" if var_info["present"] else ""
                log(f"{var_name}{last4}", verbose=True, is_error=not var_info["present"], log_caller_file="global.py")
        if not result["ok"]:
            sys.exit(1)

if __name__ == "__main__":
    main()