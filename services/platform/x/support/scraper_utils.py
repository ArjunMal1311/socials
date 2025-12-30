import os
import json
import time

from typing import Optional
from rich.console import Console
from datetime import datetime, timezone

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_scrape_output_file_path
from services.support.path_config import get_browser_data_dir, ensure_dir_exists

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.platform.x.support.process_container import process_container
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll

console = Console()

def _format_tweet_data(raw_tweet_data: dict) -> dict:
    scraped_at_str = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    likes = int(raw_tweet_data.get('likes', 0) * 1000) if isinstance(raw_tweet_data.get('likes'), float) and raw_tweet_data.get('likes') < 100 else int(raw_tweet_data.get('likes', 0))

    tweet_date_str = raw_tweet_data.get('tweet_date', '')
    try:
        tweet_date_iso = datetime.strptime(tweet_date_str, '%Y-%m-%d %H:%M:%S').isoformat() + 'Z'
    except ValueError:
        tweet_date_iso = tweet_date_str if tweet_date_str else datetime.now(timezone.utc).isoformat()

    return {
        "source": "x",
        "scraped_at": scraped_at_str,
        "engagement": {
            "likes": likes,
            "retweets": int(raw_tweet_data.get('retweets', 0)),
            "replies": int(raw_tweet_data.get('replies', 0)),
            "bookmarks": int(raw_tweet_data.get('bookmarks', 0)),
            "views": int(raw_tweet_data.get('views', 0)),
        },
        "data": {
            "tweet_id": raw_tweet_data.get('tweet_id', ''),
            "text": raw_tweet_data.get('tweet_text', ''),
            "tweet_url": raw_tweet_data.get('tweet_url', ''),
            "media_urls": raw_tweet_data.get('media_urls', ''),
            "tweet_date": tweet_date_iso,
            "profile_image_url": raw_tweet_data.get('profile_image_url', ''),
        }
    }

def fetch_tweets(driver, service=None, profile_name="Default", max_tweets=1000, community_name: Optional[str] = None, verbose: bool = False, status=None, specific_search_url: Optional[str] = None):
    all_tweets_data = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    if specific_search_url:
        log(f"Navigating to specific URL: {specific_search_url}", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get(specific_search_url)
    else:
        log("Navigating to X.com home page...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get("https://x.com/home")
    time.sleep(5)

    if community_name:
        log(f"Attempting to navigate to community: {community_name}...", verbose, status=status, log_caller_file="scraper_utils.py")
        try:
            community_tab = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[@role='tab']//span[contains(text(), '{community_name}')]"))
            )
            community_tab.click()
            log(f"Successfully clicked on '{community_name}' community tab.", verbose, status=status, log_caller_file="scraper_utils.py")
            time.sleep(5)
        except Exception as e:
            log(f"Community tab not found, trying search approach: {e}", verbose, status=status, log_caller_file="scraper_utils.py")
            try:
                search_box = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@data-testid='SearchBox_Search_Input']"))
                )
                search_box.clear()
                search_box.send_keys(community_name)
                time.sleep(1)

                from selenium.webdriver.common.keys import Keys
                search_box.send_keys(Keys.RETURN)
                time.sleep(3)

                community_links = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/i/communities/') or contains(@href, '/communities/')]"))
                )

                if community_links:
                    community_links[0].click()
                    log(f"Successfully navigated to community via search: {community_name}", verbose, status=status, log_caller_file="scraper_utils.py")
                    time.sleep(5)
                else:
                    raise Exception("No community links found in search results")

            except Exception as search_e:
                log(f"Could not navigate to community '{community_name}' via search either: {search_e}. Proceeding with general home feed scraping.", verbose, is_error=False, status=status, log_caller_file="scraper_utils.py")
                driver.get("https://x.com/home")
                time.sleep(5)

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            raw_containers = []
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose, status
            )

            newly_processed_tweets = []
            for container in raw_containers:
                tweet_data = process_container(container, verbose=verbose)
                if tweet_data:
                    tweet_data['name'] = profile_name
                    newly_processed_tweets.append(tweet_data)

            all_tweets_data.extend(newly_processed_tweets)
            
            log(f"Collected tweets: {len(all_tweets_data)} collected...", verbose, status=status, log_caller_file="scraper_utils.py")
            time.sleep(1)

            if len(all_tweets_data) >= max_tweets:
                log(f"Reached target tweet count ({len(all_tweets_data)})!", verbose, status=status, log_caller_file="scraper_utils.py")
                break
            if no_new_content_count >= max_retries:
                log("No new content after multiple attempts, stopping collection.", verbose, is_error=False, status=status, log_caller_file="scraper_utils.py")
                break

    except KeyboardInterrupt:
        log(f"Collection stopped manually.", verbose, status=status, log_caller_file="scraper_utils.py")
    
    return all_tweets_data

def scrape_tweets(scrape_type: str, target_name: str, profile_name: str, browser_profile: Optional[str] = None, max_tweets: int = 1000, verbose: bool = False, headless: bool = True, status=None, specific_search_url: Optional[str] = None):
    driver = None
    all_tweets_data = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = get_scrape_output_file_path(profile_name, scrape_type, target_name, timestamp)

    try:
        user_data_dir = get_browser_data_dir(browser_profile or profile_name)
        driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile or profile_name, verbose=verbose, headless=headless, status=status)
        for msg in setup_messages:
            log(msg, verbose, status=status, log_caller_file="scraper_utils.py")
        
        log("Proceeding with browser profile. Assuming pre-existing login session.", verbose, status=status, log_caller_file="scraper_utils.py")

        log("Starting tweet scraping...", verbose, status=status, log_caller_file="scraper_utils.py")
        for i in range(3, 0, -1):
            log(f"{i} seconds left...", verbose, status=status, log_caller_file="scraper_utils.py")
            time.sleep(1)

        target_desc = f"community '{target_name}'" if scrape_type == "community" else "home feed"
        log(f"Starting {target_desc} tweet scraping (target: {max_tweets} tweets)...", verbose, status=status, log_caller_file="scraper_utils.py")
        
        community_name_for_fetch = target_name if scrape_type == "community" else None
        all_tweets_data = fetch_tweets(driver, profile_name=profile_name, max_tweets=max_tweets, community_name=community_name_for_fetch, verbose=verbose, status=status, specific_search_url=specific_search_url)

        if all_tweets_data:
            formatted_for_saving = [_format_tweet_data(tweet) for tweet in all_tweets_data]
            ensure_dir_exists(os.path.dirname(output_filename))
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(formatted_for_saving, f, ensure_ascii=False, indent=4)
            log(f"Successfully saved {len(formatted_for_saving)} tweets to {output_filename}", verbose, status=status, log_caller_file="scraper_utils.py")
        else:
            log("No tweets to save.", verbose, is_error=False, status=status, log_caller_file="scraper_utils.py")

    except Exception as e:
        target_desc = f"community '{target_name}'" if scrape_type == "community" else "home feed"
        log(f"An error occurred during {target_desc} scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
    finally:
        if driver:
            driver.quit()
    return all_tweets_data
