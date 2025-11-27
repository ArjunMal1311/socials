import os
import json

from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_youtube_schedule_videos_dir

console = Console()

def load_youtube_schedules(profile_name="Default", verbose: bool = False):
    schedule_dir = get_youtube_schedule_videos_dir(profile_name)
    schedule_file = os.path.join(schedule_dir, 'youtube_schedule.json')

    if not os.path.exists(schedule_dir):
        os.makedirs(schedule_dir)
        log(f"Created schedule directory: {schedule_dir}", verbose, log_caller_file="load_youtube_schedules.py")

    if not os.path.exists(schedule_file):
        with open(schedule_file, 'w') as f:
            json.dump([], f)
        log(f"Created empty schedule file: {schedule_file}", verbose, log_caller_file="load_youtube_schedules.py")
        return []

    with open(schedule_file, 'r') as f:
        return json.load(f) 