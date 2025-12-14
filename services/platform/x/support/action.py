import os
import json
import time
import random

from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from selenium.webdriver.support.ui import WebDriverWait
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir
from selenium.webdriver.support import expected_conditions as EC
from services.platform.x.support.process_container import process_container
from services.platform.x.support.post_approved_tweets import post_tweet_reply
from services.support.database import save_data_to_service, get_data_from_service
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from services.platform.x.support.action_support import _generate_with_pool, _ensure_action_mode_folder, _cleanup_temp_media_dir, _prepare_media_for_gemini_action_mode, _navigate_to_community

console = Console()

def run_action_mode_online(profile_name: str, custom_prompt: str, max_tweets: int = 10, status=None, api_key: str = None, ignore_video_tweets: bool = False, run_number: int = 1, community_name: Optional[str] = None, post_via_api: bool = False, specific_search_url: Optional[str] = None, target_profile_name: Optional[str] = None, verbose: bool = False, headless: bool = True) -> Any:
    user_data_dir = get_browser_data_dir(profile_name)
    schedule_folder = _ensure_action_mode_folder(profile_name)
    setup_messages = []
    log(f"Action Mode Online: user_data_dir is {user_data_dir}", verbose, status, log_caller_file="action.py")

    try:
        driver, messages_from_driver = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, status=status, headless=headless)
        setup_messages.extend(messages_from_driver)
        log(f"Messages from driver setup: {messages_from_driver}", verbose, status, log_caller_file="action.py")
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="action.py")
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True, log_caller_file="action.py")
        log(f"WebDriver setup messages: {setup_messages}", verbose, status, is_error=True, log_caller_file="action.py")
        return None

    if specific_search_url:
        driver.get(specific_search_url)
        log(f"Navigated to specific search URL: {specific_search_url}", verbose, status, log_caller_file="action.py")
    else:
        driver.get("https://x.com/home")
        log("Navigated to x.com/home...", verbose, status, log_caller_file="action.py")
    time.sleep(5)
    
    if community_name:
        _navigate_to_community(driver, community_name, verbose)

    raw_containers: List[Dict[str, Any]] = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    if status:
        status.update("Starting tweet collection (Action Mode Online)...")
    
    last_new_content_time = time.time()

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count
            )
            if new_tweets_in_pass > 0:
                last_new_content_time = time.time()

            if time.time() - last_new_content_time > 10:
                log("No new content for 10 seconds. Forcing a scroll.", verbose, status, is_error=False, log_caller_file="action.py")
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                last_new_content_time = time.time()
                no_new_content_count = 0

            if status:
                status.update(f"Collecting tweets: {len(processed_tweet_ids)} collected...")
            time.sleep(1)
    except KeyboardInterrupt:
        log("Collection stopped manually.", verbose, status, log_caller_file="action.py")

    if not raw_containers:
        log("No tweets found during collection.", verbose, status, log_caller_file="action.py")
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

    all_replies = get_data_from_service(service_preference="google_sheets", operation_type="generated_replies", profile_name=profile_name, verbose=verbose, status=status)

    enriched_items: List[Dict[str, Any]] = []
    for td in processed_tweets:
        media_abs_paths = _prepare_media_for_gemini_action_mode(td, profile_name, schedule_folder, is_online_mode=True, ignore_video_tweets=ignore_video_tweets, verbose=verbose)
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
                log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True, log_caller_file="action.py")
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
                    'bookmarks': td.get('bookmarks', '') 
                })

        for future, item in future_map.items():
            try:
                td = item['tweet_data']
                record = {
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'tweet_date': td.get('tweet_date'),
                    'likes': td.get('likes', ''), 
                    'retweets': td.get('retweets', ''), 
                    'replies': td.get('replies', ''), 
                    'views': td.get('views', ''), 
                    'bookmarks': td.get('bookmarks', '') 
                }
                results.append(record)
            except Exception as e:
                td = item['tweet_data']
                log(f"Error generating analysis for tweet {td.get('tweet_id')}: {str(e)}", verbose, status, is_error=True, log_caller_file="action.py")
                results.append({
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'media_files': td.get('media_urls', ''),
                    'generated_reply': f"Error: {str(e)}",
                    'profile': target_profile_name if target_profile_name else profile_name,
                    'status': 'analysis_failed',
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'run_number': run_number,
                    'profile_image_url': td.get('profile_image_url', ''),
                    'likes': td.get('likes', ''), 
                    'retweets': td.get('retweets', ''), 
                    'replies': td.get('replies', ''), 
                    'views': td.get('views', ''), 
                    'bookmarks': td.get('bookmarks', '') 
                })

    if results:
        log(f"[DEBUG] Results to save ({len(results)} items): {results[:2]}... (showing first 2)", verbose, status=status, log_caller_file="action.py")
        log(f"Saving {len(results)} generated replies to Google Sheet...", verbose, status=status, log_caller_file="action.py")
        save_data_to_service(
            data=results,
            service_preference="google_sheets",
            operation_type="initial_generated_replies",
            profile_name=profile_name,
            verbose=verbose,
            status=status
        )
    _cleanup_temp_media_dir(schedule_folder, verbose)
    
    return driver


