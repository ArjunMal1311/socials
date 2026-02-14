# socials instagram <profile> scout

import os
import sys
import json
import argparse

from datetime import datetime
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import get_instagram_profile_dir, ensure_dir_exists

from services.platform.instagram.support.scout_utils import scout_instagram_reels, process_reel_for_standalone

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Instagram Content Scout CLI Tool")
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="scout.py")
        sys.exit(1)

    # profile parameters
    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    instagram_props = platform_props.get('instagram', {})
    scout_props = instagram_props.get('scout', {})

    max_posts = scout_props.get('max_posts', 100)
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    videos_props = instagram_props.get('videos', {})
    restrict_filenames = videos_props.get('restrict_filenames', True)
    output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')

    replies_props = instagram_props.get('replies', {})
    max_comments = replies_props.get('max_comments', 50)

    log(f"Starting Instagram scout for profile '{profile}' - will download {max_posts} reels from the reels feed", verbose, log_caller_file="scout.py")

    driver = None
    all_reels_data = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(get_instagram_profile_dir(profile), f"scouted_reels_{timestamp}.json")

    try:
        driver, scouted_reels = scout_instagram_reels(profile_name=profile, count=max_posts, max_comments=max_comments, verbose=verbose, headless=headless, status=None)

        if scouted_reels:
            for reel in scouted_reels:
                processed_reel = process_reel_for_standalone(reel_data=reel, driver=driver, profile=profile, output_format=output_format, restrict_filenames=restrict_filenames, verbose=verbose)
                all_reels_data.append(processed_reel)

            ensure_dir_exists(os.path.dirname(output_filename))
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(all_reels_data, f, ensure_ascii=False, indent=4)
            log(f"Successfully saved {len(all_reels_data)} reels metadata to {output_filename}", verbose, log_caller_file="scout.py")
        else:
            log("No reels data to save.", verbose, is_error=False, log_caller_file="scout.py")

        log(f"Scouting complete. Processed {len(all_reels_data)} reels.", verbose, log_caller_file="scout.py")

    except Exception as e:
        log(f"An unexpected error occurred during scouting: {e}", verbose, is_error=True, log_caller_file="scout.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, log_caller_file="scout.py")


if __name__ == "__main__":
    main()
