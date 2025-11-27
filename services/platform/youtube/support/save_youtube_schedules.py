import os
import json

from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_youtube_schedule_videos_dir

console = Console()

def save_youtube_schedules(schedule_data, profile_name="Default", verbose: bool = False):
    schedule_dir = get_youtube_schedule_videos_dir(profile_name)
    schedule_file = os.path.join(schedule_dir, 'youtube_schedule.json')

    if not os.path.exists(schedule_dir):
        os.makedirs(schedule_dir)

    with open(schedule_file, 'w') as f:
        json.dump(schedule_data, f, indent=4)
    log(f"YouTube schedule saved to: {schedule_file}", verbose, log_caller_file="save_youtube_schedules.py") 