def post_approved_action_mode_replies_online(driver, profile_name: str, run_number: int, post_via_api: bool = False, verbose: bool = False) -> Dict[str, Any]:
    today_date = datetime.now().strftime('%Y-%m-%d')
    items_with_indices = get_data_from_service(service_preference="google_sheets", operation_type="online_action_mode_replies", profile_name=profile_name, target_date=today_date, run_number=run_number, verbose=verbose, status=None)
    approved_replies_with_indices = [(item, idx) for item, idx in items_with_indices if item.get('status') == 'approved' and item.get('profile') == profile_name]

    if not approved_replies_with_indices:
        log(f"No approved replies found for today ({today_date}) and run number ({run_number}) in the Google Sheet.", verbose, is_error=False, log_caller_file="action.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    time.sleep(5)

    posted = 0
    failed = 0
    updates_to_sheet = []

    log("Starting automated posting of approved replies from Google Sheets...", verbose, log_caller_file="action.py")

    if driver and not post_via_api:
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(random.uniform(2, 3))

    for i, (tweet_data, row_idx) in enumerate(approved_replies_with_indices):
        tweet_url = tweet_data.get('tweet_url')
        generated_reply = tweet_data.get('generated_reply')
        tweet_id = tweet_data.get('tweet_id')

        if not tweet_url or not generated_reply or not tweet_id:
            log(f"Skipping invalid entry in Google Sheet: {tweet_data}", verbose, is_error=False, log_caller_file="action.py")
            failed += 1
            updates_to_sheet.append({
                'range': f'{profile_name}_online_replies!G{row_idx}',
                'values': [['invalid_entry']]
            })
            continue

        if not post_via_api:
            found_tweet_element = None
            scroll_attempts = 0
            max_scroll_attempts = 30

            while found_tweet_element is None and scroll_attempts < max_scroll_attempts:
                try:
                    log(f"Searching for tweet ID: {tweet_id} on home feed (scroll attempt {scroll_attempts + 1}/{max_scroll_attempts})...", verbose, log_caller_file="action.py")

                    tweet_link_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, f'article[role="article"][data-testid="tweet"] a[href*="/status/{tweet_id}"]'))
                    )
                    found_tweet_element = tweet_link_element.find_element(By.XPATH, './ancestor::article[@role="article"]')
                    
                    driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", found_tweet_element)
                    time.sleep(random.uniform(1, 2))
                    
                except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                    log(f"Tweet ID {tweet_id} not visible or stale ({e}). Scrolling down to load more content...", verbose, log_caller_file="action.py")
                    driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                    time.sleep(random.uniform(2, 4))
                    scroll_attempts += 1

            if found_tweet_element is None:
                log(f"Could not find tweet with ID {tweet_id} on home feed after {max_scroll_attempts} scrolls. Skipping.", verbose, is_error=False, log_caller_file="action.py")
                failed += 1
                updates_to_sheet.append({
                    'range': f'{profile_name}_online_replies!G{row_idx}',
                    'values': [['tweet_not_found']]
                })
                continue

        try:
            if post_via_api:
                log(f"Found tweet ID: {tweet_id}. Posting reply via API.", verbose, log_caller_file="action.py")
                success = post_tweet_reply(tweet_id, generated_reply, profile_name=profile_name)
                if success:
                    log(f"Successfully posted reply to {tweet_url} via API", verbose, is_error=False, log_caller_file="action.py")
                    posted += 1
                    current_posted_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    updates_to_sheet.append({
                        'range': f'{profile_name}_online_replies!G{row_idx}',
                        'values': [['posted_via_api']]
                    })
                    updates_to_sheet.append({
                        'range': f'{profile_name}_online_replies!H{row_idx}',
                        'values': [[current_posted_date]]
                    })
                    save_data_to_service(data=tweet_data, service_preference="google_sheets", operation_type="posted_reply", profile_name=profile_name, verbose=verbose)
                    time.sleep(2)
                else:
                    log(f"Failed to post reply to {tweet_url} via API", verbose, is_error=True, log_caller_file="action.py")
                    failed += 1
                    updates_to_sheet.append({
                        'range': f'{profile_name}_online_replies!G{row_idx}',
                        'values': [['api_post_failed']]
                    })
            else:
                log(f"Found tweet ID: {tweet_id}. Attempting to post reply.", verbose, log_caller_file="action.py")
                
                reply_button = WebDriverWait(found_tweet_element, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="reply"]'))
                )
                reply_button.click()
                time.sleep(random.uniform(1.5, 2.5))

                reply_textarea = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                )
                for char in generated_reply:
                    reply_textarea.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))
                time.sleep(random.uniform(1, 2))

                post_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
                )
                post_button.click()
                time.sleep(random.uniform(2, 4))

                try:
                    like_button = WebDriverWait(found_tweet_element, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="like"]'))
                    )
                    like_button.click()
                    log(f"Successfully liked tweet {tweet_id}.", verbose, is_error=False, log_caller_file="action.py")
                    time.sleep(random.uniform(1, 2))
                except Exception as like_e:
                    log(f"Could not like tweet {tweet_id}: {like_e}", verbose, is_error=False, log_caller_file="action.py")

                log(f"Successfully posted reply to {tweet_url}", verbose, is_error=False, log_caller_file="action.py")
                posted += 1
                current_posted_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updates_to_sheet.append({
                    'range': f'{profile_name}_online_replies!G{row_idx}',
                    'values': [['posted']]
                })
                updates_to_sheet.append({
                    'range': f'{profile_name}_online_replies!H{row_idx}',
                    'values': [[current_posted_date]]
                })
                save_data_to_service(data=tweet_data, service_preference="google_sheets", operation_type="posted_reply", profile_name=profile_name, verbose=verbose)

        except Exception as e:
            log(f"Failed to post reply to {tweet_url}: {e}", verbose, is_error=True, log_caller_file="action.py")
            failed += 1
            updates_to_sheet.append({
                'range': f'{profile_name}_online_replies!G{row_idx}',
                'values': [['post_failed']]
            })
        
        if driver and not post_via_api:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.3);")
            time.sleep(random.uniform(1, 2))
    
    if updates_to_sheet:
        save_data_to_service(data=updates_to_sheet, service_preference="google_sheets", operation_type="batch_update_online_replies", profile_name=profile_name, verbose=verbose, status=None, updates_to_sheet=updates_to_sheet)

    return {"processed": len(approved_replies_with_indices), "posted": posted, "failed": failed}