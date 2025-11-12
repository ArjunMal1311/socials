import re
import os
import time

from pathlib import Path
from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from youtube_transcript_api.formatters import SRTFormatter
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir
from selenium.webdriver.support import expected_conditions as EC
from services.support.path_config import get_youtube_captions_dir
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from services.platform.youtube.support.youtube_api_utils import initialize_youtube_api, list_caption_tracks, download_caption_track

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False):
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
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[caption_downloader.py] {timestamp}|[{color}]{log_message}[/{color}]")
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
            "video_id": video_id,
            "caption_filepath": None
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
                "video_id": video_id,
                "caption_filepath": None
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
                "video_id": video_id,
                "caption_filepath": downloaded_file
            }
        else:
            return {
                "success": False,
                "error": "Download timed out after 30 seconds",
                "video_id": video_id,
                "caption_filepath": None
            }
            
    except Exception as inner_e:
        _log(f"Error during caption extraction: {inner_e}", verbose, is_error=True)
        return {
            "success": False,
            "error": str(inner_e),
            "video_id": video_id,
            "caption_filepath": None
        }
        
def download_captions_for_videos(profile_name: str, videos_data: List[Dict[str, Any]], verbose: bool = False, headless: bool = True, caption_method: str = "selenium") -> Dict[str, Any]:
    _log(f"Starting to download captions for {len(videos_data)} videos for profile '{profile_name}' using {caption_method} method.", verbose)

    if caption_method == "api":
        download_results = download_captions_via_api(profile_name, videos_data, verbose=verbose)
    elif caption_method == "selenium":
        
        download_results = {
            "success": [],
            "failed": []
        }

        total_videos = len(videos_data)
        _log(f"Starting to download captions for {total_videos} videos for profile '{profile_name}' via Selenium", verbose)

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
                    download_results["failed"].append({
                        "video_id": video.get("video_id", "Unknown"),
                        "title": video.get("title", "Unknown Title"),
                        "reason": "No URL provided",
                        "caption_filepath": None
                    })
                    continue

                video_title = video.get("title", "Unknown Title")
                _log(f"Processing video {i+1}/{total_videos}: {video_title}", verbose)

                try:
                    result = scrape_caption_from_subtitle_to(driver, video_url, profile_name, verbose)
                    if result.get("success", False):
                        download_results["success"].append({
                            "video_id": result["video_id"],
                            "title": video_title,
                            "filename": result["filename"],
                            "caption_filepath": result["caption_filepath"]
                        })
                        _log(f"Successfully downloaded captions for: {video_title}", verbose)
                    else:
                        download_results["failed"].append({
                            "video_id": result.get("video_id", video.get("video_id", "Unknown")),
                            "title": video_title,
                            "reason": result.get("error", "Unknown error"),
                            "caption_filepath": result.get("caption_filepath", None)
                        })
                        _log(f"Failed to download captions for: {video_title} - {result.get('error', 'Unknown error')}", verbose, is_error=True)
                except Exception as e:
                    _log(f"Unexpected error for video {video_title}: {e}", verbose, is_error=True)
                    download_results["failed"].append({
                        "video_id": video.get("video_id", "Unknown"),
                        "title": video_title,
                        "reason": str(e),
                        "caption_filepath": None
                    })

                time.sleep(2)

        except Exception as e:
            _log(f"Error setting up driver for caption download: {e}", verbose, is_error=True)
            download_results["failed"].append({"video_id": "N/A", "title": "Driver Setup", "reason": str(e), "caption_filepath": None})
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
    elif caption_method == "transcript_api":
        download_results = download_captions_via_transcript_api(profile_name, videos_data, verbose=verbose)
    else:
        _log(f"Unknown caption download method: {caption_method}", verbose, is_error=True)
        return videos_data
    
    for video in videos_data:
        video_id = video.get("video_id")
        for success_item in download_results["success"]:
            if success_item.get("video_id") == video_id and success_item.get("caption_filepath"):
                video["caption_filepath"] = success_item["caption_filepath"]
                break
        for failed_item in download_results["failed"]:
            if failed_item.get("video_id") == video_id:
                video["caption_filepath"] = None
                break

    _log(f"Completed caption download. Success: {len(download_results['success'])}, Failed: {len(download_results['failed'])}", verbose)
    return videos_data

