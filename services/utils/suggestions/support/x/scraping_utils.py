import os
import json
import time
import sys

from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Any

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_suggestions_dir

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.platform.x.support.process_container import process_container
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll

console = Console()

def scrape_current_page(driver, max_tweets: int, verbose: bool = False, status=None) -> List[Dict[str, Any]]:
    tweets_data = []

    try:
        log("Starting to capture tweet containers...", verbose, status=status, log_caller_file="scraping_utils.py")

        raw_containers = []
        processed_tweet_ids = set()
        no_new_content_count = 0
        scroll_count = 0
        max_scrolls = 20

        while len(tweets_data) < max_tweets and scroll_count < max_scrolls and no_new_content_count < 3:
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose, status
            )

            if new_tweets_in_pass > 0:
                log(f"Pass completed. New tweets found: {new_tweets_in_pass}", verbose, status=status, log_caller_file="scraping_utils.py")

                for container in raw_containers[-new_tweets_in_pass:]:
                    try:
                        tweet_data = process_container(container, verbose)
                        if tweet_data and tweet_data.get('tweet_id'):
                            tweets_data.append(tweet_data)

                            if len(tweets_data) >= max_tweets:
                                break

                    except Exception as e:
                        log(f"Error processing container: {e}", verbose, is_error=True, status=status, log_caller_file="scraping_utils.py")
                        continue

                if len(tweets_data) >= max_tweets:
                    break

            time.sleep(1)

        log(f"Scraping completed. Total tweets collected: {len(tweets_data)}", verbose, status=status, log_caller_file="scraping_utils.py")

    except Exception as e:
        log(f"Error during page scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraping_utils.py")

    return tweets_data[:max_tweets]

def scrape_community_and_profiles(profile_name: str, max_tweets_profile: int = 20, max_tweets_community: int = 20, verbose: bool = False, headless: bool = True) -> List[Dict[str, Any]]:
    all_tweets = []

    profile_config = PROFILES[profile_name]
    profile_props = profile_config.get('properties', {})
    target_profiles = profile_props.get('target_profiles', [])
    browser_profile = profile_props.get('browser_profile')

    actual_browser_profile = browser_profile if browser_profile else profile_name
    user_data_dir = get_browser_data_dir(actual_browser_profile)
    driver = None

    try:
        driver, _ = setup_driver(user_data_dir, profile=actual_browser_profile, headless=headless, verbose=verbose)
        driver.get("https://x.com/home")
        time.sleep(3)

        if target_profiles:
            with Status(f"[white]Scraping {len(target_profiles)} target profiles...[/white]", spinner="dots", console=console) as status:
                for target_profile in target_profiles:
                    try:
                        username = target_profile
                        log(f"Scraping tweets from @{username}...", verbose, status=status, log_caller_file="scraping_utils.py")

                        search_query = f"from:{username} -filter:replies"
                        encoded_query = quote(search_query)
                        search_url = f"https://x.com/search?q={encoded_query}&src=typed_query"

                        driver.get(search_url)
                        time.sleep(3)

                        tweets_data = scrape_current_page(driver, max_tweets_profile, verbose, status)
                        all_tweets.extend(tweets_data)

                        log(f"Scraped {len(tweets_data)} tweets from @{username}", verbose, status=status, log_caller_file="scraping_utils.py")

                    except Exception as e:
                        log(f"Error scraping @{target_profile}: {e}", verbose, is_error=True, status=status, log_caller_file="scraping_utils.py")
                        continue
                status.stop()

        communities = profile_props.get('communities', [''])
        with Status(f"[white]Scraping {len(communities)} communities...[/white]", spinner="dots", console=console) as status:
            for community_name in communities:
                try:
                    log(f"Scraping community '{community_name}'...", verbose, status=status, log_caller_file="scraping_utils.py")

                    driver.get("https://x.com/home")
                    time.sleep(2)

                    if community_name:
                        try:
                            community_tab = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, f"//a[@role='tab']//span[contains(text(), '{community_name}')]"))
                            )
                            community_tab.click()
                            log(f"Successfully clicked on '{community_name}' community tab.", verbose, status=status, log_caller_file="scraping_utils.py")
                            time.sleep(5)
                        except Exception as e:
                            log(f"Community tab not found, trying search approach: {e}", verbose, status=status, log_caller_file="scraping_utils.py")
                            try:
                                search_box = WebDriverWait(driver, 10).until(
                                    EC.element_to_be_clickable((By.XPATH, "//input[@data-testid='SearchBox_Search_Input']"))
                                )
                                search_box.clear()
                                search_box.send_keys(community_name)
                                time.sleep(1)
                                search_box.send_keys(Keys.RETURN)
                                time.sleep(3)
                                community_links = WebDriverWait(driver, 10).until(
                                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@href, '/i/communities/') or contains(@href, '/communities/')]"))
                                )
                                if community_links:
                                    community_links[0].click()
                                    log(f"Successfully navigated to community via search: {community_name}", verbose, status=status, log_caller_file="scraping_utils.py")
                                    time.sleep(5)
                                else:
                                    raise Exception("No community links found in search results")
                            except Exception as search_e:
                                log(f"Could not navigate to community '{community_name}' via search either: {search_e}. Proceeding with general home feed scraping.", verbose, is_error=False, status=status, log_caller_file="scraping_utils.py")
                                driver.get("https://x.com/home")
                                time.sleep(5)

                    tweets_data = scrape_current_page(driver, max_tweets_community, verbose, status)
                    all_tweets.extend(tweets_data)

                    log(f"Scraped {len(tweets_data)} tweets from community '{community_name}'", verbose, status=status, log_caller_file="scraping_utils.py")

                except Exception as e:
                    log(f"Error scraping community '{community_name}': {e}", verbose, is_error=True, status=status, log_caller_file="scraping_utils.py")
                    continue
            status.stop()

    finally:
        if driver:
            driver.quit()

    return all_tweets

