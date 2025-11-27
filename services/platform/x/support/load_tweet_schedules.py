import os
import re
import json

from datetime import datetime
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_file_path

console = Console()

def load_tweet_schedules(profile_name="Default", verbose: bool = False, status=None):
    schedule_file_path = get_schedule_file_path(profile_name)
    
    if not os.path.exists(schedule_file_path):
        log("Schedule file not found, returning empty list", verbose, status=status, log_caller_file="load_tweet_schedules.py")
        return []
    
    with open(schedule_file_path, 'r') as f:
        try:
            schedules = json.load(f)
            return sorted(schedules, key=lambda x: datetime.strptime(x['scheduled_time'], '%Y-%m-%d %H:%M:%S'))
        except json.JSONDecodeError:
            log("Invalid JSON in schedule file, returning empty list", verbose, is_error=True, status=status, log_caller_file="load_tweet_schedules.py")

            return []
