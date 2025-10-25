import re
import os
import time

from pathlib import Path
from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from typing import List, Dict, Any, Optional
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir
from selenium.webdriver.support import expected_conditions as EC
from services.support.path_config import get_youtube_captions_dir

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if status and (is_error or verbose):
        status.stop()

    log_message = message
    if is_error:
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
        console.print(f"[caption_downloader.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[caption_downloader.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def scrape_caption_from_subtitle_to(driver, video_url: str, profile_name: str, verbose: bool = False) -> Dict[str, Any]:
    video_id = "unknown"
    if 'youtube.com' in video_url:
        video_id = video_url.split('v=')[-1].split('&')[0]
    elif 'youtu.be' in video_url:
        video_id = video_url.split('/')[-1].split('?')[0]
        
    subtitle_to_url = f"https://subtitle.to/{video_url}"
    
    _log(f"Accessing subtitle.to for video {video_id}", verbose)
    try:
        driver.get(subtitle_to_url)
    except Exception as e:
        _log(f"Error loading page: {e}", verbose, is_error=True)
        return {
            "success": False,
            "error": str(e),
            "video_id": video_id
        }
    
    time.sleep(3)
    
    try:
        wait = WebDriverWait(driver, 15)
        
        selectors = [
            'button.download-button[data-title="[TXT] English"]',
            'button.download-button',
            '.subtitle-download-btn',
            '.download-button'
        ]
        
        download_button = None
        for selector in selectors:
            try:
                download_button = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if download_button:
                    _log(f"Found download button with selector: {selector}", verbose)
                    break
            except TimeoutException:
                continue
        
        if not download_button:
            return {
                "success": False,
                "error": "Download button not found",
                "video_id": video_id
            }
        
        download_button.click()
        
        start_time = time.time()
        downloaded_file = None
        captions_dir = get_youtube_captions_dir(profile_name)
        
        while time.time() - start_time < 30:
            downloaded_files = [f for f in os.listdir(captions_dir) if f.startswith("[English]") and f.endswith("[DownSub.com].txt")]
            
            if downloaded_files:
                downloaded_file = max([os.path.join(captions_dir, f) for f in downloaded_files], key=os.path.getctime)
                break
            
            time.sleep(0.5)
        
        if downloaded_file:
            return {
                "success": True,
                "filename": downloaded_file,
                "video_id": video_id
            }
        else:
            return {
                "success": False,
                "error": "Download timed out after 30 seconds",
                "video_id": video_id
            }
            
    except Exception as inner_e:
        _log(f"Error during caption extraction: {inner_e}", verbose, is_error=True)
        return {
            "success": False,
            "error": str(inner_e),
            "video_id": video_id
        }
        
def download_captions_for_videos(profile_name: str, videos_data: List[Dict[str, Any]], verbose: bool = False, headless: bool = True) -> Dict[str, Any]:
    results = {
        "success": [],
        "failed": []
    }
    
    total_videos = len(videos_data)
    _log(f"Starting to download captions for {total_videos} videos for profile '{profile_name}'", verbose)
    
    driver = None
    try:
        download_dir = get_youtube_captions_dir(profile_name)
        Path(download_dir).mkdir(parents=True, exist_ok=True)
        
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }

        additional_arguments = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-notifications',
            '--disable-popup-blocking',
            '--disable-extensions',
            '--disable-infobars',
            '--log-level=3',
            '--disable-logging',
            '--disable-login-animations',
            '--disable-prompts',
            '--disable-web-security',
            '--disable-translate',
            '--disable-features=TranslateUI',
            '--disable-features=GlobalMediaControls',
            '--disable-client-side-phishing-detection',
        ]

        user_data_dir = get_browser_data_dir("Download")

        driver, setup_messages = setup_driver(
            user_data_dir=user_data_dir,
            profile=profile_name,
            headless=headless,
            prefs=prefs,
            additional_arguments=additional_arguments
        )
        for msg in setup_messages:
            _log(msg, verbose)
            
        for i, video in enumerate(videos_data):
            video_url = video.get('url')
            if not video_url:
                _log(f"No URL found for video {i+1}/{total_videos}. Skipping.", verbose)
                results["failed"].append({
                    "video_id": video.get("video_id", "Unknown"),
                    "title": video.get("title", "Unknown Title"),
                    "reason": "No URL provided"
                })
                continue
                
            video_title = video.get("title", "Unknown Title")
            _log(f"Processing video {i+1}/{total_videos}: {video_title}", verbose)
            
            try:
                result = scrape_caption_from_subtitle_to(driver, video_url, profile_name, verbose)
                if result.get("success", False):
                    results["success"].append({
                        "video_id": result["video_id"],
                        "title": video_title,
                        "filename": result["filename"]
                    })
                    _log(f"Successfully downloaded captions for: {video_title}", verbose)
                else:
                    results["failed"].append({
                        "video_id": result.get("video_id", video.get("video_id", "Unknown")),
                        "title": video_title,
                        "reason": result.get("error", "Unknown error")
                    })
                    _log(f"Failed to download captions for: {video_title} - {result.get('error', 'Unknown error')}", verbose, is_error=True)
            except Exception as e:
                _log(f"Unexpected error for video {video_title}: {e}", verbose, is_error=True)
                results["failed"].append({
                    "video_id": video.get("video_id", "Unknown"),
                    "title": video_title,
                    "reason": str(e)
                })
                
            time.sleep(2)
            
    except Exception as e:
        _log(f"Error setting up driver for caption download: {e}", verbose, is_error=True)
        results["failed"].append({"video_id": "N/A", "title": "Driver Setup", "reason": str(e)})
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    _log(f"Completed caption download. Success: {len(results['success'])}, Failed: {len(results['failed'])}", verbose)
    return results 