def save_scraped_content(scraped_tweets: List[Dict[str, Any]], profile_name: str, verbose: bool = False) -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    content_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "scraped_tweets": scraped_tweets,
        "metadata": {
            "total_tweets": len(scraped_tweets),
            "scrape_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filename = f"scraped_content_x_{timestamp}.json"
    filepath = os.path.join(suggestions_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)

        log(f"Saved {len(scraped_tweets)} scraped tweets to {filepath}", verbose, log_caller_file="scraping_utils.py")
        return filepath

    except Exception as e:
        log(f"Error saving scraped content: {e}", verbose, is_error=True, log_caller_file="scraping_utils.py")
        return ""

def run_suggestions_workflow(profile_name: str, max_tweets_profile: int = 20, max_tweets_community: int = 20, verbose: bool = False, headless: bool = True) -> Dict[str, Any]:
    if profile_name not in PROFILES:
        return {"error": f"Profile '{profile_name}' not found"}

    log(f"Starting content scraping workflow for profile: {profile_name}", verbose, log_caller_file="scraping_utils.py")

    scraped_tweets = scrape_community_and_profiles(profile_name, max_tweets_profile, max_tweets_community, verbose, headless)

    if not scraped_tweets:
        return {"error": "No tweets were scraped from communities or target profiles"}

    log(f"Total tweets scraped: {len(scraped_tweets)}", verbose, log_caller_file="scraping_utils.py")

    saved_file = save_scraped_content(scraped_tweets, profile_name, verbose)

    result = {
        "success": True,
        "total_tweets_scraped": len(scraped_tweets),
        "saved_file": saved_file
    }

    return result

def get_latest_approved_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    approved_files_with_media = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_') and f.endswith('_with_media.json')]
    if approved_files_with_media:
        approved_files_with_media.sort(reverse=True)
        return os.path.join(suggestions_dir, approved_files_with_media[0])

    approved_files = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_') and f.endswith('.json')]
    if not approved_files:
        return ""

    approved_files.sort(reverse=True)
    return os.path.join(suggestions_dir, approved_files[0])

def get_latest_suggestions_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    suggestions_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_') and f.endswith('.json')]
    if not suggestions_files:
        return ""

    suggestions_files.sort(reverse=True)
    return os.path.join(suggestions_dir, suggestions_files[0])