import re
import os
import json
import time
import shutil
import random
import pyperclip

from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from selenium.webdriver.support.ui import WebDriverWait
from services.support.image_download import download_images
from services.support.web_driver_handler import setup_driver
from selenium.webdriver.support import expected_conditions as EC
from services.support.video_download import download_twitter_videos
from services.platform.x.support.process_container import process_container
from services.platform.x.support.post_approved_tweets import post_tweet_reply
from services.platform.x.support.action_html import build_action_mode_schedule_html
from services.platform.x.support.generate_reply_with_key import generate_reply_with_key
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from services.support.path_config import get_browser_data_dir, get_replies_dir, get_action_schedule_file_path, ensure_dir_exists
from services.support.sheets_util import get_google_sheets_service, save_action_mode_replies_to_sheet, get_online_action_mode_replies, batch_update_online_action_mode_replies, sanitize_sheet_name, get_generated_replies, save_posted_reply_to_replied_tweets_sheet

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if is_error:
        if status:
            status.stop()
        log_message = message
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[action_mode.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[action_mode.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)
        
def filter_bmp(text):
    return ''.join(c for c in text if ord(c) <= 0xFFFF)

def _generate_with_pool(api_pool: APIKeyPool, args: tuple, status=None, verbose: bool = False, max_attempts: int = 6):
    attempts = 0
    last_error_text = None
    tried_keys = set()
    
    while attempts < max_attempts:
        api_key = api_pool.get_key()
        if not api_key:
            return "Error generating reply: No API key available"
        
        if api_key in tried_keys and api_pool.size() > 1:
            continue
        
        tried_keys.add(api_key)
        new_args = (args[0], args[1], args[2], api_key, args[4], args[5], args[6], args[7])
        result = generate_reply_with_key(new_args, status=status, verbose=verbose)
        
        if isinstance(result, str) and result.startswith("Error generating reply:"):
            last_error_text = result
            if re.search(r"\b429\b|rate limit|quota|Resource has been exhausted|Too Many Requests", result, re.IGNORECASE):
                api_pool.report_failure(api_key, result)
                attempts += 1
                if api_pool.size() > 1:
                    continue
                else:
                    break
            else:
                return result
        else:
            return result
        
    return last_error_text or "Error generating reply: Exhausted retries"

def _ensure_action_mode_folder(profile_name: str) -> str:
    base_dir = get_replies_dir(profile_name)
    return ensure_dir_exists(base_dir)

def _get_temp_media_dir(schedule_folder: str) -> str:
    temp_dir = os.path.join(schedule_folder, '_temp_media')
    return ensure_dir_exists(temp_dir)

def _cleanup_temp_media_dir(schedule_folder: str, verbose: bool = False):
    temp_dir = os.path.join(schedule_folder, '_temp_media')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        _log(f"Cleaned up temporary media directory: {temp_dir}", verbose)


def _copy_medi_into_action_mode(media_paths: List[str], schedule_folder: str, verbose: bool = False) -> List[str]:
    saved_abs_paths: List[str] = []
    for path in media_paths:
        if not path:
            continue
        try:
            filename = os.path.basename(path)
            target_path = os.path.join(schedule_folder, filename)
            
            if os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                suffix_idx = 1
                while os.path.exists(target_path):
                    filename = f"{name}_{suffix_idx}{ext}"
                    target_path = os.path.join(schedule_folder, filename)
                    suffix_idx += 1
            shutil.copy2(path, target_path)
            saved_abs_paths.append(os.path.abspath(target_path))
        except Exception as e:
            _log(f"Error copying media {path} into schedule folder: {e}", verbose, is_error=True)
    return saved_abs_paths

def _prepare_media_for_gemini_action_mode(tweet_data: Dict[str, Any], profile_name: str, schedule_folder: str, is_online_mode: bool = False, ignore_video_tweets: bool = False, verbose: bool = False) -> List[str]:
    media_abs_paths_for_gemini: List[str] = []
    raw_media_urls = tweet_data.get('media_urls')

    if is_online_mode:
        temp_media_dir = _get_temp_media_dir(schedule_folder)
        if raw_media_urls:
            if ignore_video_tweets and (raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video')):
                _log(f"Ignoring video tweet {tweet_data['tweet_id']} due to --ignore-video-tweets flag.", verbose, is_error=False)
            elif raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
                try:
                    video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True)
                    if video_path:
                        copied = _copy_medi_into_action_mode([video_path], temp_media_dir, verbose)
                        media_abs_paths_for_gemini.extend(copied)
                    else:
                        _log(f"Video download failed or returned no path for {tweet_data['tweet_id']}", verbose, is_error=False)
                except Exception as e:
                    _log(f"Error handling video for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)
            elif isinstance(raw_media_urls, (list, str)):
                image_urls = [u.strip() for u in (raw_media_urls if isinstance(raw_media_urls, list) else str(raw_media_urls).split(';')) if u and u.strip()]
                if image_urls:
                    downloaded_images = download_images(image_urls, temp_media_dir)
                    copied = _copy_medi_into_action_mode(downloaded_images, temp_media_dir, verbose)
                    media_abs_paths_for_gemini.extend(copied)
                
        return media_abs_paths_for_gemini

    if ignore_video_tweets and (raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video')):
        _log(f"Ignoring video tweet {tweet_data['tweet_id']} due to --ignore-video-tweets flag.", verbose, is_error=False)
    elif raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
        try:
            video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True)
            if video_path:
                copied = _copy_medi_into_action_mode([video_path], schedule_folder, verbose)
                media_abs_paths_for_gemini.extend(copied)
            else:
                _log(f"Video download failed or returned no path for {tweet_data['tweet_id']}", verbose, is_error=False)
        except Exception as e:
            _log(f"Error handling video for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)
    elif raw_media_urls:
        try:
            image_urls = [u.strip() for u in str(raw_media_urls).split(';') if u and u.strip()]
            if image_urls:
                downloaded_images = download_images(image_urls, profile_name)
                copied = _copy_medi_into_action_mode(downloaded_images, schedule_folder, verbose)
                media_abs_paths_for_gemini.extend(copied)
        except Exception as e:
            _log(f"Error handling images for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)

    return media_abs_paths_for_gemini

def _navigate_to_community(driver, community_name: str, verbose: bool = False):
    try:
        community_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[@role='tab']//span[contains(text(), '{community_name}')]"))
        )
        community_tab.click()
        _log(f"Successfully clicked on '{community_name}' community tab.", verbose)
        time.sleep(5)
    except Exception as e:
        _log(f"Could not find or click community tab '{community_name}': {e}. Proceeding with general home feed scraping.", verbose, is_error=False)

def run_action_mode_online(profile_name: str, custom_prompt: str, max_tweets: int = 10, status=None, api_key: str = None, ignore_video_tweets: bool = False, run_number: int = 1, community_name: Optional[str] = None, post_via_api: bool = False, specific_search_url: Optional[str] = None, target_profile_name: Optional[str] = None, verbose: bool = False, headless: bool = True) -> Any:
    user_data_dir = get_browser_data_dir(profile_name)
    schedule_folder = _ensure_action_mode_folder(profile_name)
    setup_messages = []
    _log(f"Action Mode Online: user_data_dir is {user_data_dir}", verbose, status)

    try:
        driver, messages_from_driver = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, status=status, headless=headless)
        setup_messages.extend(messages_from_driver)
        _log(f"Messages from driver setup: {messages_from_driver}", verbose, status)
        for msg in setup_messages:
            _log(msg, verbose, status)
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        _log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True)
        _log(f"WebDriver setup messages: {setup_messages}", verbose, status, is_error=True)
        return None

    if specific_search_url:
        driver.get(specific_search_url)
        _log(f"Navigated to specific search URL: {specific_search_url}", verbose, status)
    else:
        driver.get("https://x.com/home")
        _log("Navigated to x.com/home...", verbose, status)
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
                _log("No new content for 10 seconds. Forcing a scroll.", verbose, status, is_error=False)
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                last_new_content_time = time.time()
                no_new_content_count = 0

            if status:
                status.update(f"Collecting tweets: {len(processed_tweet_ids)} collected...")
            time.sleep(1)
    except KeyboardInterrupt:
        _log("Collection stopped manually.", verbose, status)

    if not raw_containers:
        _log("No tweets found during collection.", verbose, status)
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

    sheets_service = get_google_sheets_service(verbose=verbose, status=status)
    all_replies = []
    if sheets_service:
        try:
            profile_suffix = profile_name
            reply_sheet_name = f"{sanitize_sheet_name(profile_suffix)}_replied_tweets"
            all_replies = get_generated_replies(sheets_service, reply_sheet_name, verbose=verbose, status=status)
            if verbose:
                _log(f"Fetched {len(all_replies)} approved replies from sheet for review.", verbose, status)
        except Exception as e:
            _log(f"Error fetching generated replies for {profile_name}: {e}", verbose, status, is_error=True)
            all_replies = []

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
                _log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True)
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
                reply_text = future.result()
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
                    'media_files': td.get('media_urls', ''),
                    'generated_reply': reply_text,
                    'profile': target_profile_name if target_profile_name else profile_name,
                    'status': 'ready_for_approval',
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'run_number': run_number,
                    'profile_image_url': td.get('profile_image_url', ''),
                    'bookmarks': td.get('bookmarks', '') 
                }
                results.append(record)
            except Exception as e:
                td = item['tweet_data']
                _log(f"Error generating analysis for tweet {td.get('tweet_id')}: {str(e)}", verbose, status, is_error=True)
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

    if sheets_service:
        save_action_mode_replies_to_sheet(sheets_service, profile_name, results, verbose=verbose, status=status)
    else:
        _log("Google Sheets service not available. Skipping saving to sheet.", verbose, status, is_error=True)
    
    _cleanup_temp_media_dir(schedule_folder, verbose)
    
    return driver


