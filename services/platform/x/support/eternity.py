import re
import os
import json
import time
import shutil

from profiles import PROFILES

from rich.console import Console
from typing import List, Dict, Any
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from services.support.image_download import download_images
from services.support.web_driver_handler import setup_driver
from selenium.webdriver.support import expected_conditions as EC
from services.support.video_download import download_twitter_videos
from services.platform.x.support.process_container import process_container
from services.platform.x.support.eternity_html import build_eternity_schedule_html
from services.platform.x.support.generate_reply_with_key import generate_reply_with_key
from services.support.path_config import get_browser_data_dir, get_eternity_dir, get_eternity_schedule_file_path, ensure_dir_exists



console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False):
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
        console.print(f"[eternity.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif status:
        status.update(message)


def _ensure_eternity_folder(profile_name: str) -> str:
    base_dir = get_eternity_dir(profile_name)
    return ensure_dir_exists(base_dir)


def _copy_media_into_eternity(media_paths: List[str], eternity_folder: str, verbose: bool = False) -> List[str]:
    saved_abs_paths: List[str] = []
    for path in media_paths:
        if not path:
            continue
        try:
            filename = os.path.basename(path)
            target_path = os.path.join(eternity_folder, filename)
            if os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                suffix_idx = 1
                while os.path.exists(target_path):
                    filename = f"{name}_{suffix_idx}{ext}"
                    target_path = os.path.join(eternity_folder, filename)
                    suffix_idx += 1
            shutil.copy2(path, target_path)
            saved_abs_paths.append(os.path.abspath(target_path))
        except Exception as e:
            _log(f"Error copying media {path} into eternity folder: {e}", verbose, is_error=True)
    return saved_abs_paths


def _prepare_media_for_gemini(tweet_data: Dict[str, Any], profile_name: str, eternity_folder: str, verbose: bool = False) -> List[str]:
    media_abs_paths_for_gemini: List[str] = []
    raw_media_urls = tweet_data.get('media_urls')

    if raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
        try:
            video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True, verbose=verbose)
            if video_path:
                copied = _copy_media_into_eternity([video_path], eternity_folder, verbose)
                media_abs_paths_for_gemini.extend(copied)
            else:
                _log(f"Video download failed or returned no path for {tweet_data['tweet_id']}", verbose, is_error=False)
        except Exception as e:
            _log(f"Error handling video for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)
    elif raw_media_urls:
        try:
            image_urls = [u.strip() for u in str(raw_media_urls).split(';') if u and u.strip()]
            if image_urls:
                downloaded_images = download_images(image_urls, profile_name, verbose)
                copied = _copy_media_into_eternity(downloaded_images, eternity_folder, verbose)
                media_abs_paths_for_gemini.extend(copied)
        except Exception as e:
            _log(f"Error handling images for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)

    return media_abs_paths_for_gemini


def _get_tweets_from_profile_page(driver, profile_url: str, max_tweets_to_collect: int = 10, days_back_limit: int = 2, verbose: bool = False) -> List[Dict[str, Any]]:
    _log(f"Navigating to profile: {profile_url}", verbose)
    driver.get(profile_url)
    time.sleep(5)

    collected_tweets: List[Dict[str, Any]] = []
    processed_tweet_ids = set()
    scroll_attempts = 0
    MAX_SCROLL_ATTEMPTS = 3
    TWO_DAYS_AGO = datetime.now() - timedelta(days=days_back_limit)

    current_max_scroll_attempts = MAX_SCROLL_ATTEMPTS if max_tweets_to_collect > 0 else 50

    while (max_tweets_to_collect == 0 or len(collected_tweets) < max_tweets_to_collect) and scroll_attempts < current_max_scroll_attempts:
        current_height = driver.execute_script("return document.body.scrollHeight")
        containers = driver.find_elements(By.CSS_SELECTOR, 'article[role="article"][data-testid="tweet"]')
        new_found_in_pass = 0

        for container in containers:
            try:
                tweet_url_elem = WebDriverWait(container, 1).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="/status/"]'))
                )
                tweet_url = tweet_url_elem.get_attribute('href')
                tweet_id = tweet_url.split('/status/')[1].split('/')[0]
                
                if tweet_id in processed_tweet_ids:
                    continue

                raw_container_data = {
                    'html': container.get_attribute('outerHTML'),
                    'text': container.text,
                    'url': tweet_url,
                    'tweet_id': tweet_id
                }
                tweet_data = process_container(raw_container_data, {}, verbose=verbose)

                if tweet_data:
                    tweet_date_obj = datetime.strptime(tweet_data['tweet_date'], '%Y-%m-%d %H:%M:%S')
                    if tweet_date_obj >= TWO_DAYS_AGO:
                        collected_tweets.append(tweet_data)
                        processed_tweet_ids.add(tweet_id)
                        new_found_in_pass += 1
                        if max_tweets_to_collect > 0 and len(collected_tweets) >= max_tweets_to_collect:
                            break
            except TimeoutException:
                continue
            except Exception as e:
                _log(f"Error processing container on profile page: {e}", verbose, is_error=False)
                continue
        
        if max_tweets_to_collect > 0 and len(collected_tweets) >= max_tweets_to_collect:
            break

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts += 1

        if new_found_in_pass == 0 and new_height == current_height and scroll_attempts > 5:
            _log("No new content found or unable to scroll further, stopping collection on this profile.", verbose, is_error=False)
            break

    _log(f"Collected {len(collected_tweets)} recent tweets from {profile_url}", verbose)
    return collected_tweets[:max_tweets_to_collect] if max_tweets_to_collect > 0 else collected_tweets


