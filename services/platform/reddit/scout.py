# socials reddit <profile> scout subreddits

import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.reddit.support.scout_utils import run_reddit_scout

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Reddit Scout CLI Tool")

    parser.add_argument("profile", type=str, help="Profile name to use from profiles.py")
    parser.add_argument("mode", choices=["subreddits"], help="Scout mode: 'subreddits' for scouting configured subreddits")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True)
        sys.exit(1)

    # profile parameters
    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)

    if args.mode == "subreddits":
        with Status(f"[white]Running Reddit Scout for profile '{args.profile}' ...[/white]", spinner="dots", console=console) as status:
            scout_data = run_reddit_scout(args.profile, status=status, verbose=verbose)
            if scout_data:
                log(f"Successfully scouted {len(scout_data)} Reddit posts.", verbose, status=status)
            else:
                log("No Reddit data scouted.", verbose, is_error=True, status=status)

if __name__ == "__main__":
    main()