def post_approved_action_mode_replies_online(driver, profile_name: str, run_number: int, post_via_api: bool = False, verbose: bool = False) -> Dict[str, Any]:
    service = get_google_sheets_service(verbose=verbose, status=None)
    if not service:
        _log("Google Sheets service not available. Cannot post replies.", verbose, is_error=True)
        return {"processed": 0, "posted": 0, "failed": 0}

    today_date = datetime.now().strftime('%Y-%m-%d')
    items_with_indices = get_online_action_mode_replies(service, profile_name, target_date=today_date, run_number=run_number, verbose=verbose, status=None)
    approved_replies_with_indices = [(item, idx) for item, idx in items_with_indices if item.get('status') == 'approved' and item.get('profile') == profile_name]

    if not approved_replies_with_indices:
        _log(f"No approved replies found for today ({today_date}) and run number ({run_number}) in the Google Sheet.", verbose, is_error=False)
        return {"processed": 0, "posted": 0, "failed": 0}

    time.sleep(5)

    posted = 0
    failed = 0
    updates_to_sheet = []

    _log("Starting automated posting of approved replies from Google Sheets...", verbose)

    if driver and not post_via_api:
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(random.uniform(2, 3))

    for i, (tweet_data, row_idx) in enumerate(approved_replies_with_indices):
        tweet_url = tweet_data.get('tweet_url')
        generated_reply = tweet_data.get('generated_reply')
        tweet_id = tweet_data.get('tweet_id')

        if not tweet_url or not generated_reply or not tweet_id:
            _log(f"Skipping invalid entry in Google Sheet: {tweet_data}", verbose, is_error=False)
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
                    _log(f"Searching for tweet ID: {tweet_id} on home feed (scroll attempt {scroll_attempts + 1}/{max_scroll_attempts})...", verbose)

                    tweet_link_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, f'article[role="article"][data-testid="tweet"] a[href*="/status/{tweet_id}"]'))
                    )
                    found_tweet_element = tweet_link_element.find_element(By.XPATH, './ancestor::article[@role="article"]')
                    
                    driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", found_tweet_element)
                    time.sleep(random.uniform(1, 2))
                    
                except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                    _log(f"Tweet ID {tweet_id} not visible or stale ({e}). Scrolling down to load more content...", verbose)
                    driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                    time.sleep(random.uniform(2, 4))
                    scroll_attempts += 1

            if found_tweet_element is None:
                _log(f"Could not find tweet with ID {tweet_id} on home feed after {max_scroll_attempts} scrolls. Skipping.", verbose, is_error=False)
                failed += 1
                updates_to_sheet.append({
                    'range': f'{profile_name}_online_replies!G{row_idx}',
                    'values': [['tweet_not_found']]
                })
                continue

        try:
            if post_via_api:
                _log(f"Found tweet ID: {tweet_id}. Posting reply via API.", verbose)
                success = post_tweet_reply(tweet_id, generated_reply, profile_name=profile_name)
                if success:
                    _log(f"Successfully posted reply to {tweet_url} via API", verbose, is_error=False)
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
                    save_posted_reply_to_replied_tweets_sheet(service, profile_name, tweet_data, verbose=verbose)
                    time.sleep(2)
                else:
                    _log(f"Failed to post reply to {tweet_url} via API", verbose, is_error=True)
                    failed += 1
                    updates_to_sheet.append({
                        'range': f'{profile_name}_online_replies!G{row_idx}',
                        'values': [['api_post_failed']]
                    })
            else:
                _log(f"Found tweet ID: {tweet_id}. Attempting to post reply.", verbose)
                
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
                    _log(f"Successfully liked tweet {tweet_id}.", verbose, is_error=False)
                    time.sleep(random.uniform(1, 2))
                except Exception as like_e:
                    _log(f"Could not like tweet {tweet_id}: {like_e}", verbose, is_error=False)

                _log(f"Successfully posted reply to {tweet_url}", verbose, is_error=False)
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
                save_posted_reply_to_replied_tweets_sheet(service, profile_name, tweet_data, verbose=verbose)

        except Exception as e:
            _log(f"Failed to post reply to {tweet_url}: {e}", verbose, is_error=True)
            failed += 1
            updates_to_sheet.append({
                'range': f'{profile_name}_online_replies!G{row_idx}',
                'values': [['post_failed']]
            })
        
        if driver and not post_via_api:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.3);")
            time.sleep(random.uniform(1, 2))
    
    if updates_to_sheet:
        batch_update_online_action_mode_replies(service, profile_name, updates_to_sheet, verbose=verbose, status=None)

    return {"processed": len(approved_replies_with_indices), "posted": posted, "failed": failed}