def run_eternity_mode(profile_name: str, custom_prompt: str, eternity_browser_profile: str, max_tweets: int = 10, days_back: int = 2, status=None, verbose: bool = False, headless: bool = True) -> List[Dict[str, Any]]:
    
    browser_profile_name = eternity_browser_profile or profile_name
    user_data_dir = get_browser_data_dir(browser_profile_name)
    eternity_folder = _ensure_eternity_folder(profile_name)

    try:
        driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile_name, verbose=verbose, headless=headless)
        for msg in setup_messages:
            _log(msg, verbose, status)
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        _log(f"Error setting up WebDriver for {browser_profile_name}: {e}", verbose, status, is_error=True)
        return []

    all_collected_tweets: List[Dict[str, Any]] = []
    if profile_name not in PROFILES or not PROFILES[profile_name].get("target_profiles"):
        _log(f"Profile '{profile_name}' has no target_profiles defined. Skipping eternity mode.", verbose, is_error=False)
        driver.quit()
        return []

    target_profile_urls = PROFILES[profile_name]["target_profiles"]
    if status:
        status.update(f"[white]Scraping {len(target_profile_urls)} target profiles for {max_tweets} tweets each from last {days_back} days...[/white]")

    for target_url in target_profile_urls:
        collected_from_current_profile = _get_tweets_from_profile_page(driver, target_url, max_tweets_to_collect=max_tweets, days_back_limit=days_back, verbose=verbose)
        all_collected_tweets.extend(collected_from_current_profile)
        if status:
            status.update(f"[white]Collected {len(all_collected_tweets)} tweets overall. Continuing...[/white]")
        if max_tweets > 0 and len(all_collected_tweets) >= max_tweets:
            all_collected_tweets = all_collected_tweets[:max_tweets]
            break
    
    if not all_collected_tweets:
        _log("No tweets found from target profiles within the specified time frame.", verbose, is_error=False)
        driver.quit()
        return []

    if status:
        status.update(f"[white]Processing collected tweets ({len(all_collected_tweets)} raw containers)...[/white]")

    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()

    enriched_items: List[Dict[str, Any]] = []
    for td in all_collected_tweets:
        media_abs_paths = _prepare_media_for_gemini(td, profile_name, eternity_folder, verbose)
        args = (td['tweet_text'], media_abs_paths, profile_name, api_pool.get_key(), rate_limiter, custom_prompt, td['tweet_id'])
        enriched_items.append({
            'tweet_data': td,
            'media_abs_paths': media_abs_paths,
            'gemini_args': args
        })

    if status:
        status.update(f"[white]Running Gemini for {len(enriched_items)} tweets...[/white]")

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {}
        for item in enriched_items:
            args = item['gemini_args']
            if args[3]:
                future = executor.submit(generate_reply_with_key, args, status)
                future_map[future] = item
            else:
                _log("No available API keys for Gemini for one of the tweets.", verbose, status, is_error=True)
                td = item['tweet_data']
                results.append({
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'tweet_date': td.get('tweet_date'),
                    'likes': td.get('likes'),
                    'retweets': td.get('retweets'),
                    'replies': td.get('replies'),
                    'views': td.get('views'),
                    'media_files': [os.path.basename(p) for p in item['media_abs_paths']],
                    'generated_reply': '',
                    'profile': profile_name,
                    'status': 'no_api_key'
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
                    'likes': td.get('likes'),
                    'retweets': td.get('retweets'),
                    'replies': td.get('replies'),
                    'views': td.get('views'),
                    'media_files': [os.path.basename(p) for p in item['media_abs_paths']],
                    'generated_reply': reply_text,
                    'profile': profile_name,
                    'status': 'ready_for_approval'
                }
                results.append(record)
            except Exception as e:
                td = item['tweet_data']
                _log(f"Error generating analysis for tweet {td.get('tweet_id')}: {str(e)}", verbose, status, is_error=True)
                results.append({
                    'tweet_id': td.get('tweet_id'),
                    'tweet_url': td.get('tweet_url'),
                    'tweet_text': td.get('tweet_text'),
                    'media_files': [os.path.basename(p) for p in item['media_abs_paths']],
                    'generated_reply': f"Error: {str(e)}",
                    'profile': profile_name,
                    'status': 'analysis_failed'
                })

    schedule_path = get_eternity_schedule_file_path(profile_name)
    try:
        with open(schedule_path, 'w') as f:
            json.dump(results, f, indent=2)
        _log(f"Saved Eternity approval file: {schedule_path}", verbose)
    except Exception as e:
        _log(f"Failed to save schedule file: {e}", verbose, is_error=True)

    try:
        html_path = build_eternity_schedule_html(profile_name, verbose=verbose)
        if html_path:
            _log(f"Eternity Review HTML ready: {html_path}", verbose)
    except Exception as e:
        _log(f"Failed to generate Eternity review HTML: {e}", verbose, is_error=False)

    try:
        driver.quit()
    except Exception:
        pass

    return results 


def clear_eternity_files(profile_name: str, status=None, verbose: bool = False) -> int:
    eternity_folder = _ensure_eternity_folder(profile_name)
    deleted = 0
    try:
        for name in os.listdir(eternity_folder):
            path = os.path.join(eternity_folder, name)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                deleted += 1
            except Exception as e:
                _log(f"Could not delete {path}: {e}", verbose, is_error=False)
        
        schedule_path = os.path.join(eternity_folder, 'schedule.json')
        with open(schedule_path, 'w') as f:
            json.dump([], f, indent=2)
        if status:
            status.update(f"[white]Cleared {deleted} items and reset {schedule_path}[/white]")
        else:
            _log(f"Cleared {deleted} items and reset {schedule_path}", verbose)
    except Exception as e:
        _log(f"Failed to clear Eternity files for {profile_name}: {e}", verbose, is_error=True)
    return deleted 