import os
import requests

from typing import List, Dict, Any
from services.support.logger_util import _log as log

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
        image_urls = [url for url in media_urls if url and url != 'video' and not url.startswith('video')]
        if image_urls:
            downloaded_images = download_images_to_dir(image_urls, media_dir, verbose)
            downloaded_paths.extend(downloaded_images)
    elif isinstance(media_urls, str):
        if media_urls != 'video' and not media_urls.startswith('video'):
            image_urls = [url.strip() for url in media_urls.split(';') if url.strip() and url.strip() != 'video']
            if image_urls:
                downloaded_images = download_images_to_dir(image_urls, media_dir, verbose)
                downloaded_paths.extend(downloaded_images)

    if downloaded_paths:
        log(f"Downloaded {len(downloaded_paths)} media files for tweet {tweet_id}", verbose, log_caller_file="media_downloader.py")

    return downloaded_paths