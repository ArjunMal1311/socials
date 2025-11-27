import os

from datetime import datetime
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_youtube_profile_dir

console = Console()

def get_latest_dated_json_file(profile_name: str, prefix: str, verbose: bool = False) -> Optional[str]:
    youtube_profile_dir = get_youtube_profile_dir(profile_name)
    latest_json_path = None
    latest_date = None

    if not os.path.exists(youtube_profile_dir):
        log(f"Profile directory does not exist: {youtube_profile_dir}", verbose, log_caller_file="get_latest_dated_json_file.py")
        return None

    log(f"Searching for JSON files with prefix '{prefix}' in {youtube_profile_dir}", verbose, log_caller_file="get_latest_dated_json_file.py")
    
    for f in os.listdir(youtube_profile_dir):
        if f.startswith(prefix) and f.endswith('.json'):
            try:
                date_part = f.replace(prefix, '').replace('.json', '').strip('_')
                if len(date_part) == 8:
                    current_date = datetime.strptime(date_part, '%Y%m%d').date()
                    if latest_date is None or current_date > latest_date:
                        latest_date = current_date
                        latest_json_path = os.path.join(youtube_profile_dir, f)
                        log(f"Found newer file: {f} (date: {current_date})", verbose, log_caller_file="get_latest_dated_json_file.py")
            except ValueError:
                log(f"Skipping file with invalid date format: {f}", verbose, log_caller_file="get_latest_dated_json_file.py")
                continue
    
    if latest_json_path:
        log(f"Latest JSON file found: {latest_json_path}", verbose, log_caller_file="get_latest_dated_json_file.py")
    else:
        log(f"No JSON files found with prefix '{prefix}'", verbose, log_caller_file="get_latest_dated_json_file.py")
    
    return latest_json_path
