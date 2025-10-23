import re
import os
import json
import time

from typing import Optional
from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from services.support.web_driver_handler import setup_driver
from selenium.webdriver.support import expected_conditions as EC
from services.platform.x.support.process_container import process_container
from services.support.path_config import get_browser_data_dir, get_community_output_file_path
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll

console = Console()

def _log(message: str, verbose: bool, is_error: bool = False):
    if verbose or is_error:
        log_message = message
        if is_error and not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red" if is_error else "white"
        console.print(f"[community_scraper_utils.py] {timestamp}|[{color}]{log_message}[/{color}]")

def fetch_tweets(driver, service=None, profile_name="Default", max_tweets=1000, community_name: Optional[str] = None, verbose: bool = False):
    all_tweets_data = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    _log("Navigating to X.com home page...", verbose)
    driver.get("https://x.com/home")
    time.sleep(5)

    if community_name:
        _log(f"Attempting to navigate to community: {community_name}...", verbose)
        try:
            community_tab_selector = f'a[role="tab"][href*="/home"] div[dir="ltr"] span.css-1jxf684.r-bcqeeo.r-1ttztb7.r-qvutc0.r-poiln3:text("{community_name}")'
            
            community_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[@role='tab']//span[contains(text(), '{community_name}')]"))
            )
            community_tab.click()
            _log(f"Successfully clicked on '{community_name}' community tab.", verbose)
            time.sleep(5)
        except Exception as e:
            _log(f"Could not find or click community tab '{community_name}': {e}. Proceeding with general home feed scraping.", verbose, is_error=False)
            driver.get("https://x.com/home")
            time.sleep(5)

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            raw_containers = []
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose
            )
            
            newly_processed_tweets = []
            for container in raw_containers:
                tweet_data = process_container(container, {'name': profile_name}, verbose=verbose)
                if tweet_data:
                    tweet_data['name'] = profile_name
                    newly_processed_tweets.append(tweet_data)

            all_tweets_data.extend(newly_processed_tweets)
            
            _log(f"Collected tweets: {len(all_tweets_data)} collected...", verbose)
            time.sleep(1)

            if len(all_tweets_data) >= max_tweets:
                _log(f"Reached target tweet count ({len(all_tweets_data)})!", verbose)
                break
            if no_new_content_count >= max_retries:
                _log("No new content after multiple attempts, stopping collection.", verbose, is_error=False)
                break

    except KeyboardInterrupt:
        _log(f"Collection stopped manually.", verbose)
    
    return all_tweets_data

def scrape_community_tweets(community_name: str, profile_name: str, browser_profile: Optional[str] = None, max_tweets: int = 1000, verbose: bool = False, headless: bool = True):
    driver = None
    all_tweets_data = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = get_community_output_file_path(profile_name, community_name, timestamp)

    try:
        user_data_dir = get_browser_data_dir(browser_profile or profile_name)
        driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile or profile_name, verbose=verbose, headless=headless)
        for msg in setup_messages:
            _log(msg, verbose)
        
        _log("Proceeding with browser profile. Assuming pre-existing login session.", verbose)

        _log("Starting tweet scraping...", verbose)
        for i in range(3, 0, -1):
            _log(f"{i} seconds left...", verbose)
            time.sleep(1)

        _log(f"Starting {community_name} tweet scraping (target: {max_tweets} tweets)...", verbose)
        
        all_tweets_data = fetch_tweets(driver, profile_name=profile_name, max_tweets=max_tweets, community_name=community_name, verbose=verbose)

        if all_tweets_data:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(all_tweets_data, f, ensure_ascii=False, indent=4)
            _log(f"Successfully saved {len(all_tweets_data)} tweets to {output_filename}", verbose)
        else:
            _log("No tweets to save.", verbose, is_error=False)

    except Exception as e:
        _log(f"An error occurred during {community_name} scraping: {e}", verbose, is_error=True)
    finally:
        if driver:
            driver.quit()
    return all_tweets_data
