import os
import json

from rich.console import Console

from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_file_path, ensure_dir_exists

console = Console()

def save_tweet_schedules(schedules, profile_name="Default", verbose: bool = False):
    schedule_file_path = get_schedule_file_path(profile_name)
    ensure_dir_exists(os.path.dirname(schedule_file_path))
    
    with open(schedule_file_path, 'r+') as f:
        try:
            all_schedules = json.load(f)
        except json.JSONDecodeError:
            all_schedules = []
        
        schedule_map = {(s['scheduled_time'], s['scheduled_tweet']): s for s in all_schedules}

        updated_count = 0
        for new_schedule_entry in schedules:
            key = (new_schedule_entry['scheduled_time'], new_schedule_entry['scheduled_tweet'])
            if key in schedule_map:
                schedule_map[key].update(new_schedule_entry)
                updated_count += 1
            else:
                all_schedules.append(new_schedule_entry)
                updated_count += 1
        
        f.seek(0)
        json.dump(all_schedules, f, indent=2)
        f.truncate()
        
    log(f"Updated {updated_count} tweet schedules in {schedule_file_path}", verbose, log_caller_file="save_tweet_schedules.py")
