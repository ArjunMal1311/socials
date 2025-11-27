import os
import json

from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_file_path, ensure_dir_exists

console = Console()

def save_tweet_schedules(schedules, profile_name="Default", verbose: bool = False):
    schedule_file_path = get_schedule_file_path(profile_name)
    ensure_dir_exists(os.path.dirname(schedule_file_path))
    
    with open(schedule_file_path, 'w') as f:
        json.dump(schedules, f, indent=2)
    log(f"Tweet schedules saved to {schedule_file_path}", verbose, log_caller_file="save_tweet_schedules.py")
