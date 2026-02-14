import os
import json
import subprocess

from rich.status import Status

from services.support.logger_util import _log as log
from services.support.path_config import get_instagram_reels_dir, get_instagram_videos_dir

def download_instagram_videos(video_urls: str | list, profile_name: str, output_format: str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', restrict_filenames: bool = True, status: Status = None, verbose: bool = False, extract_cdn_links: bool = False, use_reels_dir: bool = False):
    is_single_url = isinstance(video_urls, str)
    urls = [video_urls] if is_single_url else video_urls
    
    if use_reels_dir:
        output_dir = get_instagram_reels_dir(profile_name)
    else:
        output_dir = get_instagram_videos_dir(profile_name)
    
    os.makedirs(output_dir, exist_ok=True)

    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except FileNotFoundError:
        log("Error: yt-dlp is not installed.", verbose, is_error=True, log_caller_file="video_utils.py")
        log("Please install it using: pip install yt-dlp or sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp", verbose, log_caller_file="video_utils.py")
        return (None, None) if (is_single_url and extract_cdn_links) else (None if is_single_url else [])
    except subprocess.CalledProcessError as e:
        log(f"Error checking yt-dlp version: {e}", verbose, is_error=True, log_caller_file="video_utils.py")
        return (None, None) if (is_single_url and extract_cdn_links) else (None if is_single_url else [])

    results = []
    
    for i, url in enumerate(urls):
        if status:
            progress_text = f"[white]Downloading video {i+1}/{len(urls)} from {url} using yt-dlp...[/white]"
            status.update(progress_text)

        cdn_link = None
        
        if extract_cdn_links:
            try:
                info_command = ['yt-dlp', '--dump-json', url]
                
                if verbose:
                    log(f"Fetching video metadata for {url} using yt-dlp: {' '.join(info_command)}", verbose, log_caller_file="video_utils.py")
                
                info_result = subprocess.run(info_command, capture_output=True, text=True, check=True)
                video_info = json.loads(info_result.stdout)

                for fmt in video_info.get('formats', []):
                    if fmt.get('ext') == 'mp4' and fmt.get('url') and fmt.get('protocol', '') != 'm3u8_native':
                        cdn_link = fmt['url']
                        log(f"Found CDN link for MP4: {cdn_link}", verbose, log_caller_file="video_utils.py")
                        break
                
                if not cdn_link and 'url' in video_info:
                    cdn_link = video_info['url']
                    log(f"Found generic CDN link from video info: {cdn_link}", verbose, log_caller_file="video_utils.py")

                if not cdn_link:
                    log(f"Could not find a suitable CDN link for {url}", verbose, is_error=True, log_caller_file="video_utils.py")
                    
            except subprocess.CalledProcessError as e:
                log(f"Error fetching metadata for {url}: {e.stderr}", verbose, is_error=True, log_caller_file="video_utils.py")
            except Exception as e:
                log(f"An unexpected error occurred fetching metadata for {url}: {e}", verbose, is_error=True, log_caller_file="video_utils.py")

        try:
            output_template = os.path.join(output_dir, '%(id)s.%(ext)s')
            download_command = [
                'yt-dlp',
                '--format', output_format,
                '--output', output_template,
                '--print', 'after_move:filepath',
            ]

            if restrict_filenames:
                download_command.append('--restrict-filenames')

            download_command.append(url)

            if verbose:
                log(f"Downloading video with yt-dlp command: {' '.join(download_command)}", verbose, log_caller_file="video_utils.py")

            download_result = subprocess.run(download_command, capture_output=True, text=True, check=True)
            downloaded_file_path = download_result.stdout.strip()

            if downloaded_file_path and os.path.exists(downloaded_file_path):
                log(f"Successfully downloaded video to: {downloaded_file_path}", verbose, log_caller_file="video_utils.py")
                
                if status:
                    status.update(f"[green]Successfully downloaded {os.path.basename(downloaded_file_path)}[/green]")
                
                results.append({
                    'file_path': downloaded_file_path,
                    'cdn_link': cdn_link
                })
            else:
                log(f"Could not determine or find downloaded file path for {url}. Output: {download_result.stdout}", verbose, is_error=True, log_caller_file="video_utils.py")
                results.append({
                    'file_path': None,
                    'cdn_link': cdn_link
                })

        except subprocess.CalledProcessError as e:
            log(f"Error downloading {url} with yt-dlp: {e.stderr}", verbose, is_error=True, log_caller_file="video_utils.py")
            if status:
                status.update(f"[bold red]Error downloading {url}[/bold red]")
            results.append({
                'file_path': None,
                'cdn_link': cdn_link
            })
        except Exception as e:
            log(f"An unexpected error occurred downloading {url}: {e}", verbose, is_error=True, log_caller_file="video_utils.py")
            if status:
                status.update(f"[bold red]An unexpected error occurred for {url}[/bold red]")
            results.append({
                'file_path': None,
                'cdn_link': cdn_link
            })

    if is_single_url:
        if extract_cdn_links:
            return (results[0]['file_path'], results[0]['cdn_link'])
        else:
            return results[0]['file_path']
    else:
        return results