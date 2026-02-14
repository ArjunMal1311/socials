import os
import time
import shutil
import base64
import mimetypes

from rich.console import Console
from typing import List, Dict, Any, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.image_download import download_images
from services.support.video_download import download_twitter_videos
from services.support.path_config import get_x_replies_dir, ensure_dir_exists
from services.support.gemini_util import generate_gemini
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker

console = Console()

def build_reply_prompt_parts(tweet_text: str, media_paths: List[str], custom_prompt: str, all_replies: List[Dict], verbose: bool = False, status=None) -> List:
    prompt_parts = []
    
    prompt_parts.append(custom_prompt)
    
    sample_section = ''
    if all_replies:
        approved_examples = []
        for r in all_replies:
            if r.get('approved') and r.get('reply') and r.get('tweet_text'):
                approved_examples.append(f"Original Tweet: {r['tweet_text']}\nApproved Reply: {r['reply']}")
        
        if approved_examples:
            sample_section = 'Sample approved tweet-reply pairs:\n' + '\n---\n'.join(approved_examples) + '\n\n'
    
    if sample_section:
        prompt_parts.append("This is sample section of approved replies to similar tweets:\n")
        prompt_parts.append(sample_section)
    
    prompt_parts.append(f"Tweet Text: {tweet_text}\n")
    
    if media_paths:
        for media_path in media_paths:
            try:
                mime_type = mimetypes.guess_type(media_path)[0] or "application/octet-stream"
                if not mime_type.startswith(('image/', 'video/')):
                    log(f"Skipping unsupported media type {mime_type} for {media_path}", verbose, status, is_error=False, log_caller_file="reply_home_support.py")
                    continue
                
                with open(media_path, 'rb') as f:
                    data_b64 = base64.b64encode(f.read()).decode('utf-8')
                
                prompt_parts.append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": data_b64
                    }
                })
                prompt_parts.append("\n")
                log(f"Inlined media {os.path.basename(media_path)} (MIME: {mime_type})", verbose, status, is_error=False, log_caller_file="reply_home_support.py")
            except Exception as e:
                log(f"Could not process media item {media_path}: {e}", verbose, status, is_error=False, log_caller_file="reply_home_support.py")
    
    prompt_parts.append("Important: Generate exactly ONE reply. Do not provide multiple options or explanations take inspiration from sample_section to my writing style.\n")
    prompt_parts.append("Just write a single direct reply that matches the prompt requirements.\n")
    prompt_parts.append("Reply:\n")
    
    return prompt_parts

def _ensure_home_mode_folder(profile_name: str) -> str:
    base_dir = get_x_replies_dir(profile_name)
    return ensure_dir_exists(base_dir)

def _get_temp_media_dir(temp_processing_dir: str) -> str:
    temp_dir = os.path.join(temp_processing_dir, '_temp_media')
    return ensure_dir_exists(temp_dir)

def _cleanup_temp_media_dir(temp_processing_dir: str, verbose: bool = False):
    temp_dir = os.path.join(temp_processing_dir, '_temp_media')
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        log(f"Cleaned up temporary media directory: {temp_dir}", verbose, log_caller_file="reply_home_support.py")

def _copy_medi_into_home_mode(media_paths: List[str], temp_processing_dir: str, verbose: bool = False) -> List[str]:
    saved_abs_paths: List[str] = []
    for path in media_paths:
        if not path:
            continue
        try:
            filename = os.path.basename(path)
            target_path = os.path.join(temp_processing_dir, filename)

            if os.path.exists(target_path):
                name, ext = os.path.splitext(filename)
                suffix_idx = 1
                while os.path.exists(target_path):
                    filename = f"{name}_{suffix_idx}{ext}"
                    target_path = os.path.join(temp_processing_dir, filename)
                    suffix_idx += 1
            shutil.copy2(path, target_path)
            saved_abs_paths.append(os.path.abspath(target_path))
        except Exception as e:
            log(f"Error copying media {path} into temp processing dir: {e}", verbose, is_error=True, log_caller_file="reply_home_support.py")
    return saved_abs_paths