def post_approved_action_mode_replies(driver, profile_name: str, verbose: bool = False) -> Dict[str, Any]:
    service = get_google_sheets_service(verbose=verbose, status=None)
    if not service:
        _log("Google Sheets service not available. Cannot post replies.", verbose, is_error=True)
        return {"processed": 0, "posted": 0, "failed": 0}

    schedule_folder = _ensure_action_mode_folder(profile_name)
    schedule_path = os.path.join(schedule_folder, 'schedule.json')
    
    if not os.path.exists(schedule_path):
        _log(f"Schedule file not found for action mode: {schedule_path}", verbose, is_error=True)
        return {"processed": 0, "posted": 0, "failed": 0}

    with open(schedule_path, 'r') as f:
        try:
            items: List[Dict[str, Any]] = json.load(f)
        except Exception as e:
            _log(f"Failed to read action mode schedule file: {e}", verbose, is_error=True)
            return {"processed": 0, "posted": 0, "failed": 0}

    approved_replies = [item for item in items if item.get('status') == 'approved']

    if not approved_replies:
        _log("No approved replies found in the schedule.", verbose, is_error=False)
        return {"processed": 0, "posted": 0, "failed": 0}

    time.sleep(5)

    posted = 0
    failed = 0

    _log("Starting automated posting of approved replies...", verbose)

    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(random.uniform(2, 3))

    for i, tweet_data in enumerate(approved_replies):
        tweet_url = tweet_data.get('tweet_url')
        generated_reply = tweet_data.get('generated_reply')
        tweet_id = tweet_data.get('tweet_id')

        if not tweet_url or not generated_reply or not tweet_id:
            _log(f"Skipping invalid entry in schedule: {tweet_data}", verbose, is_error=False)
            failed += 1
            continue

        found_tweet_element = None
        scroll_attempts = 0
        max_scroll_attempts = 30

        while found_tweet_element is None and scroll_attempts < max_scroll_attempts:
            try:
                _log(f"Searching for tweet ID: {tweet_id} on home feed (scroll attempt {scroll_attempts + 1}/{max_scroll_attempts})...", verbose)

                tweet_link_element = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f'article[role="article"][data-testid="tweet"] a[href*="/status/{tweet_id}"]'))
                )
                found_tweet_element = tweet_link_element.find_element(By.XPATH, './ancestor::article[@role="article"]')
                
                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", found_tweet_element)
                time.sleep(random.uniform(1, 2))
                
            except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                _log(f"Tweet ID {tweet_id} not visible or stale ({e}). Scrolling down to load more content...", verbose)
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                scroll_attempts += 1

        if found_tweet_element is None:
            _log(f"Could not find tweet with ID {tweet_id} on home feed after {max_scroll_attempts} scrolls. Skipping.", verbose, is_error=False)
            failed += 1
            tweet_data['status'] = 'tweet_not_found'
            with open(schedule_path, 'w') as f:
                json.dump(items, f, indent=2)
            continue

        try:
            _log(f"Found tweet ID: {tweet_id}. Attempting to post reply.", verbose)
            
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
                _log(f"Successfully liked tweet {tweet_id}.", verbose, is_error=False)
                time.sleep(random.uniform(1, 2))
            except Exception as like_e:
                _log(f"Could not like tweet {tweet_id}: {like_e}", verbose, is_error=False)

            _log(f"Successfully posted reply to {tweet_url}", verbose, is_error=False)
            posted += 1
            tweet_data['status'] = 'posted'
            save_posted_reply_to_replied_tweets_sheet(service, profile_name, tweet_data, verbose=verbose)

        except Exception as e:
            _log(f"Failed to post reply to {tweet_url}: {e}", verbose, is_error=True)
            failed += 1
            tweet_data['status'] = 'post_failed'
        
        with open(schedule_path, 'w') as f:
            json.dump(items, f, indent=2)

        driver.execute_script("window.scrollBy(0, window.innerHeight * 0.3);")
        time.sleep(random.uniform(1, 2))

    return {"processed": len(approved_replies), "posted": posted, "failed": failed}

