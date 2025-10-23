import re
import os
import json
import time
import shutil

from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.image_download import download_images
from services.support.web_driver_handler import setup_driver
from services.support.video_download import download_twitter_videos
from services.platform.x.support.turbin_html import build_schedule_html
from services.platform.x.support.turbin_server import start_review_server
from services.platform.x.support.process_container import process_container
from services.platform.x.support.generate_reply_with_key import generate_reply_with_key
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll
from services.support.path_config import get_browser_data_dir, get_replies_dir, get_turbin_schedule_file_path, get_review_html_path, ensure_dir_exists

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False):
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[turbin.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[turbin.py] {timestamp}|[{color}]{message}[/{color}]")
    elif status:
        status.update(message)

def _ensure_schedule_folder(profile_name: str) -> str:
    base_dir = get_replies_dir(profile_name)
    return ensure_dir_exists(base_dir)

def _copy_media_into_schedule(media_paths: List[str], schedule_folder: str, verbose: bool = False) -> List[str]:
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

def _prepare_media_for_gemini(tweet_data: Dict[str, Any], profile_name: str, schedule_folder: str, verbose: bool = False) -> List[str]:
    media_abs_paths_for_gemini: List[str] = []
    raw_media_urls = tweet_data.get('media_urls')

    if raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
        try:
            video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True, verbose=verbose)
            if video_path:
                copied = _copy_media_into_schedule([video_path], schedule_folder, verbose)
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
                copied = _copy_media_into_schedule(downloaded_images, schedule_folder, verbose)
                media_abs_paths_for_gemini.extend(copied)
        except Exception as e:
            _log(f"Error handling images for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True)

    return media_abs_paths_for_gemini

def run_turbin_mode(profile_name: str, custom_prompt: str, max_tweets: int = 10, status=None, api_key: str = None, verbose: bool = False, headless: bool = True) -> List[Dict[str, Any]]:
    user_data_dir = get_browser_data_dir(profile_name)
    schedule_folder = _ensure_schedule_folder(profile_name)

    try:
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, headless=headless)
        for msg in setup_messages:
            _log(msg, verbose, status)
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        _log(f"Error setting up WebDriver: {e}", verbose, status, is_error=True)
        _log(f"WebDriver setup messages: {setup_messages}", verbose, status, is_error=True)
        return []

    if status:
        status.update("[white]Navigating to x.com/home...[/white]")
    driver.get("https://x.com/home")
    time.sleep(5)

    raw_containers: List[Dict[str, Any]] = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    max_retries = 5
    scroll_count = 0

    if status:
        status.update("[white]Starting tweet collection (Turbin)...[/white]")

    try:
        while len(processed_tweet_ids) < max_tweets and no_new_content_count < max_retries:
            no_new_content_count, scroll_count, new_tweets_in_pass = capture_containers_and_scroll(
                driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose
            )
            if status:
                status.update(f"[white]Collecting tweets: {len(processed_tweet_ids)} collected...[/white]")
            time.sleep(1)
    except KeyboardInterrupt:
        _log("Collection stopped manually.", verbose, status)

    if not raw_containers:
        _log("No tweets found during collection.", verbose, status)
        driver.quit()
        return []

    if status:
        status.update(f"[white]Processing collected tweets ({len(raw_containers)} raw containers)...[/white]")

    processed_tweets: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_container, c, {'name': profile_name}) for c in raw_containers[:max_tweets]]
        for future in futures:
            td = future.result()
            if td:
                td['name'] = profile_name
                processed_tweets.append(td)

    if status:
        status.update(f"[white]Successfully processed {len(processed_tweets)} tweets for Gemini analysis.[/white]")

    api_pool = APIKeyPool()
    if api_key:
        api_pool.set_explicit_key(api_key)
    rate_limiter = RateLimiter()

    enriched_items: List[Dict[str, Any]] = []
    for td in processed_tweets:
        media_abs_paths = _prepare_media_for_gemini(td, profile_name, schedule_folder, verbose)
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
                    'likes': td.get('likes') / 1000,
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
                    'likes': td.get('likes') / 1000,
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

    schedule_path = get_turbin_schedule_file_path(profile_name)
    try:
        with open(schedule_path, 'w') as f:
            json.dump(results, f, indent=2)
        _log(f"Saved Turbin approval file: {schedule_path}", verbose)
    except Exception as e:
        _log(f"Failed to save schedule file: {e}", verbose, is_error=True)

    try:
        html_path = build_schedule_html(profile_name, verbose=verbose)
        if html_path:
            _log(f"Review HTML ready: {html_path}", verbose)
    except Exception as e:
        _log(f"Failed to generate review HTML: {e}", verbose, is_error=False)

    try:
        driver.quit()
    except Exception:
        pass

    return results 

def clear_turbin_files(profile_name: str, status=None, verbose: bool = False) -> int:
    deleted = 0
    try:
        schedule_folder = _ensure_schedule_folder(profile_name)
        for name in os.listdir(schedule_folder):
            path = os.path.join(schedule_folder, name)
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                deleted += 1
            except Exception as e:
                _log(f"Could not delete {path}: {e}", verbose, is_error=False)
        schedule_path = os.path.join(schedule_folder, 'schedule.json')
        with open(schedule_path, 'w') as f:
            json.dump([], f, indent=2)
        if status:
            status.update(f"[white]Cleared {deleted} items and reset {schedule_path}[/white]")
        else:
            _log(f"Cleared {deleted} items and reset {schedule_path}", verbose)
    except Exception as e:
        _log(f"Failed to clear Turbin files for {profile_name}: {e}", verbose, is_error=True)
    return deleted 

def serve_turbin_review(profile_name: str, port: int = 8765, verbose: bool = False):
    start_review_server(profile_name, port=port, verbose=verbose) 