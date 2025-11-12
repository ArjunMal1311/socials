import os
import re
import shutil
import json

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Optional, List, Dict, Any
from services.support.path_config import get_youtube_profile_dir, get_youtube_videos_dir, get_youtube_captions_dir

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
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
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[file_manager.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[file_manager.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def _parse_views_string(views_str: str) -> int:
    if not views_str or views_str.lower() == 'no views':
        return 0
    
    views_str = views_str.lower().replace('views', '').strip().replace(',', '')
    
    if 'k' in views_str:
        return int(float(views_str.replace('k', '')) * 1000)
    elif 'm' in views_str:
        return int(float(views_str.replace('m', '')) * 1000000)
    elif 'b' in views_str:
        return int(float(views_str.replace('b', '')) * 1000000000)
    else:
        try:
            return int(views_str)
        except ValueError:
            return 0

def _parse_video_length_to_seconds(length_str: str) -> int:
    if not length_str:
        return 0
    
    parts = length_str.split(':')
    total_seconds = 0
    if len(parts) == 1:
        try:
            total_seconds = int(parts[0])
        except ValueError:
            pass
    elif len(parts) == 2:
        try:
            minutes = int(parts[0])
            seconds = int(parts[1])
            total_seconds = minutes * 60 + seconds
        except ValueError:
            pass
    elif len(parts) == 3:
        try:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            total_seconds = hours * 3600 + minutes * 60 + seconds
        except ValueError:
            pass
    return total_seconds

def clear_youtube_files(profile_name: str, status: Optional[Status] = None, verbose: bool = False) -> int:
    youtube_profile_dir = get_youtube_profile_dir(profile_name)
    videos_dir = get_youtube_videos_dir(profile_name)
    captions_dir = get_youtube_captions_dir(profile_name)

    deleted_count = 0

    if os.path.exists(videos_dir):
        if status:
            status.update(f"[white]Removing video files from {videos_dir}...[/white]")
        else:
            _log(f"Removing video files from {videos_dir}...", verbose)
        try:
            shutil.rmtree(videos_dir)
            deleted_count += 1
        except Exception as e:
            if status:
                status.update(f"[yellow]Could not delete video directory {videos_dir}: {e}[/yellow]")
            else:
                _log(f"Could not delete video directory {videos_dir}: {e}", verbose)
    
    if os.path.exists(captions_dir):
        if status:
            status.update(f"[white]Removing caption files from {captions_dir}...[/white]")
        else:
            _log(f"Removing caption files from {captions_dir}...", verbose)
        try:
            shutil.rmtree(captions_dir)
            deleted_count += 1
        except Exception as e:
            if status:
                status.update(f"[yellow]Could not delete caption directory {captions_dir}: {e}[/yellow]")
            else:
                _log(f"Could not delete caption directory {captions_dir}: {e}", verbose)

    if status:
        status.update(f"[white]Recreating empty 'videos' and 'captions' directories for {profile_name}...[/white]")
    else:
        _log(f"Recreating empty 'videos' and 'captions' directories for {profile_name}...", verbose)

    os.makedirs(videos_dir, exist_ok=True)
    os.makedirs(captions_dir, exist_ok=True)
    
    if status:
        status.update(f"[white]Cleared {deleted_count} directories for profile {profile_name}.[/white]")
    else:
        _log(f"Cleared {deleted_count} directories for profile {profile_name}.", verbose)

    return deleted_count

def get_latest_dated_json_file(directory: str, prefix: str = "youtube_scraped_data_") -> Optional[str]:
    latest_file = None
    latest_timestamp = None
    for filename in os.listdir(directory):
        if filename.startswith(prefix) and filename.endswith(".json"):
            try:
                timestamp_str = filename[len(prefix):-len(".json")]
                current_timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if latest_timestamp is None or current_timestamp > latest_timestamp:
                    latest_timestamp = current_timestamp
                    latest_file = os.path.join(directory, filename)
            except ValueError:
                continue
    return latest_file

def clean_and_sort_videos(profile_name: str, json_filename_prefix: str, weekly_filter: bool = False, today_filter: bool = False, max_duration_minutes: Optional[int] = None, status: Optional[Status] = None, verbose: bool = False) -> None:
    youtube_profile_dir = get_youtube_profile_dir(profile_name)
    
    latest_json_path = None
    latest_date = None

    for f in os.listdir(youtube_profile_dir):
        if f.startswith(json_filename_prefix) and f.endswith('.json'):
            try:
                date_part = f.replace(json_filename_prefix, '').replace('.json', '').strip('_')
                if len(date_part) == 8:
                    current_date = datetime.strptime(date_part, '%Y%m%d').date()
                    if latest_date is None or current_date > latest_date:
                        latest_date = current_date
                        latest_json_path = os.path.join(youtube_profile_dir, f)
            except ValueError:
                continue

    if not latest_json_path:
        if status:
            status.update(f"[yellow]No video data file found with prefix '{json_filename_prefix}' in {youtube_profile_dir}. Skipping clean and sort.[/yellow]")
        else:
            _log(f"No video data file found with prefix '{json_filename_prefix}' in {youtube_profile_dir}. Skipping clean and sort.", verbose)
        return

    try:
        with open(latest_json_path, 'r', encoding='utf-8') as f:
            videos: List[Dict[str, Any]] = json.load(f)
    except Exception as e:
        if status:
            status.update(f"[bold red]Error loading video data from {latest_json_path}: {e}[/bold red]")
        else:
            _log(f"Error loading video data from {latest_json_path}: {e}", verbose, is_error=True)
        return

    initial_count = len(videos)
    if status:
        status.update(f"[white]Loaded {initial_count} videos. Cleaning and sorting...[/white]")

    _log(f"Debug: today_filter={today_filter}, weekly_filter={weekly_filter}, max_duration_minutes={max_duration_minutes}", verbose)

    cleaned_videos = []
    for video in videos:
        views_str = str(video.get('views', '0')).strip()
        numeric_views = _parse_views_string(views_str)

        video_length_str = str(video.get('video_length', '')).strip()
        video_length_seconds = _parse_video_length_to_seconds(video_length_str)
        
        should_keep = False
        if today_filter:
            if numeric_views >= 500:
                should_keep = True
            else:
                _log(f"Debug: Skipping '{video.get('title', 'Unknown')}' ({views_str} -> {numeric_views}) - below daily threshold.", verbose)
        elif weekly_filter:
            if numeric_views >= 2000:
                should_keep = True
            else:
                _log(f"Debug: Skipping '{video.get('title', 'Unknown')}' ({views_str} -> {numeric_views}) - below weekly threshold.", verbose)
        else:
            if numeric_views > 0: 
                should_keep = True
            else:
                _log(f"Debug: Skipping '{video.get('title', 'Unknown')}' ({views_str} -> {numeric_views}) - no views.", verbose)

        if should_keep and max_duration_minutes is not None:
            if video_length_seconds > (max_duration_minutes * 60):
                _log(f"Debug: Skipping '{video.get('title', 'Unknown')}' ({video_length_str}) - exceeds max duration of {max_duration_minutes} minutes.", verbose)
                should_keep = False

        if should_keep:
            video['parsed_views'] = numeric_views 
            cleaned_videos.append(video)
        else:
            if status:
                status.update(f"[yellow]Skipping video '{video.get('title', 'Unknown')}' due to low views, no views, or exceeding max duration.[/yellow]")

    sorted_videos = sorted(cleaned_videos, key=lambda x: x.get('parsed_views', 0), reverse=True)

    for video in sorted_videos:
        video.pop('parsed_views', None)

    try:
        with open(latest_json_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_videos, f, indent=2, ensure_ascii=False)
        if status:
            status.update(f"[white]Cleaned and sorted {len(sorted_videos)} videos saved to {latest_json_path}. Removed {initial_count - len(sorted_videos)} videos.[/white]")
        else:
            _log(f"Cleaned and sorted {len(sorted_videos)} videos saved to {latest_json_path}. Removed {initial_count - len(sorted_videos)} videos.", verbose)
    except Exception as e:
        if status:
            status.update(f"[bold red]Error saving cleaned and sorted video data to {latest_json_path}: {e}[/bold red]")
        else:
            _log(f"Error saving cleaned and sorted video data to {latest_json_path}: {e}", verbose, is_error=True) 