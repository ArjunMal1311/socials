import os
import json
import requests
import re

from typing import List, Dict, Any
from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir
from services.utils.suggestions.support.reddit.scraping_utils import get_latest_approved_reddit_file

def extract_reddit_media_urls(content: str, post_url: str) -> List[str]:
    media_urls = []

    patterns = [
        r'https?://i\.redd\.it/[^)\s]+',
        r'https?://v\.redd\.it/[^)\s]+',
        r'https?://i\.imgur\.com/[^)\s]+',
        r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|mp4|webm)(?:\?[^\s]*)?',
    ]

    if content:
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            media_urls.extend(matches)

    if post_url:
        for pattern in patterns:
            matches = re.findall(pattern, post_url, re.IGNORECASE)
            media_urls.extend(matches)

    seen = set()
    unique_urls = []
    for url in media_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls

def download_reddit_images_to_dir(image_urls: List[str], download_dir: str, verbose: bool = False) -> List[str]:
    os.makedirs(download_dir, exist_ok=True)

    local_image_paths = []
    for url in image_urls:
        try:
            if not any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                continue

            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()

            filename = os.path.basename(url.split('?')[0])
            if not filename:
                filename = f"reddit_image_{len(local_image_paths)}.jpg"

            file_path = os.path.join(download_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(response.content)

            local_image_paths.append(file_path)
            log(f"Downloaded Reddit image: {filename}", verbose, log_caller_file="media_downloader.py")

        except Exception as e:
            log(f"Error downloading Reddit image {url}: {str(e)}", verbose, is_error=True, log_caller_file="media_downloader.py")

    return local_image_paths

def download_reddit_post_media(post_data: Dict[str, Any], media_dir: str, verbose: bool = False) -> List[str]:
    content = post_data.get('data', {}).get('content', '')
    post_url = post_data.get('data', {}).get('url', '')
    post_id = post_data.get('data', {}).get('id', 'unknown')

    if not content and not post_url:
        return []

    media_urls = extract_reddit_media_urls(content, post_url)

    if not media_urls:
        return []

    downloaded_paths = []

    image_urls = [url for url in media_urls if not url.lower().endswith(('.mp4', '.webm', '.mov'))]

    if image_urls:
        downloaded_images = download_reddit_images_to_dir(image_urls, media_dir, verbose)
        downloaded_paths.extend(downloaded_images)


    if downloaded_paths:
        log(f"Downloaded {len(downloaded_paths)} media files for Reddit post {post_id}", verbose, log_caller_file="media_downloader.py")

    return downloaded_paths

def run_reddit_media_download(profile_name: str) -> Dict[str, Any]:
    approved_file = get_latest_approved_reddit_file(profile_name)
    if not approved_file:
        return {"error": "No approved Reddit content found. Run 'web' command and approve content first."}

    try:
        with open(approved_file, 'r') as f:
            approved_data = json.load(f)

        approved_posts = approved_data.get('approved_reddit_posts', [])
        if not approved_posts:
            return {"error": "No approved Reddit posts found in the file."}

        profile_props = PROFILES[profile_name].get('properties', {})
        global_props = profile_props.get('global', {})
        verbose = global_props.get('verbose', False)

        media_dir = os.path.join(get_suggestions_dir(profile_name), "reddit_media")
        os.makedirs(media_dir, exist_ok=True)

        downloaded_count = 0
        for post in approved_posts:
            post['profile_name'] = profile_name
            current_downloaded_paths = download_reddit_post_media(post, media_dir, verbose)
            if current_downloaded_paths:
                post['media_urls'] = current_downloaded_paths
                downloaded_count += len(current_downloaded_paths)

        import datetime
        updated_approved_filename = f"approved_content_reddit_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_with_media.json"
        updated_approved_filepath = os.path.join(get_suggestions_dir(profile_name), updated_approved_filename)

        with open(updated_approved_filepath, 'w') as f:
            json.dump(approved_data, f, indent=2)

        return {
            "success": True,
            "downloaded_count": downloaded_count,
            "updated_file": updated_approved_filepath
        }

    except Exception as e:
        return {"error": f"Error during Reddit media download: {str(e)}"}

from profiles import PROFILES
