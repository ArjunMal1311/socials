from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.x.support.home import run_home_mode

console = Console()

def scrape_and_store(profile_names: list, storages: dict, verbose: bool = False):
    log(f"Starting scrape and store for profiles: {', '.join(profile_names)}", verbose, log_caller_file="scraper.py")

    now = datetime.now()
    batch_id = now.strftime("%d%m%y%H%M")
    log(f"Generated unified batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

    all_scraped_content = []
    drivers = {}

    try:
        for profile_name in profile_names:
            if profile_name not in PROFILES:
                raise ValueError(f"Profile '{profile_name}' not found in PROFILES")

        for profile_name in profile_names:
            log(f"Processing profile: {profile_name}", verbose, log_caller_file="scraper.py")

            profile_config = PROFILES[profile_name]
            custom_prompt = profile_config['prompts']['reply_generation']
            storage = storages[profile_name]  # Get storage for this profile

            profile_props = profile_config.get('properties', {})
            max_tweets_action = profile_props.get('max_tweets_action', 17)
            ignore_video_tweets = profile_props.get('ignore_video_tweets', False)
            headless = profile_props.get('headless', True)

            log(f"Scraping {max_tweets_action} tweets for profile {profile_name}", verbose, log_caller_file="scraper.py")

            with Status(f'[white]Scraping tweets for {profile_name}...[/white]', spinner="dots", console=console) as status:
                result = run_home_mode(
                    profile_name=profile_name,
                    custom_prompt=custom_prompt,
                    max_tweets=max_tweets_action,
                    status=status,
                    ignore_video_tweets=ignore_video_tweets,
                    verbose=verbose,
                    headless=headless
                )

            if isinstance(result, tuple):
                driver, scraped_tweets = result
            else:
                driver = result
                scraped_tweets = []

            drivers[profile_name] = driver

            log(f"Scraped {len(scraped_tweets)} tweets for profile {profile_name}", verbose, log_caller_file="scraper.py")

            if scraped_tweets:
                # Store content for this profile with unified batch_id
                success = storage.push_content(scraped_tweets, batch_id, verbose)
                if not success:
                    log(f"Failed to store tweets for profile {profile_name}", verbose, is_error=True, log_caller_file="scraper.py")
                    continue

                log(f"Successfully stored {len(scraped_tweets)} tweets for profile {profile_name} with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")
            else:
                log(f"No tweets scraped for profile {profile_name}", verbose, log_caller_file="scraper.py")

        log(f"Completed scraping for {len(profile_names)} profiles with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

        return batch_id, drivers

    except Exception as e:
        log(f"Failed to scrape and store tweets: {e}", verbose, is_error=True, log_caller_file="scraper.py")
        raise
