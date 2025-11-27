import os
import re
import json
import time

from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from typing import List, Dict, Any, Optional
from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir
from services.support.path_config import get_youtube_profile_dir

console = Console()

def _ensure_scrape_folder(profile_name: str) -> str:
    base_dir = get_youtube_profile_dir(profile_name)
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

def _save_scraped_videos(profile_name: str, videos_data: List[Dict[str, Any]], weekly: bool, today: bool, verbose: bool = False) -> None:
    scrape_folder = _ensure_scrape_folder(profile_name)
    
    current_date = datetime.now().strftime('%Y%m%d')
    output_filename = f"videos_{current_date}.json"
    if weekly:
        output_filename = f"videos_weekly_{current_date}.json"
    elif today:
        output_filename = f"videos_daily_{current_date}.json"

    output_path = os.path.join(scrape_folder, output_filename)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(videos_data, f, indent=2, ensure_ascii=False)
        log(f"Saved {len(videos_data)} videos to {output_path}", verbose, log_caller_file="scraper_utils.py")
    except Exception as e:
        log(f"Error saving videos to {output_path}: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")

def _extract_video_data(video_element, verbose: bool = False) -> Optional[Dict[str, Any]]:
    try:
        video_data = {}

        title_element = video_element.find_element(By.CSS_SELECTOR, '#video-title')
        video_data['title'] = title_element.get_attribute('title')
        video_data['url'] = title_element.get_attribute('href')

        video_id = ''
        if video_data['url'] and 'watch?v=' in video_data['url']:
            video_id = video_data['url'].split('/watch?v=')[1].split('&')[0]
        video_data['video_id'] = video_id

        video_data['video_length'] = ''
        try:
            badge_shape_element = video_element.find_element(By.CSS_SELECTOR, 'ytd-thumbnail-overlay-time-status-renderer badge-shape')
            aria_label = badge_shape_element.get_attribute('aria-label')
            if aria_label:
                minutes_match = re.search(r'(\d+)\s+minute', aria_label)
                seconds_match = re.search(r'(\d+)\s+second', aria_label)
                
                minutes = minutes_match.group(1) if minutes_match else '0'
                seconds = seconds_match.group(1) if seconds_match else '0'
                
                video_data['video_length'] = f"{int(minutes):02}:{int(seconds):02}"
        except Exception:
            pass

        published = ''
        views = ''
        try:
            metadata_line_elements = video_element.find_elements(By.CSS_SELECTOR, '#metadata-line span.inline-metadata-item')
            for item in metadata_line_elements:
                text = item.text.lower()
                if 'ago' in text:
                    published = item.text
                elif 'views' in text:
                    views = item.text.replace(' views', '').strip().replace(',', '')
        except Exception:
            pass
        video_data['published'] = published
        video_data['views'] = views

        try:
            channel_name_element = video_element.find_element(By.CSS_SELECTOR, '#channel-name yt-formatted-string a')
            video_data['channel_name'] = channel_name_element.text.strip()
            video_data['channel_url'] = channel_name_element.get_attribute('href')
        except Exception:
            video_data['channel_name'] = ''
            video_data['channel_url'] = ''

        try:
            thumbnail = video_element.find_element(By.CSS_SELECTOR, '#thumbnail img')
            video_data['thumbnail_url'] = thumbnail.get_attribute('src')
        except Exception:
            video_data['thumbnail_url'] = ''
            
        video_data['scraped_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return video_data
    except Exception as e:
        log(f"Error extracting video data: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
        return None

def _scroll_page(driver, verbose: bool = False):
    last_height = driver.execute_script("return document.documentElement.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 10
    while scroll_attempts < max_scroll_attempts:
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.documentElement.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_attempts += 1
    log(f"Scrolled {scroll_attempts} times.", verbose, log_caller_file="scraper_utils.py")


def run_youtube_scraper(profile_name: str, search_query: Optional[str] = None, max_videos: int = 50, weekly_filter: bool = False, today_filter: bool = False, status=None, verbose: bool = False, headless: bool = True) -> List[Dict[str, Any]]:
    user_data_dir = get_browser_data_dir(profile_name)
    
    try:
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless)
        for msg in setup_messages:
            log(msg, verbose, log_caller_file="scraper_utils.py")
        if status:
            status.update("[white]WebDriver setup complete.[/white]")
    except Exception as e:
        log(f"Error setting up WebDriver: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
        return []

    videos_data: List[Dict[str, Any]] = []
    video_ids_seen = set()

    try:
        if status:
            status.update(f"[white]Navigating to YouTube...[/white]")
        
        if search_query:
            base_search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
            if weekly_filter:
                search_url = f"{base_search_url}&sp=EgIIAw%253D%253D"
            elif today_filter:
                search_url = f"{base_search_url}&sp=EgQIAhAB"
            else:
                search_url = f"{base_search_url}&sp=EgIIAw%253D%253D"
            driver.get(search_url)
            log(f"Searching YouTube for: '{search_query}' with filter: {'Weekly' if weekly_filter else ('Today' if today_filter else 'None')}", verbose, log_caller_file="scraper_utils.py")
        else:
            driver.get("https://www.youtube.com/feed/trending")
            log("Scraping trending videos on YouTube.", verbose, log_caller_file="scraper_utils.py")
        
        time.sleep(3)

        current_videos_count = 0
        while current_videos_count < max_videos:
            if status:
                status.update(f"[white]Scraped {current_videos_count}/{max_videos} videos... Scrolling...[/white]")
            
            _scroll_page(driver, verbose)
            
            video_elements = driver.find_elements(By.CSS_SELECTOR, 'ytd-video-renderer, ytd-compact-video-renderer, ytd-grid-video-renderer, ytd-rich-grid-media')
            
            new_videos_found = 0
            for element in video_elements:
                if len(videos_data) >= max_videos:
                    break
                
                extracted_data = _extract_video_data(element, verbose)
                if extracted_data and extracted_data.get('video_id') and extracted_data['video_id'] not in video_ids_seen:
                    videos_data.append(extracted_data)
                    video_ids_seen.add(extracted_data['video_id'])
                    new_videos_found += 1
            
            current_videos_count = len(videos_data)
            if new_videos_found == 0 and current_videos_count > 0:
                log("No new videos loaded after scroll. Stopping collection.", verbose, log_caller_file="scraper_utils.py")
                break
            elif new_videos_found == 0 and current_videos_count == 0 and search_query:
                log("No videos found for the given search query. Consider a different query.", verbose, log_caller_file="scraper_utils.py")
                break
            elif new_videos_found == 0 and current_videos_count == 0 and not search_query:
                log("No trending videos found. YouTube page might be empty or layout changed.", verbose, log_caller_file="scraper_utils.py")
                break

            time.sleep(1)

    except Exception as e:
        log(f"Error during YouTube scraping: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        _save_scraped_videos(profile_name, videos_data, weekly_filter, today_filter, verbose)
    
    return videos_data 