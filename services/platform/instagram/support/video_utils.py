import os
import subprocess
import json
import re

from rich.status import Status

from typing import Optional, Tuple

from services.support.logger_util import _log as log
from services.support.path_config import get_instagram_reels_dir, get_instagram_videos_dir


def download_instagram_reel(reel_url: str, profile_name: str, output_format: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', restrict_filenames: bool = True, status: Status = None, verbose: bool = False) -> Tuple[Optional[str], Optional[str]]:
    output_dir = get_instagram_reels_dir(profile_name)
    os.makedirs(output_dir, exist_ok=True)

    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except FileNotFoundError:
        log("Error: yt-dlp is not installed.", verbose, is_error=True, log_caller_file="video_utils.py")
        log("Please install it using: pip install yt-dlp or sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp", verbose, log_caller_file="video_utils.py")
        return None, None
    except subprocess.CalledProcessError as e:
        log(f"Error checking yt-dlp version: {e}", verbose, is_error=True, log_caller_file="video_utils.py")
        return None, None

    try:
        info_command = [
            'yt-dlp',
            '--dump-json',
            reel_url,
        ]

        if verbose:
            log(f"Fetching video metadata for {reel_url} using yt-dlp: {' '.join(info_command)}", verbose, log_caller_file="video_utils.py")
        
        info_result = subprocess.run(info_command, capture_output=True, text=True, check=True)
        video_info = json.loads(info_result.stdout)

        cdn_link = None
        for fmt in video_info.get('formats', []):
            if fmt.get('ext') == 'mp4' and fmt.get('url') and fmt.get('protocol', '') != 'm3u8_native':
                cdn_link = fmt['url']
                log(f"Found CDN link for MP4: {cdn_link}", verbose, log_caller_file="video_utils.py")
                break
        
        if not cdn_link and 'url' in video_info:
            cdn_link = video_info['url']
            log(f"Found generic CDN link from video info: {cdn_link}", verbose, log_caller_file="video_utils.py")


        if not cdn_link:
            log(f"Could not find a suitable CDN link for {reel_url}", verbose, is_error=True, log_caller_file="video_utils.py")
            return None, None

        output_template = os.path.join(output_dir, '%(id)s.%(ext)s')
        download_command = [
            'yt-dlp',
            '--format', output_format,
            '--output', output_template,
            '--print', 'after_move:filepath',
        ]

        if restrict_filenames:
            download_command.append('--restrict-filenames')

        download_command.append(reel_url)

        if status:
            status.update(f"[white]Downloading reel from {reel_url} using yt-dlp...[/white]")

        if verbose:
            log(f"Downloading reel with yt-dlp command: {' '.join(download_command)}", verbose, log_caller_file="video_utils.py")

        download_result = subprocess.run(download_command, capture_output=True, text=True, check=True)
        downloaded_file_path = download_result.stdout.strip()

        if downloaded_file_path and os.path.exists(downloaded_file_path):
            log(f"Successfully downloaded reel to: {downloaded_file_path}", verbose, log_caller_file="video_utils.py")
            return downloaded_file_path, cdn_link
        else:
            log(f"Could not determine or find downloaded file path for {reel_url}. Output: {download_result.stdout}", verbose, is_error=True, log_caller_file="video_utils.py")
            return None, cdn_link

    except subprocess.CalledProcessError as e:
        log(f"Error downloading {reel_url} with yt-dlp: {e.stderr}", verbose, is_error=True, log_caller_file="video_utils.py")
    except Exception as e:
        log(f"An unexpected error occurred downloading {reel_url}: {e}", verbose, is_error=True, log_caller_file="video_utils.py")

    return None, None


def download_instagram_videos(video_urls: list, profile_name: str, output_format: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', restrict_filenames: bool = True, status: Status = None, verbose: bool = False):
    output_dir = get_instagram_videos_dir(profile_name)
    os.makedirs(output_dir, exist_ok=True)

    if '%(id)s' not in output_format and '%(title)s' not in output_format:
        output_format = f'%(id)s.{output_format}'

    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except FileNotFoundError:
        log("Error: yt-dlp is not installed.", verbose, is_error=True, log_caller_file="video_utils.py")
        log("Please install it using: pip install yt-dlp or sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp", verbose, log_caller_file="video_utils.py")
        return []
    except subprocess.CalledProcessError as e:
        log(f"Error checking yt-dlp version: {e}", verbose, is_error=True, log_caller_file="video_utils.py")
        return []

    downloaded_paths = []
    for i, url in enumerate(video_urls):
        if status:
            status.update(f"[white]Downloading video {i+1}/{len(video_urls)} from {url} using yt-dlp...[/white]")

        try:
            output_template = os.path.join(output_dir, '%(id)s.%(ext)s')
            command = [
                'yt-dlp',
                '--format', output_format,
                '--output', output_template,
                '--print', 'after_move:filepath',
            ]

            if restrict_filenames:
                command.append('--restrict-filenames')

            command.append(url)

            result = subprocess.run(command, capture_output=True, text=True, check=True)

            downloaded_file = result.stdout.strip()
            if downloaded_file and os.path.exists(downloaded_file):
                downloaded_paths.append(downloaded_file)
                if status:
                    status.update(f"[green]Successfully downloaded {os.path.basename(downloaded_file)}[/green]")
                else:
                    log(f"Successfully downloaded {os.path.basename(downloaded_file)}", verbose, log_caller_file="video_utils.py")
            else:
                log(f"yt-dlp output did not contain expected download destination or file not found. Output: {result.stdout}", verbose, is_warning=True, log_caller_file="video_utils.py")

        except subprocess.CalledProcessError as e:
            if status:
                status.update(f"[bold red]Error downloading {url} with yt-dlp: {e.stderr}[/bold red]")
            else:
                log(f"Error downloading {url} with yt-dlp: {e.stderr}", verbose, is_error=True, log_caller_file="video_utils.py")
        except Exception as e:
            if status:
                status.update(f"[bold red]An unexpected error occurred for {url}: {e}[/bold red]")
            else:
                log(f"An unexpected error occurred for {url}: {e}", verbose, is_error=True, log_caller_file="video_utils.py")

    return downloaded_paths