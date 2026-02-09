# socials instagram <profile> videos --urls "url1,url2"

import os
import sys
import argparse

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.platform.instagram.support.video_utils import download_instagram_videos

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Instagram Video Downloader CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")
    parser.add_argument("--urls", type=str, required=True, help="Comma-separated list of Instagram video URLs to download.")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="videos.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    instagram_props = platform_props.get('instagram', {})
    videos_props = instagram_props.get('videos', {})

    verbose = global_props.get('verbose', False)
    output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')
    restrict_filenames = videos_props.get('restrict_filenames', True)

    video_urls = [url.strip() for url in args.urls.split(',') if url.strip()]

    if not video_urls:
        log("No valid URLs provided. Please provide a comma-separated list of Instagram video URLs.", verbose, is_error=True, log_caller_file="videos.py")
        sys.exit(1)

    with Status("[white]Starting Instagram video download...[/white]", spinner="dots", console=console) as status:
        downloaded = download_instagram_videos(video_urls, profile, output_format=output_format, restrict_filenames=restrict_filenames, status=status, verbose=verbose)
        status.stop()
        log(f"Download process complete. Downloaded {len(downloaded)} videos.", verbose, log_caller_file="videos.py")

if __name__ == "__main__":
    main()
