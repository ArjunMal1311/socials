# socials <profile> global init
# socials <profile> global delete
# socials <profile> global <platform> login
# socials <profile> global <platform> check-credentials

import sys
import argparse

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories

from services.support.global_support import check_profile_credentials, delete_profile, init_profile, login_profile

def main():
    initialize_directories()

    parser = argparse.ArgumentParser(description="Global Profile and Platform Commands")
    parser.add_argument("profile", type=str, help="Profile name")
    parser.add_argument("command", type=str, help="Command: init, delete, or platform name")
    parser.add_argument("action", nargs='?', type=str, choices=["login", "check-credentials"], help="Platform-specific action")

    args = parser.parse_args()

    if args.command in ["init", "delete"]:
        if args.command == "init":
            if not init_profile(args.profile):
                sys.exit(1)
        elif args.command == "delete":
            if not delete_profile(args.profile):
                sys.exit(1)

    elif args.action:
        platform = args.command
        if args.action == "login":
            if not login_profile(args.profile, platform):
                sys.exit(1)
        elif args.action == "check-credentials":
            result = check_profile_credentials(args.profile, platform)
            if result["ok"]:
                log(f"All {platform.upper()} API credentials found for profile '{args.profile}'", verbose=True, log_caller_file="global.py")
            else:
                log(f"Missing {platform.upper()} API credentials for profile '{args.profile}':", verbose=True, is_error=True, log_caller_file="global.py")
                for var_name, var_info in result["vars"].items():
                    last4 = f" (ends with: {var_info['last4']})" if var_info["present"] else ""
                    log(f"{var_name}{last4}", verbose=True, is_error=not var_info["present"], log_caller_file="global.py")
            if not result["ok"]:
                sys.exit(1)
    else:
        log("Invalid command format. Use:", verbose=True, is_error=True, log_caller_file="global.py")
        log("  socials <profile> global init", verbose=True, is_error=True, log_caller_file="global.py")
        log("  socials <profile> global delete", verbose=True, is_error=True, log_caller_file="global.py")
        log("  socials <profile> global <platform> login", verbose=True, is_error=True, log_caller_file="global.py")
        log("  socials <profile> global <platform> check-credentials", verbose=True, is_error=True, log_caller_file="global.py")
        sys.exit(1)

if __name__ == "__main__":
    main()