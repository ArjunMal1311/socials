from datetime import datetime

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.x.support.home import run_home_mode

console = Console()

def scrape_and_store(profile_name: str, storage, verbose: bool = False):
    log(f"Starting scrape and store for profile: {profile_name}", verbose, log_caller_file="scraper.py")

    now = datetime.now()
    batch_id = now.strftime("%d%m%y%H%M")
    log(f"Generated batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

    try:
        if profile_name not in PROFILES:
            raise ValueError(f"Profile '{profile_name}' not found in PROFILES")

        profile_config = PROFILES[profile_name]
        custom_prompt = profile_config['prompts']['reply_generation']

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

        log(f"Scraped {len(scraped_tweets)} tweets", verbose, log_caller_file="scraper.py")

        if not scraped_tweets:
            raise Exception("No tweets were scraped")

        success = storage.push_content(scraped_tweets, batch_id, verbose)
        if not success:
            raise Exception("Failed to store tweets in database")

        log(f"Successfully stored {len(scraped_tweets)} tweets with batch ID: {batch_id}", verbose, log_caller_file="scraper.py")

        return batch_id, driver

    except Exception as e:
        log(f"Failed to scrape and store tweets: {e}", verbose, is_error=True, log_caller_file="scraper.py")
        raise