def run_action_mode_with_review(profile_name: str, custom_prompt: str, max_tweets: int = 10, status=None, api_key: str = None, ignore_video_tweets: bool = False, run_number: int = 1, community_name: Optional[str] = None, post_via_api: bool = False, specific_search_url: Optional[str] = None, target_profile_name: Optional[str] = None, verbose: bool = False, headless: bool = True) -> Any:
    user_data_dir = get_browser_data_dir(profile_name)
    schedule_folder = _ensure_action_mode_folder(profile_name)
    setup_messages = []
    
    _log(f"Action Mode With Review: user_data_dir is {user_data_dir}", verbose, status)

    try:
        driver, messages_from_driver = setup_driver(user_data_dir, profile=profile_name, headless=headless)
        setup_messages.extend(messages_from_driver)
        _log(f"Messages from driver setup: {messages_from_driver}", verbose, status)
        for msg in setup_messages:
            _log(msg, verbose, status)
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        _log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True)
        _log(f"WebDriver setup messages: {setup_messages}", verbose, status, is_error=True)
        return None

    if specific_search_url:
        driver.get(specific_search_url)
        _log(f"Navigated to specific search URL: {specific_search_url}", verbose, status)
    else:
        driver.get("https://x.com/home")
        _log("Navigated to x.com/home...", verbose, status)
    time.sleep(5)

    if community_name:
        _navigate_to_community(driver, community_name, verbose)

    raw_containers: List[Dict[str, Any]] = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    if status:
        status.update("Starting tweet collection (Action Mode with review)...")

    last_new_content_time = time.time()

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count
            )
            if new_tweets_in_pass > 0:
                last_new_content_time = time.time()

            if time.time() - last_new_content_time > 10:
                _log("No new content for 10 seconds. Forcing a scroll.", verbose, status, is_error=False)
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                time.sleep(random.uniform(2, 4))
                last_new_content_time = time.time()
                no_new_content_count = 0

            if status:
                status.update(f"Collecting tweets: {len(processed_tweet_ids)} collected...")
            time.sleep(1)
    except KeyboardInterrupt:
        _log("Collection stopped manually.", verbose, status)

    if not raw_containers:
        _log("No tweets found during collection.", verbose, status)
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
    
    service = get_google_sheets_service(verbose=verbose, status=status)
    all_replies = []
    if service:
        try:
            profile_suffix = profile_name
            reply_sheet_name = f"{sanitize_sheet_name(profile_suffix)}_replied_tweets"
            all_replies = get_generated_replies(service, reply_sheet_name, verbose=verbose, status=status)
            if verbose:
                _log(f"Fetched {len(all_replies)} approved replies from sheet for review.", verbose, status)
        except Exception as e:
            _log(f"Error fetching generated replies for {profile_name}: {e}", verbose, status, is_error=True)
            all_replies = []

    enriched_items: List[Dict[str, Any]] = []
    for td in processed_tweets:
        media_abs_paths = _prepare_media_for_gemini_action_mode(td, profile_name, schedule_folder, is_online_mode=False, ignore_video_tweets=ignore_video_tweets, verbose=verbose)
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
                _log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True)
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
                reply_text = future.result()
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
                    'media_files': td.get('media_urls', ''),
                    'generated_reply': reply_text,
                    'profile': target_profile_name if target_profile_name else profile_name,
                    'status': 'ready_for_approval',
                    'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'run_number': run_number,
                    'profile_image_url': td.get('profile_image_url', ''),
                    'bookmarks': td.get('bookmarks', '') 
                }
                results.append(record)
            except Exception as e:
                td = item['tweet_data']
                _log(f"Error generating analysis for tweet {td.get('tweet_id')}: {str(e)}", verbose, status, is_error=True)
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

    schedule_path = get_action_schedule_file_path(profile_name)
    try:
        with open(schedule_path, 'w') as f:
            json.dump(results, f, indent=2)
        _log(f"Saved Action Mode approval file: {schedule_path}", verbose)
    except Exception as e:
        _log(f"Failed to save schedule file: {e}", verbose, is_error=True)

    try:
        html_path = build_action_mode_schedule_html(profile_name)
        if html_path:
            _log(f"Action Mode Review HTML ready: {html_path}", verbose)
    except Exception as e:
        _log(f"Failed to generate Action Mode review HTML: {e}", verbose, is_error=False)
    
    return driver

