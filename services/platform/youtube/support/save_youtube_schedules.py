import os
import re
import json

from datetime import datetime
from rich.console import Console
from typing import Optional, Dict, Any
from services.support.path_config import get_youtube_schedule_videos_dir

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
        console.print(f"[save_youtube_schedules.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[save_youtube_schedules.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def save_youtube_schedules(schedule_data, profile_name="Default", verbose: bool = False):
    schedule_dir = get_youtube_schedule_videos_dir(profile_name)
    schedule_file = os.path.join(schedule_dir, 'youtube_schedule.json')

    if not os.path.exists(schedule_dir):
        os.makedirs(schedule_dir)

    with open(schedule_file, 'w') as f:
        json.dump(schedule_data, f, indent=4)
    _log(f"YouTube schedule saved to: {schedule_file}", verbose) 