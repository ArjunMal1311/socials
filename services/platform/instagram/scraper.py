# socials instagram <profile> scraper

import os
import sys
import time
import json
import argparse

from datetime import datetime
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver

from services.platform.instagram.support.video_utils import download_instagram_reel
from services.platform.instagram.support.scraper_utils import extract_current_reel_url, move_to_next_reel, scrape_instagram_reels_comments, _format_reel_data

from services.support.path_config import get_browser_data_dir, get_instagram_profile_dir, ensure_dir_exists

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

    try:
        user_data_dir = get_browser_data_dir(browser_profile)

        with Status(f"[white]Initializing WebDriver for profile '{browser_profile}'...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile, headless=headless)
            for msg in setup_messages:
                status.update(f"[white]{msg}[/white]")
                time.sleep(0.1)
            status.update("[white]WebDriver initialized.[/white]")
        status.stop()

        if not driver:
            log("WebDriver could not be initialized. Aborting.", verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status("[white]Navigating to Instagram Reels...[/white]", spinner="dots", console=console) as status:
            driver.get("https://www.instagram.com/reels/")
            time.sleep(5)
        status.stop()

        downloaded_reels = 0
        reel_number = 0

        while downloaded_reels < max_posts:
            reel_number += 1
            log(f"--- Processing Reel {reel_number} ---", verbose, log_caller_file="scraper.py")

            reel_url = extract_current_reel_url(driver)
            if not reel_url:
                log(f"Could not extract reel URL for reel {reel_number}, waiting and retrying...", verbose, log_caller_file="scraper.py")
                time.sleep(3)
                reel_url = extract_current_reel_url(driver)
                if not reel_url:
                    log(f"Still could not extract reel URL for reel {reel_number}, skipping", verbose, log_caller_file="scraper.py")
                    if not move_to_next_reel(driver, verbose=verbose):
                        log("Could not move to next reel. Ending scraping process.", verbose, log_caller_file="scraper.py")
                        break
                    continue

            log(f"Found reel URL: {reel_url}", verbose, log_caller_file="scraper.py")

            with Status(f"[white]Scraping comments from reel {reel_number}...[/white]", spinner="dots", console=console) as status:
                comments_data, _ = scrape_instagram_reels_comments(
                    driver=driver,
                    max_comments=max_comments,
                    status=status,
                    html_dump_path=None,
                    verbose=verbose,
                    reel_index=reel_number - 1
                )
            status.stop()

            if comments_data:
                log(f"Scraped {len(comments_data)} comments from reel {reel_number}", verbose, log_caller_file="scraper.py")
            else:
                log(f"No comments found for reel {reel_number}", verbose, log_caller_file="scraper.py")
                comments_data = []

            with Status(f"[white]Downloading reel {reel_number} ({reel_url})...[/white]", spinner="dots", console=console) as status:
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
                downloaded_reels += 1
                log(f"Successfully downloaded reel {reel_number}: {os.path.basename(downloaded_path)}", verbose, log_caller_file="scraper.py")
                log(f"Progress: {downloaded_reels}/{max_posts} reels downloaded", verbose, log_caller_file="scraper.py")

                reel_data = _format_reel_data(reel_url, downloaded_path, cdn_link, comments_data, profile)
                all_reels_data.append(reel_data)
            else:
                log(f"Failed to download reel {reel_number} ({reel_url})", verbose, log_caller_file="scraper.py")

            if not move_to_next_reel(driver, verbose=verbose):
                log("Could not move to next reel. Ending scraping process.", verbose, log_caller_file="scraper.py")
                break

            if downloaded_reels >= max_posts:
                log(f"Reached maximum reels limit ({max_posts}). Stopping scraping.", verbose, log_caller_file="scraper.py")
                break

        if all_reels_data:
            ensure_dir_exists(os.path.dirname(output_filename))
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(all_reels_data, f, ensure_ascii=False, indent=4)
            log(f"Successfully saved {len(all_reels_data)} reels metadata to {output_filename}", verbose, log_caller_file="scraper.py")
        else:
            log("No reels data to save.", verbose, is_error=False, log_caller_file="scraper.py")

        log(f"Scraping complete. Downloaded {downloaded_reels} reels.", verbose, log_caller_file="scraper.py")

    except Exception as e:
        log(f"An unexpected error occurred during scraping: {e}", verbose, is_error=True, log_caller_file="scraper.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, log_caller_file="scraper.py")


if __name__ == "__main__":
    main()