def _prepare_media_for_gemini_home_mode(tweet_data: Dict[str, Any], profile_name: str, temp_processing_dir: str, is_home_mode: bool = False, ignore_video_tweets: bool = False, verbose: bool = False) -> List[str]:
    media_abs_paths_for_gemini: List[str] = []
    raw_media_urls = tweet_data.get('media_urls')

    if is_home_mode:
        temp_media_dir = _get_temp_media_dir(temp_processing_dir)
        if raw_media_urls:
            if ignore_video_tweets and (raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video')):
                log(f"Ignoring video tweet {tweet_data['tweet_id']} due to --ignore-video-tweets flag.", verbose, is_error=False, log_caller_file="reply_home_support.py")
            elif raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
                try:
                    video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True)
                    if video_path:
                        copied = _copy_medi_into_home_mode([video_path], temp_media_dir, verbose)
                        media_abs_paths_for_gemini.extend(copied)
                    else:
                        log(f"Video download failed or returned no path for {tweet_data['tweet_id']}", verbose, is_error=False, log_caller_file="reply_home_support.py")
                except Exception as e:
                    log(f"Error handling video for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True, log_caller_file="reply_home_support.py")
            elif isinstance(raw_media_urls, (list, str)):
                image_urls = [u.strip() for u in (raw_media_urls if isinstance(raw_media_urls, list) else str(raw_media_urls).split(';')) if u and u.strip()]
                if image_urls:
                    downloaded_images = download_images(image_urls, temp_media_dir)
                    copied = _copy_medi_into_home_mode(downloaded_images, temp_media_dir, verbose)
                    media_abs_paths_for_gemini.extend(copied)
                
        return media_abs_paths_for_gemini

    if ignore_video_tweets and (raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video')):
        log(f"Ignoring video tweet {tweet_data['tweet_id']} due to --ignore-video-tweets flag.", verbose, is_error=False, log_caller_file="reply_home_support.py")
    elif raw_media_urls == 'video' or (isinstance(raw_media_urls, str) and raw_media_urls.strip() == 'video'):
        try:
            video_path = download_twitter_videos([tweet_data['tweet_url']], profile_name="Download", headless=True)
            if video_path:
                copied = _copy_medi_into_home_mode([video_path], temp_processing_dir, verbose)
                media_abs_paths_for_gemini.extend(copied)
            else:
                log(f"Video download failed or returned no path for {tweet_data['tweet_id']}", verbose, is_error=False, log_caller_file="reply_home_support.py")
        except Exception as e:
            log(f"Error handling video for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True, log_caller_file="reply_home_support.py")
    elif raw_media_urls:
        try:
            image_urls = [u.strip() for u in str(raw_media_urls).split(';') if u and u.strip()]
            if image_urls:
                downloaded_images = download_images(image_urls, profile_name)
                copied = _copy_medi_into_home_mode(downloaded_images, temp_processing_dir, verbose)
                media_abs_paths_for_gemini.extend(copied)
        except Exception as e:
            log(f"Error handling images for tweet {tweet_data['tweet_id']}: {str(e)}", verbose, is_error=True, log_caller_file="reply_home_support.py")

    return media_abs_paths_for_gemini

def _navigate_to_community(driver, community_name: str, verbose: bool = False):
    try:
        community_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f"//a[@role='tab']//span[contains(text(), '{community_name}')]"))
        )
        community_tab.click()
        log(f"Successfully clicked on '{community_name}' community tab.", verbose, log_caller_file="reply_home_support.py")
        time.sleep(5)
    except Exception as e:
        log(f"Could not find or click community tab '{community_name}': {e}. Proceeding with general home feed scouting.", verbose, is_error=False, log_caller_file="reply_home_support.py")
