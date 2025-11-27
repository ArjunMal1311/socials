import os

from typing import Optional
from datetime import datetime
from rich.console import Console
from services.support.logger_util import _log as log

console = Console()


def get_latest_dated_json_file(directory: str, prefix: str, verbose: bool = False) -> Optional[str]:
    latest_json_path = None
    latest_date = None

    if not os.path.exists(directory):
        log(f"Directory does not exist: {directory}", verbose, log_caller_file="file_manager.py")
        return None

    log(f"Searching for JSON files with prefix '{prefix}' in {directory}", verbose, log_caller_file="file_manager.py")
    
    for f in os.listdir(directory):
        if f.startswith(prefix) and f.endswith('.json'):
            try:
                date_part = f.replace(prefix, '').replace('.json', '').strip('_')
                if len(date_part) == 15:
                    current_date = datetime.strptime(date_part, '%Y%m%d_%H%M%S').date()
                    if latest_date is None or current_date > latest_date:
                        latest_date = current_date
                        latest_json_path = os.path.join(directory, f)
                        log(f"Found newer file: {f} (date: {current_date})", verbose, log_caller_file="file_manager.py")
            except ValueError:
                log(f"Skipping file with invalid date format: {f}", verbose, log_caller_file="file_manager.py")
                continue
    
    if latest_json_path:
        log(f"Latest JSON file found: {latest_json_path}", verbose, log_caller_file="file_manager.py")
    else:
        log(f"No JSON files found with prefix '{prefix}'", verbose, log_caller_file="file_manager.py")
    
    return latest_json_path