def download_captions_via_api(profile_name: str, videos_data: List[Dict[str, Any]], verbose: bool = False) -> Dict[str, Any]:
    results = {
        "success": [],
        "failed": []
    }
    youtube_service = initialize_youtube_api(profile_name, verbose=verbose)
    if not youtube_service:
        _log("YouTube API not initialized. Cannot download captions via API.", verbose, is_error=True)
        return results

    captions_dir = get_youtube_captions_dir(profile_name)
    Path(captions_dir).mkdir(parents=True, exist_ok=True)

    for i, video in enumerate(videos_data):
        video_id = video.get("video_id")
        video_title = video.get("title", "Unknown Title")

        if not video_id:
            _log(f"No video ID found for video {i+1}. Skipping API caption download.", verbose, is_error=True)
            results["failed"].append({"video_id": "N/A", "title": video_title, "reason": "No video ID", "caption_filepath": None})
            continue

        _log(f"Listing caption tracks for video '{video_title}' ({video_id}) via API.", verbose)
        caption_tracks = list_caption_tracks(profile_name, youtube_service, video_id, verbose=verbose)

        if not caption_tracks:
            _log(f"No caption tracks found for video '{video_title}' ({video_id}).", verbose)
            results["failed"].append({"video_id": video_id, "title": video_title, "reason": "No caption tracks available", "caption_filepath": None})
            continue

        target_caption = next((track for track in caption_tracks if track["language"] == "en"), caption_tracks[0])
        caption_id = target_caption["id"]
        caption_language = target_caption["language"]
        
        output_filename = f"{video_id}_{caption_language}.srt"
        output_path = os.path.join(captions_dir, output_filename)

        _log(f"Attempting to download {caption_language} caption for '{video_title}' ({video_id}) via API.", verbose)
        if download_caption_track(profile_name, youtube_service, caption_id, output_path, verbose=verbose):
            results["success"].append({"video_id": video_id, "title": video_title, "filename": output_path, "caption_filepath": output_path})
            _log(f"Successfully downloaded captions for '{video_title}' ({video_id}).", verbose)
        else:
            results["failed"].append({"video_id": video_id, "title": video_title, "reason": "API download failed", "caption_filepath": None})
            _log(f"Failed to download captions for '{video_title}' ({video_id}) via API.", verbose, is_error=True)
    return results 

def download_captions_via_transcript_api(profile_name: str, videos_data: List[Dict[str, Any]], verbose: bool = False) -> Dict[str, Any]:
    results = {
        "success": [],
        "failed": []
    }
    
    captions_dir = get_youtube_captions_dir(profile_name)
    Path(captions_dir).mkdir(parents=True, exist_ok=True)
    
    formatter = SRTFormatter()
    ytt_api = YouTubeTranscriptApi()

    for i, video in enumerate(videos_data):
        video_id = video.get("video_id")
        video_title = video.get("title", "Unknown Title")

        if not video_id:
            _log(f"No video ID found for video {i+1}. Skipping Transcript API caption download.", verbose, is_error=True)
            results["failed"].append({"video_id": "N/A", "title": video_title, "reason": "No video ID", "caption_filepath": None})
            continue
        
        try:
            _log(f"Attempting to fetch captions for '{video_title}' ({video_id}) via YouTubeTranscriptApi.", verbose)
            transcript_list = ytt_api.list(video_id)
            
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except NoTranscriptFound:
                _log(f"No manually created English transcript found for {video_id}, trying generated.", verbose)
                try:
                    transcript = transcript_list.find_generated_transcript(['en'])
                except NoTranscriptFound:
                    _log(f"No generated English transcript found for {video_id}, trying any available manually created.", verbose)
                    try:
                        transcript = transcript_list.find_manually_created_transcript([t.language_code for t in transcript_list])
                    except NoTranscriptFound:
                        _log(f"No manually created transcripts in any language found for {video_id}, trying any available generated.", verbose)
                        try:
                            transcript = transcript_list.find_generated_transcript([t.language_code for t in transcript_list])
                        except NoTranscriptFound:
                            pass
            
            if transcript:
                fetched_transcript = transcript.fetch()
                formatted_caption = formatter.format_transcript(fetched_transcript)
                
                output_filename = f"{video_id}_{transcript.language_code}.srt"
                output_path = os.path.join(captions_dir, output_filename)

                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_caption)
                
                results["success"].append({"video_id": video_id, "title": video_title, "filename": output_path, "caption_filepath": output_path})
                _log(f"Successfully downloaded captions for '{video_title}' ({video_id}) via Transcript API.", verbose)
            else:
                _log(f"No suitable caption tracks found for video '{video_title}' ({video_id}) via Transcript API.", verbose)
                results["failed"].append({"video_id": video_id, "title": video_title, "reason": "No suitable caption tracks found via Transcript API", "caption_filepath": None})

        except (NoTranscriptFound, TranscriptsDisabled) as e:
            _log(f"Captions not available or disabled for '{video_title}' ({video_id}): {e}", verbose, is_error=True)
            results["failed"].append({"video_id": video_id, "title": video_title, "reason": str(e), "caption_filepath": None})
        except Exception as e:
            _log(f"Unexpected error fetching captions for '{video_title}' ({video_id}) via Transcript API: {repr(e)}", verbose, is_error=True)
            results["failed"].append({"video_id": video_id, "title": video_title, "reason": repr(e), "caption_filepath": None})
            
    return results 