import time

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import get_browser_data_dir
from services.support.storage.storage_factory import get_storage

from services.platform.x.support.reply_home import run_home_mode
from services.platform.linkedin.support.reply_utils import run_linkedin_reply_mode
from services.platform.instagram.support.replies_utils import (generate_instagram_replies, run_instagram_reply_mode)

console = Console()

def scrape_single_platform(profile_name: str, platform: str, profile_config: dict, batch_id: str, verbose: bool = False):
    log(f"Scraping {platform} content for profile {profile_name}", verbose, log_caller_file="scraper.py")

    try:
        driver, scraped_content = scrape_platform_content(
            profile_name, platform, profile_config, batch_id, verbose
        )
        return driver, scraped_content

    except Exception as e:
        log(f"Failed to scrape {platform} for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="scraper.py")
        return None, []

def scrape_platform_content(profile_name: str, platform: str, profile_config: dict, batch_id: str, verbose: bool = False):
    platform = platform.lower().strip()

    try:
        if platform in ['x', 'twitter']:
            custom_prompt = profile_config['prompts']['reply_generation']

            profile_props = profile_config.get('properties', {})
            utils_props = profile_props.get('utils', {})
            action_props = utils_props.get('action', {})
            global_props = profile_props.get('global', {})
            platform_props = profile_props.get('platform', {})
            x_props = platform_props.get('x', {})
            reply_props = x_props.get('reply', {})

            max_tweets_action = action_props.get('count', 17)
            ignore_video_tweets = reply_props.get('ignore_video_tweets', False)
            headless = global_props.get('headless', True)

            browser_data_dir = get_browser_data_dir(profile_name, "x")

            with Status(f'[white]Scraping {platform} content for {profile_name}...[/white]', spinner="dots", console=console) as status:
                result = run_home_mode(
                    profile_name=profile_name,
                    custom_prompt=custom_prompt,
                    max_tweets=max_tweets_action,
                    status=status,
                    ignore_video_tweets=ignore_video_tweets,
                    verbose=verbose,
                    headless=headless,
                    browser_data_dir=browser_data_dir
                )

            if isinstance(result, tuple):
                driver, scraped_content = result
            else:
                driver = result
                scraped_content = []

            return driver, scraped_content


        elif platform == 'linkedin':
            profile_props = profile_config.get('properties', {})
            global_props = profile_props.get('global', {})
            platform_props = profile_props.get('platform', {})
            linkedin_props = platform_props.get('linkedin', {})
            scraper_props = linkedin_props.get('scraper', {})

            count = scraper_props.get('count', 10)
            headless = global_props.get('headless', True)

            browser_data_dir = get_browser_data_dir(profile_name, "linkedin")

            with Status(f'[white]Scraping {platform} content for {profile_name}...[/white]', spinner="dots", console=console) as status:
                driver, scraped_content = run_linkedin_reply_mode(
                    profile_name=profile_name,
                    browser_profile_name=profile_name,
                    max_posts=count,
                    verbose=verbose,
                    status=status,
                    headless=headless,
                    browser_data_dir=browser_data_dir
                )

            return driver, scraped_content

        elif platform == 'instagram':
            profile_props = profile_config.get('properties', {})
            global_props = profile_props.get('global', {})
            platform_props = profile_props.get('platform', {})
            instagram_props = platform_props.get('instagram', {})
            replies_props = instagram_props.get('replies', {})
            utils_props = profile_props.get('utils', {})
            action_props = utils_props.get('action', {})

            count = action_props.get('count', 5)
            max_comments = replies_props.get('comments', 50)
            videos_props = instagram_props.get('videos', {})
            output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')
            restrict_filenames = videos_props.get('restrict_filenames', True)
            headless = global_props.get('headless', True)

            browser_data_dir = get_browser_data_dir(profile_name, "instagram")

            with Status(f'[white]Scraping {platform} content for {profile_name}...[/white]', spinner="dots", console=console) as status:
                driver, scraped_content = run_instagram_reply_mode(
                    profile_name=profile_name,
                    count=count,
                    max_comments=max_comments,
                    output_format=output_format,
                    restrict_filenames=restrict_filenames,
                    verbose=verbose,
                    headless=headless,
                    status=status
                )

            return driver, scraped_content

        else:
            log(f"Unsupported platform for scraping: {platform}", verbose, is_error=True, log_caller_file="scraper.py")
            return None, []

    except Exception as e:
        log(f"Error scraping {platform} for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="scraper.py")
        return None, []

def scrape_and_store(profile_platform_map: dict, storages: dict, verbose: bool = False):
    all_profiles = set()
    for profiles in profile_platform_map.values():
        all_profiles.update(profiles)
    all_platforms = list(profile_platform_map.keys())

    log(f"Starting scrape and store for {len(all_profiles)} profiles across {len(all_platforms)} platforms", verbose, log_caller_file="scraper.py")

    now = datetime.now()
    batch_id = now.strftime("%d%m%y%H%M")
    log(f"Generated unified batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

    drivers = {profile_name: {} for profile_name in all_profiles}

    try:
        for profile_name in all_profiles:
            if profile_name not in PROFILES:
                raise ValueError(f"Profile '{profile_name}' not found in PROFILES")

        with ThreadPoolExecutor(max_workers=len(all_profiles) * len(all_platforms)) as executor:
            futures = {}

            for platform, profiles in profile_platform_map.items():
                for profile_name in profiles:
                    log(f"Processing profile: {profile_name} on platform: {platform}", verbose, log_caller_file="scraper.py")
                    profile_config = PROFILES[profile_name]
                    if profile_name not in drivers:
                        drivers[profile_name] = {}

                    future = executor.submit(scrape_single_platform, profile_name, platform, profile_config, batch_id, verbose)
                    futures[future] = (profile_name, platform)

            for future in as_completed(futures):
                profile_name, platform = futures[future]
                try:
                    driver, scraped_content = future.result()

                    if driver:
                        drivers[profile_name][platform] = driver

                    if scraped_content:
                        storage = storages[profile_name][platform]

                        if scraped_content and verbose:
                            sample_data = scraped_content[0] if scraped_content else {}
                            log(f"Sample {platform} data being stored: {str(sample_data)[:500]}...", verbose, log_caller_file="scraper.py")

                        success = storage.push_content(scraped_content, batch_id, verbose)
                        if not success:
                            log(f"Failed to store {platform} content for profile {profile_name}", verbose, is_error=True, log_caller_file="scraper.py")
                            continue

                        log(f"Successfully stored {len(scraped_content)} {platform} items for profile {profile_name} with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")
                    else:
                        log(f"No {platform} content scraped for profile {profile_name}", verbose, log_caller_file="scraper.py")

                except Exception as e:
                    log(f"Failed to scrape {platform} for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="scraper.py")
                    continue

        log(f"Completed scraping for {len(all_profiles)} profiles across {len(all_platforms)} platforms with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

        return batch_id, drivers

    except Exception as e:
        log(f"Failed to scrape and store tweets: {e}", verbose, is_error=True, log_caller_file="scraper.py")
        raise

