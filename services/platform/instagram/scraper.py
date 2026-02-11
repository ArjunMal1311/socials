# socials instagram <profile> scraper

import os
import sys
import json
import argparse

from datetime import datetime
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import get_instagram_profile_dir, ensure_dir_exists

from services.platform.instagram.support.video_utils import download_instagram_reel
from services.platform.instagram.support.scraper_utils import scrape_instagram_reels, _format_reel_data

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Instagram Content Scraper CLI Tool")
    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    instagram_props = platform_props.get('instagram', {})
    scraper_props = instagram_props.get('scraper', {})

    browser_profile = global_props.get('browser_profile', profile)
    max_posts = scraper_props.get('max_posts', 100)
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    videos_props = instagram_props.get('videos', {})
    restrict_filenames = videos_props.get('restrict_filenames', True)
    output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')

    replies_props = instagram_props.get('replies', {})
    max_comments = replies_props.get('max_comments', 50)

    log(f"Starting Instagram scraper for profile '{profile}' - will download {max_posts} reels from the reels feed", verbose, log_caller_file="scraper.py")

    driver = None
    all_reels_data = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = os.path.join(get_instagram_profile_dir(profile), f"scraped_reels_{timestamp}.json")

    def process_reel_for_standalone(reel_data: dict, driver) -> dict:
        reel_url = reel_data['reel_url']
        comments_data = reel_data['comments_data']
        
        with Status(f"[white]Downloading reel ({reel_url})...[/white]", spinner="dots", console=console) as status:
            downloaded_path, cdn_link = download_instagram_reel(
                reel_url=reel_url,
                profile_name=profile,
                output_format=output_format,
                restrict_filenames=restrict_filenames,
                status=status,
                verbose=verbose
            )
        status.stop()

        if downloaded_path:
            log(f"Successfully downloaded: {os.path.basename(downloaded_path)}", verbose, log_caller_file="scraper.py")
            return _format_reel_data(reel_url, downloaded_path, cdn_link, comments_data, profile)
        else:
            log(f"Failed to download reel ({reel_url})", verbose, log_caller_file="scraper.py")
            return reel_data

    try:
        driver, all_reels_data = scrape_instagram_reels(
            profile_name=profile,
            count=max_posts,
            max_comments=max_comments,
            verbose=verbose,
            headless=headless,
            status=None,
            process_item_callback=process_reel_for_standalone
        )

        if all_reels_data:
            ensure_dir_exists(os.path.dirname(output_filename))
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(all_reels_data, f, ensure_ascii=False, indent=4)
            log(f"Successfully saved {len(all_reels_data)} reels metadata to {output_filename}", verbose, log_caller_file="scraper.py")
        else:
            log("No reels data to save.", verbose, is_error=False, log_caller_file="scraper.py")

        log(f"Scraping complete. Processed {len(all_reels_data)} reels.", verbose, log_caller_file="scraper.py")

    except Exception as e:
        log(f"An unexpected error occurred during scraping: {e}", verbose, is_error=True, log_caller_file="scraper.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, log_caller_file="scraper.py")


if __name__ == "__main__":
    main()
