import os
import subprocess

from rich.console import Console
from typing import List, Dict, Any
from services.support.logger_util import _log as log
from services.support.path_config import get_downloads_dir

console = Console()

def download_videos_for_youtube_scraper(profile_name: str, videos_data: List[Dict[str, Any]], verbose: bool = False) -> List[Dict[str, Any]]:
    download_results = {
        "success": [],
        "failed": []
    }

    output_dir = os.path.abspath(os.path.join(get_downloads_dir(), 'youtube', profile_name, 'videos'))
    os.makedirs(output_dir, exist_ok=True)

    total_videos = len(videos_data)
    log(f"Starting to download {total_videos} videos for profile '{profile_name}'", verbose, log_caller_file="video_downloader.py")

    for i, video in enumerate(videos_data):
        video_url = video.get('url')
        video_id = video.get('video_id')
        video_title = video.get('title', 'Unknown Title')

        if not video_url:
            log(f"No URL found for video {i+1}/{total_videos}. Skipping.", verbose, log_caller_file="video_downloader.py")
            download_results["failed"].append({
                "video_id": video_id or "Unknown",
                "title": video_title,
                "reason": "No URL provided",
                "video_filepath": None
            })
            continue

        console.print(f"[white]Processing video {i+1}/{total_videos}: {video_title}[/white]")

        try:
            cmd = [
                'yt-dlp',
                '--output', os.path.join(output_dir, '% (id)s.% (ext)s'),
                '--restrict-filenames',
                video_url
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True, check=True)
            log(f"Successfully downloaded: {video_title}", verbose, log_caller_file="video_downloader.py")
            download_results["success"].append({
                "video_id": video_id,
                "title": video_title,
                "output": process.stdout.strip(),
                "video_filepath": os.path.join(output_dir, f'{video_id}.mp4')
            })  
            video["video_filepath"] = os.path.join(output_dir, f'{video_id}.mp4')

        except subprocess.CalledProcessError as e:
            log(f"Failed to download video {video_title}: {e.stderr.strip()}", verbose, is_error=True, log_caller_file="video_downloader.py")
            download_results["failed"].append({
                "video_id": video_id,
                "title": video_title,
                "reason": e.stderr.strip(),
                "video_filepath": None
            })
            video["video_filepath"] = None
        except Exception as e:
            log(f"An unexpected error occurred while downloading {video_title}: {e}", verbose, is_error=True, log_caller_file="video_downloader.py")
            download_results["failed"].append({
                "video_id": video_id,
                "title": video_title,
                "reason": str(e),
                "video_filepath": None
            })
            video["video_filepath"] = None
    
    for success_item in download_results["success"]:
        video_id = success_item.get("video_id")
        for fname in os.listdir(output_dir):
            if fname.startswith(video_id) and any(fname.endswith(ext) for ext in ['.mp4', '.webm', '.mkv', '.avi']):
                success_item["video_filepath"] = os.path.join(output_dir, fname)
                for video in videos_data:
                    if video.get("video_id") == video_id:
                        video["video_filepath"] = os.path.join(output_dir, fname)
                        break
                break

    log(f"Completed video download. Success: {len(download_results['success'])}, Failed: {len(download_results['failed'])}", verbose, log_caller_file="video_downloader.py")
    return videos_data 