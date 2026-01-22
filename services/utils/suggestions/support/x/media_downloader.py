import os
import json
import requests
import datetime

from profiles import PROFILES

from typing import List, Dict, Any
from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir
from services.support.video_download import download_twitter_videos
from services.utils.suggestions.support.x.scraping_utils import get_latest_approved_file

def is_local_file_and_exists(path: str) -> bool:
    return os.path.exists(path) and (path.startswith('tmp/') or os.path.isabs(path))

def download_images_to_dir(image_urls: List[str], download_dir: str, verbose: bool = False) -> List[str]:
    os.makedirs(download_dir, exist_ok=True)

    local_image_paths = []
    for url in image_urls:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            filename = os.path.basename(url.split('?')[0])

            extension = '.jpeg'
            if 'format=' in url:
                format_param = url.split('format=')[1].split('&')[0]
                if format_param.lower() in ['jpg', 'jpeg']:
                    extension = '.jpeg'
                elif format_param.lower() == 'png':
                    extension = '.png'
                elif format_param.lower() == 'gif':
                    extension = '.gif'

            if not filename:
                filename = f"image_{len(local_image_paths)}{extension}"
            elif not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                filename = f"{filename}{extension}"

            file_path = os.path.join(download_dir, filename)

            with open(file_path, 'wb') as f:
                f.write(response.content)

            local_image_paths.append(file_path)
            log(f"Downloaded image: {filename}", verbose, log_caller_file="media_downloader.py")
        except Exception as e:
            log(f"Error downloading image {url}: {str(e)}", verbose, is_error=True, log_caller_file="media_downloader.py")

    return local_image_paths

def download_post_media(post_data: Dict[str, Any], media_dir: str, verbose: bool = False) -> List[str]:
    media_urls = post_data.get('media_urls', [])
    tweet_id = post_data.get('tweet_id', 'unknown')

    if not media_urls:
        return []

    downloaded_paths = []

    if isinstance(media_urls, list):
        image_urls_to_download = []
        video_urls_to_download = []
        for url in media_urls:
            if url and is_local_file_and_exists(url):
                downloaded_paths.append(url)
                log(f"Skipping download for existing local file: {url}", verbose, log_caller_file="media_downloader.py")
            elif url and url != 'video' and not url.startswith('video'):
                image_urls_to_download.append(url)
            elif url and url.startswith('video'):
                video_urls_to_download.append(url)

        if image_urls_to_download:
            downloaded_images = download_images_to_dir(image_urls_to_download, media_dir, verbose)
            downloaded_paths.extend(downloaded_images)

        if video_urls_to_download:
            tweet_url = post_data.get('tweet_url')
            if tweet_url:
                downloaded_videos = download_twitter_videos([tweet_url], media_dir, profile_name="Default", headless=True, verbose=verbose)
                downloaded_paths.extend(downloaded_videos)
            else:
                log(f"Warning: No tweet_url found for video download in post {tweet_id}", verbose, is_error=True, log_caller_file="media_downloader.py")

    elif isinstance(media_urls, str):
        if is_local_file_and_exists(media_urls):
            downloaded_paths.append(media_urls)
            log(f"Skipping download for existing local file: {media_urls}", verbose, log_caller_file="media_downloader.py")
        elif media_urls != 'video' and not media_urls.startswith('video'):
            image_urls = [url.strip() for url in media_urls.split(';') if url.strip() and url.strip() != 'video']
            if image_urls:
                downloaded_images = download_images_to_dir(image_urls, media_dir, verbose)
                downloaded_paths.extend(downloaded_images)
        elif media_urls.startswith('video'):
            tweet_url = post_data.get('tweet_url')
            if tweet_url:
                downloaded_videos = download_twitter_videos([tweet_url], media_dir, profile_name="Default", headless=True, verbose=verbose)
                downloaded_paths.extend(downloaded_videos)
            else:
                log(f"Warning: No tweet_url found for video download in post {tweet_id}", verbose, is_error=True, log_caller_file="media_downloader.py")

    if downloaded_paths:
        log(f"Downloaded {len(downloaded_paths)} media files for tweet {tweet_id}", verbose, log_caller_file="media_downloader.py")

    return downloaded_paths

def run_media_download(profile_name: str) -> Dict[str, Any]:
    approved_file = get_latest_approved_file(profile_name)
    if not approved_file:
        return {"error": "No approved content found. Run 'web' command and approve content first."}

    try:
        with open(approved_file, 'r') as f:
            approved_data = json.load(f)

        approved_posts = approved_data.get('approved_posts', [])
        if not approved_posts:
            return {"error": "No approved posts found in the file."}


        profile_props = PROFILES[profile_name].get('properties', {})
        global_props = profile_props.get('global', {})
        verbose = global_props.get('verbose', False)

        media_dir = os.path.join(get_suggestions_dir(profile_name), "media")
        os.makedirs(media_dir, exist_ok=True)

        downloaded_count = 0
        for post in approved_posts:
            post['profile_name'] = profile_name
            current_downloaded_paths = download_post_media(post, media_dir, verbose)
            if current_downloaded_paths:
                post['media_urls'] = current_downloaded_paths
                downloaded_count += len(current_downloaded_paths)

        updated_approved_filename = f"approved_content_x_{datetime.now().strftime('%Y%m%d_%H%M%S')}_with_media.json"
        updated_approved_filepath = os.path.join(get_suggestions_dir(profile_name), updated_approved_filename)

        with open(updated_approved_filepath, 'w') as f:
            json.dump(approved_data, f, indent=2)

        return {
            "success": True,
            "downloaded_count": downloaded_count,
            "updated_file": updated_approved_filepath
        }

    except Exception as e:
        return {"error": f"Error during media download: {str(e)}"}
