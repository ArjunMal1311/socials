import os
import json

from rich.console import Console
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from services.support.logger_util import _log as log
from services.platform.x.support.save_tweet_schedules import save_tweet_schedules
from services.support.path_config import get_schedule_file_path, get_schedule2_file_path

console = Console()

def _paths(profile_name: str) -> Tuple[str, str, str]:
    schedule_json = get_schedule_file_path(profile_name)
    schedule2_json = get_schedule2_file_path(profile_name)
    base_dir = os.path.dirname(schedule_json)
    return base_dir, schedule_json, schedule2_json

def _load_json(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def move_tomorrows_from_schedule2(profile_name: str = "Default", verbose: bool = False, status=None) -> int:
    _, schedule_json, schedule2_json = _paths(profile_name)

    schedule2_items = _load_json(schedule2_json)
    
    
    if not schedule2_items:
        alt = schedule2_json.replace('schedule2.json', 'schedule_2.json')
        if os.path.basename(alt) != os.path.basename(schedule2_json):
            schedule2_items = _load_json(alt)
            if schedule2_items:
                schedule2_json = alt
                
    save_tweet_schedules([], profile_name)

    if not schedule2_items:
        log(f"Cleared schedule.json. No schedule2.json items found for profile '{profile_name}'.", verbose, status=status, log_caller_file="move_tomorrow_schedules.py")
        return 0

    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    to_move: List[Dict] = []

    for item in schedule2_items:
        ts = item.get('scheduled_time')
        if not ts:
            continue
        try:
            dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue
        if dt.strftime('%Y-%m-%d') == tomorrow_date:
            to_move.append(item)

    if not to_move:
        log(f"Cleared schedule.json. No tweets for tomorrow found in schedule2.json for profile '{profile_name}'. schedule2.json left unchanged.", verbose, status=status, log_caller_file="move_tomorrow_schedules.py")
        return 0

    merged = list(to_move)
    try:
        merged.sort(key=lambda x: datetime.strptime(x['scheduled_time'], '%Y-%m-%d %H:%M:%S'))
    except Exception:
        pass

    save_tweet_schedules(merged, profile_name)

    log(f"Cleared current schedule and copied {len(to_move)} tweet(s) for {tomorrow_date} from schedule2.json to schedule.json for profile '{profile_name}'. schedule2.json left unchanged.", verbose, status=status, log_caller_file="move_tomorrow_schedules.py")
    return len(to_move)


