import os

from datetime import datetime
from rich.console import Console
from typing import Optional, Dict, Any
from services.support.path_config import get_youtube_profile_dir

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Any] = None, api_info: Optional[Dict[str, Any]] = None):
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

def get_latest_dated_json_file(profile_name: str, prefix: str, verbose: bool = False) -> Optional[str]:
    youtube_profile_dir = get_youtube_profile_dir(profile_name)
    latest_json_path = None
    latest_date = None

    if not os.path.exists(youtube_profile_dir):
        _log(f"Profile directory does not exist: {youtube_profile_dir}", verbose)
        return None

    _log(f"Searching for JSON files with prefix '{prefix}' in {youtube_profile_dir}", verbose)
    
    for f in os.listdir(youtube_profile_dir):
        if f.startswith(prefix) and f.endswith('.json'):
            try:
                date_part = f.replace(prefix, '').replace('.json', '').strip('_')
                if len(date_part) == 8:
                    current_date = datetime.strptime(date_part, '%Y%m%d').date()
                    if latest_date is None or current_date > latest_date:
                        latest_date = current_date
                        latest_json_path = os.path.join(youtube_profile_dir, f)
                        _log(f"Found newer file: {f} (date: {current_date})", verbose)
            except ValueError:
                _log(f"Skipping file with invalid date format: {f}", verbose)
                continue
    
    if latest_json_path:
        _log(f"Latest JSON file found: {latest_json_path}", verbose)
    else:
        _log(f"No JSON files found with prefix '{prefix}'", verbose)
    
    return latest_json_path
