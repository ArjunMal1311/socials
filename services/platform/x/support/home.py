import os
import time
import json
import random

from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from services.support.web_driver_handler import setup_driver
from services.support.storage.storage_factory import get_storage
from services.support.path_config import get_browser_data_dir, ensure_dir_exists

from services.platform.x.support.process_container import process_container
from services.platform.x.support.post_approved_tweets import post_tweet_reply
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll
from services.platform.x.support.home_support import _generate_with_pool, _ensure_home_mode_folder, _cleanup_temp_media_dir, _prepare_media_for_gemini_home_mode, _navigate_to_community

console = Console()

def run_home_mode(profile_name: str, custom_prompt: str, max_tweets: int = 10, status=None, api_key: str = None, ignore_video_tweets: bool = False, community_name: Optional[str] = None, post_via_api: bool = False, specific_search_url: Optional[str] = None, target_profile_name: Optional[str] = None, verbose: bool = False, headless: bool = True, browser_data_dir: str = None) -> Any:
    user_data_dir = browser_data_dir or get_browser_data_dir(profile_name)
    temp_processing_dir = _ensure_home_mode_folder(profile_name)
    setup_messages = []
    
    log(f"Home Mode: user_data_dir is {user_data_dir}", verbose, status, log_caller_file="home.py")

    try:
        driver, messages_from_driver = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, status=status, headless=headless)
        setup_messages.extend(messages_from_driver)
        log(f"Messages from driver setup: {messages_from_driver}", verbose, status, log_caller_file="home.py")
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="home.py")
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True, log_caller_file="home.py")
        log(f"WebDriver setup messages: {setup_messages}", verbose, status, is_error=True, log_caller_file="home.py")
        return None

    if specific_search_url:
        driver.get(specific_search_url)
        log(f"Navigated to specific search URL: {specific_search_url}", verbose, status, log_caller_file="home.py")
    else:
        driver.get("https://x.com/home")
        log("Navigated to x.com/home...", verbose, status, log_caller_file="home.py")

    time.sleep(8)

    if community_name:
        _navigate_to_community(driver, community_name, verbose)

    raw_containers: List[Dict[str, Any]] = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    if status:
        status.update("Starting tweet collection (Home Mode)...")
    
    last_new_content_time = time.time()

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count
            )
            if new_tweets_in_pass > 0:
                last_new_content_time = time.time()

            if time.time() - last_new_content_time > 10:
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                last_new_content_time = time.time()
                no_new_content_count = 0

            if status:
                status.update(f"Collecting tweets: {len(processed_tweet_ids)} collected...")
            time.sleep(1)
    except KeyboardInterrupt:
        log("Collection stopped manually.", verbose, status, log_caller_file="home.py")

    if not raw_containers:
        log("No tweets found during collection.", verbose, status, log_caller_file="home.py")
        return driver

    if status:
        status.update(f"Processing collected tweets ({len(raw_containers)} raw containers)...")

    processed_tweets: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_container, c, {'name': profile_name}) for c in raw_containers[:max_tweets]]
        for future in futures:
            td = future.result()
            if td:
                td['name'] = profile_name
                processed_tweets.append(td)

    if status:
        status.update(f"Successfully processed {len(processed_tweets)} tweets for Gemini analysis.")

    api_pool = APIKeyPool()
    if api_key:
        api_pool.set_explicit_key(api_key)
    rate_limiter = RateLimiter()

    storage = get_storage('x', profile_name, 'action', verbose)
    all_replies = []
    if storage:
        all_replies = storage.get_all_approved_and_posted_tweets(verbose)
        log(f"Loaded {len(all_replies)} approved and posted tweets for context", verbose, status, log_caller_file="home.py")
    else:
        log("Warning: Could not initialize storage for approved tweets context", verbose, status, log_caller_file="home.py")

    enriched_items: List[Dict[str, Any]] = []
    for td in processed_tweets:
        media_urls = td.get('media_urls', [])
        if any('video' in str(url).lower() for url in media_urls):
            log(f"Skipping tweet {td.get('tweet_id')} - contains video content", verbose, status, log_caller_file="home.py")
            continue

        media_abs_paths = _prepare_media_for_gemini_home_mode(td, profile_name, temp_processing_dir, is_home_mode=True, ignore_video_tweets=ignore_video_tweets, verbose=verbose)
        args = (td['tweet_text'], media_abs_paths, profile_name, api_pool.get_key(), rate_limiter, custom_prompt, td['tweet_id'], all_replies)
        enriched_items.append({
            'tweet_data': td,
            'media_abs_paths': media_abs_paths,
            'gemini_args': args
        })

    if status:
        status.update(f"Running Gemini for {len(enriched_items)} tweets...")

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for item in enriched_items:
            args = item['gemini_args']
            if args[3]:
                future = executor.submit(_generate_with_pool, api_pool, args, status, verbose)
                future_map[future] = item
            else:
                log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True, log_caller_file="home.py")
                td = item['tweet_data']
                results.append({
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'tweet_date': td.get('tweet_date'),
                    'likes': td.get('likes', ''),
                    'retweets': td.get('retweets', ''),
                    'replies': td.get('replies', ''),
                    'views': td.get('views', ''),
                    'bookmarks': td.get('bookmarks', ''),
                    'media_urls': td.get('media_urls', [])
                })

        for future, item in future_map.items():
            try:
                td = item['tweet_data']
                generated_reply = future.result()
                record = {
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'tweet_date': td.get('tweet_date'),
                    'likes': td.get('likes', ''),
                    'retweets': td.get('retweets', ''),
                    'replies': td.get('replies', ''),
                    'views': td.get('views', ''),
                    'bookmarks': td.get('bookmarks', ''),
                    'media_urls': td.get('media_urls', []),
                    'generated_reply': generated_reply,
                    'profile': target_profile_name if target_profile_name else profile_name,
                    'status': 'ready_for_approval',
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'profile_image_url': td.get('profile_image_url', '')
                }
                results.append(record)
            except Exception as e:
                td = item['tweet_data']
                log(f"Error generating analysis for tweet {td.get('tweet_id')}: {str(e)}", verbose, status, is_error=True, log_caller_file="home.py")


        replies_dir = os.path.join("tmp", "replies", profile_name)
        ensure_dir_exists(replies_dir)
        schedule_file = os.path.join(replies_dir, "replies.json")

        with open(schedule_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        log(f"Saved {len(results)} results to {schedule_file}", verbose, status=status, log_caller_file="home.py")

    _cleanup_temp_media_dir(temp_processing_dir, verbose)

    return driver, results


def post_approved_home_mode_replies(driver, profile_name: str, post_via_api: bool = False, verbose: bool = False) -> Dict[str, Any]:
    replies_dir = os.path.join("tmp", "replies", profile_name)
    replies_path = os.path.join(replies_dir, 'replies.json')

    if not os.path.exists(replies_path):
        log(f"Replies file not found: {replies_path}", verbose, is_error=True, log_caller_file="home.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    with open(replies_path, 'r') as f:
        try:
            items: List[Dict[str, Any]] = json.load(f)
        except Exception as e:
            log(f"Failed to read replies file: {e}", verbose, is_error=True, log_caller_file="home.py")
            return {"processed": 0, "posted": 0, "failed": 0}

    generated_replies = [item for item in items if item.get('generated_reply') and item.get('status') == 'approved']

    if not generated_replies:
        log("No approved replies found to post.", verbose, is_error=False, log_caller_file="home.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    if post_via_api:
        posted = 0
        failed = 0
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        log("Posting replies via Twitter API...", verbose, log_caller_file="home.py")

        for item in generated_replies:
            tweet_id = item.get('tweet_id')
            reply_text = item.get('generated_reply')

            if not tweet_id or not reply_text:
                failed += 1
                continue

            success = post_tweet_reply(str(tweet_id), str(reply_text), profile_name=profile_name, verbose=verbose)
            if success:
                posted += 1
                item['status'] = 'posted'
                item['posted_date'] = now_str
            else:
                failed += 1

        with open(replies_path, 'w') as f:
            json.dump(items, f, indent=2)

        return {"processed": len(generated_replies), "posted": posted, "failed": failed}

    time.sleep(5)

    posted = 0
    failed = 0

    log("Starting automated posting of generated replies via browser...", verbose, log_caller_file="home.py")

    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(random.uniform(2, 3))

    for i, tweet_data in enumerate(generated_replies):
        tweet_url = tweet_data.get('tweet_url')
        generated_reply = tweet_data.get('generated_reply')
        tweet_id = tweet_data.get('tweet_id')

        if not tweet_url or not generated_reply or not tweet_id:
            log(f"Skipping invalid entry: {tweet_data}", verbose, is_error=False, log_caller_file="home.py")
            failed += 1
            continue

        found_tweet_element = None
        scroll_attempts = 0
        max_scroll_attempts = 30

        while found_tweet_element is None and scroll_attempts < max_scroll_attempts:
            try:
                log(f"Searching for tweet ID: {tweet_id} on home feed (scroll attempt {scroll_attempts + 1}/{max_scroll_attempts})...", verbose, log_caller_file="home.py")

                tweet_link_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f'article[role="article"][data-testid="tweet"] a[href*="/status/{tweet_id}"]'))
                )
                found_tweet_element = tweet_link_element.find_element(By.XPATH, './ancestor::article[@role="article"]')

                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", found_tweet_element)
                time.sleep(random.uniform(1, 2))

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                log(f"Tweet ID {tweet_id} not visible or stale ({e}). Scrolling down to load more content...", verbose, log_caller_file="home.py")
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                scroll_attempts += 1

        if found_tweet_element is None:
            log(f"Could not find tweet with ID {tweet_id} on home feed after {max_scroll_attempts} scrolls. Skipping.", verbose, is_error=False, log_caller_file="home.py")
            failed += 1
            tweet_data['status'] = 'tweet_not_found'
            with open(replies_path, 'w') as f:
                json.dump(items, f, indent=2)
            continue

        try:
            log(f"Found tweet ID: {tweet_id}. Attempting to post reply.", verbose, log_caller_file="home.py")

            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", found_tweet_element)
            time.sleep(random.uniform(1, 2))

            reply_button = None
            reply_selectors = [
                '[data-testid="reply"]',
                '[role="group"] [data-testid="reply"]',
                'button[data-testid="reply"]',
                '[aria-label*="Reply" i]',
                '[aria-label*="reply" i]'
            ]

            for selector in reply_selectors:
                try:
                    reply_button = WebDriverWait(found_tweet_element, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    log(f"Found reply button with selector: {selector}", verbose, log_caller_file="home.py")
                    break
                except:
                    continue

            if not reply_button:
                raise Exception("Could not find reply button with any selector")

            try:
                reply_button.click()
                log("Clicked reply button with Selenium", verbose, log_caller_file="home.py")
            except Exception as click_e:
                log(f"Selenium click failed, trying JavaScript click: {click_e}", verbose, log_caller_file="home.py")
                driver.execute_script("arguments[0].click();", reply_button)

            time.sleep(random.uniform(2, 3))

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                log("Reply dialog opened successfully", verbose, log_caller_file="home.py")
            except Exception as dialog_e:
                log(f"Reply dialog did not open: {dialog_e}", verbose, is_error=True, log_caller_file="home.py")
                raise Exception("Reply dialog failed to open")

            reply_textarea = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
            )

            reply_textarea.clear()
            time.sleep(0.5)

            for char in generated_reply:
                reply_textarea.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            time.sleep(random.uniform(1, 2))

            post_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
            )

            driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", post_button)
            time.sleep(0.5)

            try:
                post_button.click()
                log("Clicked post button with Selenium", verbose, log_caller_file="home.py")
            except Exception as post_click_e:
                log(f"Selenium post button click failed, trying JavaScript: {post_click_e}", verbose, log_caller_file="home.py")
                driver.execute_script("arguments[0].click();", post_button)

            time.sleep(random.uniform(2, 4))

            try:
                WebDriverWait(driver, 5).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                log("Reply dialog closed successfully - reply posted", verbose, log_caller_file="home.py")
            except Exception as verify_e:
                log(f"Could not verify reply was posted: {verify_e}", verbose, is_error=False, log_caller_file="home.py")

            try:
                like_button = WebDriverWait(found_tweet_element, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="like"]'))
                )
                like_button.click()
                log(f"Successfully liked tweet {tweet_id}.", verbose, is_error=False, log_caller_file="home.py")
                time.sleep(random.uniform(1, 2))
            except Exception as like_e:
                log(f"Could not like tweet {tweet_id}: {like_e}", verbose, is_error=False, log_caller_file="home.py")

            log(f"Successfully posted reply to {tweet_url}", verbose, is_error=False, log_caller_file="home.py")
            posted += 1
            tweet_data['status'] = 'posted'

        except Exception as e:
            log(f"Failed to post reply to {tweet_url}: {e}", verbose, is_error=True, log_caller_file="home.py")
            failed += 1
            tweet_data['status'] = 'post_failed'

        with open(replies_path, 'w') as f:
            json.dump(items, f, indent=2)

        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.3);")
        time.sleep(random.uniform(1, 2))

    return {"processed": len(generated_replies), "posted": posted, "failed": failed}