def run_action_mode(profile_name, custom_prompt, max_tweets=20, status=None, ignore_video_tweets: bool = False, run_number: int = 1, community_name: Optional[str] = None, post_via_api: bool = False, specific_search_url: Optional[str] = None, target_profile_name: Optional[str] = None, verbose: bool = False, headless: bool = True):
    user_data_dir = get_browser_data_dir(profile_name)
    setup_messages = [] 
    
    _log(f"Action Mode: user_data_dir is {user_data_dir}", verbose, status)

    try:
        driver, messages_from_driver = setup_driver(user_data_dir, profile=profile_name, headless=headless)
        setup_messages.extend(messages_from_driver)
        _log(f"Messages from driver setup: {messages_from_driver}", verbose, status)
        for msg in setup_messages:
            _log(msg, verbose, status)
            
    except Exception as e:
        _log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True)
        return

    if specific_search_url:
        driver.get(specific_search_url)
        _log(f"Navigated to specific search URL: {specific_search_url}", verbose, status)
    else:
        driver.get("https://x.com/home")
        _log("Navigated to x.com/home...", verbose, status)
    time.sleep(5)

    if community_name:
        _navigate_to_community(driver, community_name, verbose)

    sheets_service = get_google_sheets_service(verbose=verbose, status=status)
    all_replies = []
    if sheets_service:
        try:
            profile_suffix = profile_name
            reply_sheet_name = f"{sanitize_sheet_name(profile_suffix)}_replied_tweets"
            all_replies = get_generated_replies(sheets_service, reply_sheet_name, verbose=verbose, status=status)
        except Exception as e:
            _log(f"Error fetching generated replies for {profile_name}: {e}", verbose, status, is_error=True)
            all_replies = []

    results = []

    while True:
        raw_containers = []
        processed_tweet_ids = set()
        no_new_content_count = 0
        max_retries = 5
        scroll_count = 0
        if status:
            status.update("Starting tweet collection...")
        
        last_new_content_time = time.time()

        try:
            while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
                no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count)

                if new_tweets_in_pass > 0:
                    last_new_content_time = time.time()

                if time.time() - last_new_content_time > 10:
                    _log("No new content for 10 seconds. Forcing a scroll.", verbose, status, is_error=False)
                    driver.execute_script("window.scrollBy(0, window.innerHeight * 0.8);")
                    time.sleep(random.uniform(2, 4))
                    last_new_content_time = time.time()
                    no_new_content_count = 0

                if status:
                    status.update(f"Collecting tweets: {len(processed_tweet_ids)} collected...")
                
                if scroll_count % 5 == 0 and scroll_count > 0:
                    if status:
                        status.update(f"Performing extra scroll at scroll_count={scroll_count} ({len(processed_tweet_ids)} tweets collected)")
                    else:
                        _log(f"Performing extra scroll at scroll_count={scroll_count}", verbose)
                        
                    driver.execute_script(f"window.scrollTo(0, {driver.execute_script('return window.pageYOffset') - driver.execute_script('return window.innerHeight') * 0.2})")
                    time.sleep(0.2)
                    driver.execute_script(f"window.scrollTo(0, {driver.execute_script('return window.pageYOffset') + driver.execute_script('return window.innerHeight') * 0.2})")

                scroll_count += 1
                if len(processed_tweet_ids) >= max_tweets:
                    if status:
                        status.update(f"Reached target tweet count ({len(processed_tweet_ids)})!")
                    break
                if no_new_content_count >= max_retries:
                    if status:
                        status.update("No new content after multiple attempts, stopping collection.")
                    break

                time.sleep(1)
                
        except KeyboardInterrupt:
            if status:
                status.update(f"Collection stopped manually.")

        if not raw_containers:
            if status:
                status.update("No tweets found after collection! Waiting for user input...")
            else:
                _log("No tweets found after collection! Waiting for user input...", verbose)
            continue_action = input("Press Enter to try again or type 'no' to exit: ").lower()
            if continue_action == 'yes' or continue_action == '':
                driver.get("https://x.com/home")
                time.sleep(5)
                continue
            else:
                break
            
        processed_tweets_data = []
        if status:
            status.update(f"Processing collected tweets ({len(raw_containers)} raw containers)...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for container in raw_containers[:max_tweets]:
                future = executor.submit(process_container, container, {'name': profile_name})
                futures.append(future)

            for future in futures:
                tweet_data = future.result()
                if tweet_data:
                    tweet_data['name'] = profile_name
                    processed_tweets_data.append(tweet_data)

        if status:
            status.update(f"Successfully processed {len(processed_tweets_data)} tweets for generation.\n")

        tweets_with_replies = []
        api_pool = APIKeyPool()
        rate_limiter = RateLimiter()
        
        gemini_args = []
        if status:
            status.update("Preparing Gemini arguments for tweet replies...")

        for tweet_data in processed_tweets_data:
            tweet_text = tweet_data['tweet_text']
            raw_media_urls = tweet_data['media_urls']
            
            media_urls_for_gemini = _prepare_media_for_gemini_action_mode(tweet_data, profile_name, "", is_online_mode=False, ignore_video_tweets=ignore_video_tweets, verbose=verbose)
            
            if media_urls_for_gemini:
                gemini_args.append((tweet_text, media_urls_for_gemini, profile_name, api_pool.get_key(), rate_limiter, custom_prompt, tweet_data['tweet_id'], all_replies))
            else:
                _log(f"No valid media found for tweet {tweet_data['tweet_id']}, skipping media attachment.", verbose, is_error=False)
                gemini_args.append((tweet_text, [], profile_name, api_pool.get_key(), rate_limiter, custom_prompt, tweet_data['tweet_id'], all_replies))

        with ThreadPoolExecutor(max_workers=5) as executor:

            future_map = {}
            for i, args in enumerate(gemini_args):
                if args[3]:
                    future = executor.submit(_generate_with_pool, api_pool, args, status, verbose)
                    future_map[future] = (processed_tweets_data[i], args)
                else:
                    _log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True)
                    tweets_with_replies.append({
                        "tweet_text": processed_tweets_data[i]['tweet_text'],
                        "generated_reply": "",
                        "status": "no_api_key",
                        "tweet_url": processed_tweets_data[i]['tweet_url'],
                        "run_number": run_number,
                        'profile_image_url': processed_tweets_data[i].get('profile_image_url', ''), 
                        'likes': processed_tweets_data[i].get('likes', ''), 
                        'retweets': processed_tweets_data[i].get('retweets', ''), 
                        'replies': processed_tweets_data[i].get('replies', ''), 
                        'views': processed_tweets_data[i].get('views', ''), 
                        'bookmarks': processed_tweets_data[i].get('bookmarks', '') 
                    })
                    
            for future, (tweet_data, args) in future_map.items():
                try:
                    generated_reply = future.result()
                    tweet_data['generated_reply'] = generated_reply
                    tweet_data['run_number'] = run_number
                    tweets_with_replies.append(tweet_data)
                except Exception as e:
                    _log(f"Error generating reply for tweet {tweet_data['tweet_text'][:50]}...: {str(e)}", verbose, status, is_error=True)
                    tweet_data['generated_reply'] = f"Error: {str(e)}"
                    tweet_data['run_number'] = run_number
                    tweets_with_replies.append(tweet_data)

        _log(f"Successfully generated replies for {len(tweets_with_replies)} tweets.\n", verbose)
        
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(1) 
        
        if post_via_api:
            if status:
                status.update("Starting API posting for generated replies...")
        else:
            if status:
                status.update("Starting browser interaction for generated replies...")

        for i, tweet_data in enumerate(tweets_with_replies):
            tweet_text = tweet_data['tweet_text']
            generated_reply = tweet_data['generated_reply']
            tweet_url = tweet_data['tweet_url']
            tweet_id = tweet_data['tweet_id'] 

            if tweet_data.get('status') == "no_api_key":
                _log(f"Skipping tweet {tweet_url} due to no API key.", verbose, is_error=False)
                results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "no_api_key", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                continue
            
            if not generated_reply or "Error generating reply" in generated_reply:
                _log(f"Skipping tweet {tweet_url} as reply generation failed.", verbose, is_error=False)
                results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "reply_generation_failed", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                continue

            if post_via_api:
                safe_reply = filter_bmp(generated_reply)
                _log(f"Posting reply via API to tweet {tweet_id}: '{safe_reply[:80]}...'", verbose)
                
                if status:
                    status.update(f"Posting reply {i+1}/{len(tweets_with_replies)} via API...")
                
                success = post_tweet_reply(tweet_id, safe_reply, profile_name=profile_name)
                if success:
                    _log(f"Successfully posted reply to {tweet_url} via API", verbose, is_error=False)
                    results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "posted_via_api", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                else:
                    _log(f"Failed to post reply to {tweet_url} via API", verbose, is_error=True)
                    results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "api_post_failed", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                
                time.sleep(2);
            else:
                safe_reply = filter_bmp(generated_reply)
                pyperclip.copy(safe_reply)
                _log("Reply copied to clipboard. Click into the reply box, paste (Ctrl+V), edit if you wish, then post.", verbose)

                article = None
                try:
                    link_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, f'a[href*="/status/{tweet_id}"]'))
                    )
                    article = link_element.find_element(By.XPATH, './ancestor::article[@role="article"]')
                except Exception as e:
                    _log(f"Tweet with ID {tweet_id} (URL: {tweet_url}) not found on current page right before interaction. Skipping browser interaction. Error: {str(e)}", verbose, is_error=False)
                    results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "tweet_not_on_page_for_interaction", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                    continue

                try:
                    reply_button = WebDriverWait(article, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="reply"]'))
                    )
                    if status:
                        status.update(f"Clicked reply button for tweet {i+1}/{len(tweets_with_replies)}.")
                    try:
                        reply_button.click()
                    except:
                        driver.execute_script("arguments[0].click();", reply_button)
                    time.sleep(2)

                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
                    )
                    if status:
                        status.update("Reply box opened. Waiting for user to paste/edit/post and close the dialog.")
                    _log("Reply box opened. Waiting for user to paste/edit/post and close the dialog.", verbose)

                    dialog_closed = False
                    start_wait_time = time.time()
                    max_dialog_wait_time = 300 
                    while time.time() - start_wait_time < max_dialog_wait_time:
                        current_url = driver.current_url
                        if "x.com/compose/post" in current_url:
                            time.sleep(1) 
                        elif "x.com/home" in current_url:
                            dialog_closed = True
                            _log("Reply box closed. Moving to next tweet...", verbose)
                            break
                        else:
                            dialog_closed = True
                            _log(f"Unexpected URL ({current_url}), assuming reply box closed. Moving to next tweet...", verbose, is_error=False)
                            break
                    
                    if not dialog_closed:
                        _log(f"Reply dialog for tweet {tweet_url} did not close within {max_dialog_wait_time} seconds. Proceeding to next tweet.", verbose, is_error=False)
                        results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "dialog_timeout", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                        continue 

                    results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "posted_or_closed", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})

                except Exception as e:
                    _log(f"Error during browser interaction for tweet {tweet_url}: {str(e)}", verbose, is_error=True)
                    results.append({"tweet_text": tweet_text, "generated_reply": generated_reply, "status": "browser_interaction_failed", 'profile_image_url': tweet_data.get('profile_image_url', ''), 'likes': tweet_data.get('likes', ''), 'retweets': tweet_data.get('retweets', ''), 'replies': tweet_data.get('replies', ''), 'views': tweet_data.get('views', ''), 'bookmarks': tweet_data.get('bookmarks', '')})
                    continue 

                if status:
                    status.update("Moving to next tweet...")
                else:
                    _log("Moving to next tweet...", verbose)
                time.sleep(2)

            if post_via_api:
                _log(f"\nAction mode finished. Posted {len([r for r in results if r.get('status') == 'posted_via_api'])} replies via API.", verbose)
                break
            else:
                posted_count = len([r for r in results if r.get('status') in ['posted_or_closed', 'posted']])
                failed_count = len([r for r in results if r.get('status') not in ['posted_or_closed', 'posted', 'no_api_key', 'reply_generation_failed'] ])
                if status:
                    status.update(f"Action mode finished. Posted: {posted_count}, Failed: {failed_count}. Waiting for user input...")
                _log(f"Action mode finished. Posted: {posted_count}, Failed: {failed_count}.", verbose)
                continue_action = input("\nPress Enter to process more tweets or type 'no' to exit: ").lower()
                if continue_action == 'yes' or continue_action == '':
                    if status:
                        status.update("User chose to process more tweets. Navigating to home...")
                    driver.get("https://x.com/home")
                    time.sleep(5)
                else:
                    if status:
                        status.update("Action mode finished. Browser will remain open.")
                    else:
                        _log("Action mode finished. Browser will remain open.", verbose)
                    break
        return results