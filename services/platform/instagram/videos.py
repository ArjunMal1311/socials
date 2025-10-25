import re
import os
import sys
import argparse
import subprocess

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Optional, Dict, Any
from services.support.path_config import get_instagram_videos_dir

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None, api_info: Optional[Dict[str, Any]] = None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_error:
        level = "ERROR"
        style = "bold red"
    else:
        level = "INFO"
        style = "white"
    
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    if api_info:
        api_message = api_info.get('message', '')
        if api_message:
            formatted_message += f" | API: {api_message}"
    
    console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def download_instagram_videos(video_urls: list, profile_name: str, status: Status = None, verbose: bool = False):
    output_dir = get_instagram_videos_dir(profile_name)
    os.makedirs(output_dir, exist_ok=True)

    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except FileNotFoundError:
        _log("Error: yt-dlp is not installed.", verbose, is_error=True)
        _log("Please install it using: pip install yt-dlp or sudo wget https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -O /usr/local/bin/yt-dlp && sudo chmod a+rx /usr/local/bin/yt-dlp", verbose)
        return []
    except subprocess.CalledProcessError as e:
        _log(f"Error checking yt-dlp version: {e}", verbose, is_error=True)
        return []

    downloaded_paths = []
    for i, url in enumerate(video_urls):
        if status:
            status.update(f"[white]Downloading video {i+1}/{len(video_urls)} from {url} using yt-dlp...[/white]")
        
        try:
            output_template = os.path.join(output_dir, '%(id)s.%(ext)s')
            command = [
                'yt-dlp',
                '--format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]', 
                '--output', output_template,
                '--restrict-filenames',
                url
            ]
            
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            
            downloaded_file_match = re.search(r'\[download\] Destination: (.+)', result.stdout)
            if downloaded_file_match:
                downloaded_file = downloaded_file_match.group(1)
                downloaded_paths.append(downloaded_file)
                if status:
                    status.update(f"[green]Successfully downloaded {os.path.basename(downloaded_file)}[/green]")
                else:
                    _log(f"Successfully downloaded {os.path.basename(downloaded_file)}", verbose)
            else:
                raise Exception("yt-dlp output did not contain expected download destination.")

        except subprocess.CalledProcessError as e:
            if status:
                status.update(f"[bold red]Error downloading {url} with yt-dlp: {e.stderr}[/bold red]")
            else:
                _log(f"Error downloading {url} with yt-dlp: {e.stderr}", verbose, is_error=True)
        except Exception as e:
            if status:
                status.update(f"[bold red]An unexpected error occurred for {url}: {e}[/bold red]")
            else:
                _log(f"An unexpected error occurred for {url}: {e}", verbose, is_error=True)
    
    return downloaded_paths

def main():
    parser = argparse.ArgumentParser(description="Instagram Video Downloader CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use. Videos will be saved to instagram_videos/{profile}/.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--urls", type=str, required=True, help="Comma-separated list of Instagram video URLs to download.")
    parser.add_argument("--show-complete", action="store_true", help="Show complete logs.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    video_urls = [url.strip() for url in args.urls.split(',') if url.strip()]

    if not video_urls:
        _log("No valid URLs provided. Please provide a comma-separated list of Instagram video URLs.", args.verbose, is_error=True)
        sys.exit(1)

    with Status("[white]Starting Instagram video download...[/white]", spinner="dots", console=console) as status:
        downloaded = download_instagram_videos(video_urls, args.profile, status=status, verbose=args.verbose)
        status.stop()
        _log(f"Download process complete. Downloaded {len(downloaded)} videos.", args.verbose)

if __name__ == "__main__":
    main()
