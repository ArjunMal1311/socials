import os
import json
import random

from typing import Dict, Any
from datetime import datetime, timedelta

from profiles import PROFILES

from services.support.path_config import get_schedule_file_path
from services.platform.x.support.process_scheduled_tweets import process_scheduled_tweets
from services.utils.suggestions.support.x.scraping_utils import get_latest_suggestions_file

def run_content_scheduling(profile_name: str) -> Dict[str, Any]:
    suggestions_file = get_latest_suggestions_file(profile_name)
    if not suggestions_file:
        return {"error": "No suggestions content found. Run 'generate' command first."}

    try:
        with open(suggestions_file, 'r') as f:
            suggestions_data = json.load(f)

        generated_posts = suggestions_data.get('generated_posts', [])
        if not generated_posts:
            return {"error": "No generated posts found in the file."}

        profile_props = PROFILES[profile_name].get('properties', {})
        verbose = profile_props.get('verbose', False)

        gap_type = profile_props.get('gap_type', 'random')
        min_gap_hours = profile_props.get('min_gap_hours', 0)
        min_gap_minutes = profile_props.get('min_gap_minutes', 1)
        max_gap_hours = profile_props.get('max_gap_hours', 0)
        max_gap_minutes = profile_props.get('max_gap_minutes', 50)
        fixed_gap_hours = profile_props.get('fixed_gap_hours', 2)
        fixed_gap_minutes = profile_props.get('fixed_gap_minutes', 0)

        gap_minutes_min = min_gap_hours * 60 + min_gap_minutes
        gap_minutes_max = max_gap_hours * 60 + max_gap_minutes
        fixed_gap_minutes = fixed_gap_hours * 60 + fixed_gap_minutes

        schedule_file = get_schedule_file_path(profile_name)
        os.makedirs(os.path.dirname(schedule_file), exist_ok=True)

        existing_schedule = []
        if os.path.exists(schedule_file):
            try:
                with open(schedule_file, 'r') as f:
                    existing_schedule = json.load(f)
            except:
                existing_schedule = []

        current_time = datetime.now()

        if existing_schedule:
            latest_scheduled_time = max([datetime.strptime(entry['scheduled_time'], "%Y-%m-%d %H:%M:%S") for entry in existing_schedule if 'scheduled_time' in entry], default=datetime.min)
            current_time = max(current_time, latest_scheduled_time)

        tomorrow_start_of_day = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        current_time = max(current_time, tomorrow_start_of_day)

        current_time += timedelta(minutes=1)

        scheduled_posts = []

        for post in generated_posts:
            if not post.get('generated_caption', '').strip():
                continue

            if gap_type == 'random':
                gap_minutes = random.randint(gap_minutes_min, gap_minutes_max)
            else:
                gap_minutes = fixed_gap_minutes

            scheduled_time = current_time + timedelta(minutes=gap_minutes)
            current_time = scheduled_time

            media_paths = post.get('downloaded_media_paths', [])
            media_paths = [path for path in media_paths if path is not None] if post.get('downloaded_media_paths') else []

            if media_paths:
                project_root = os.getcwd()
                media_paths = [os.path.relpath(path, project_root) if os.path.isabs(path) else path for path in media_paths]

            schedule_entry = {
                "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                "scheduled_tweet": post['generated_caption'],
                "scheduled_image": media_paths,
                "community_posted": False,
                "community_posted_at": None,
                "community-tweet": ""
            }

            scheduled_posts.append(schedule_entry)
            post['finalized'] = True

        if scheduled_posts:
            existing_schedule.extend(scheduled_posts)

            with open(schedule_file, 'w') as f:
                json.dump(existing_schedule, f, indent=2)

            with open(suggestions_file, 'w') as f:
                json.dump(suggestions_data, f, indent=2)

            return {
                "success": True,
                "scheduled_count": len(scheduled_posts),
                "schedule_file": schedule_file
            }
        else:
            return {"success": True, "scheduled_count": 0, "message": "No new posts to schedule"}

    except Exception as e:
        return {"error": f"Error during content scheduling: {str(e)}"}

def run_content_posting(profile_name: str) -> Dict[str, Any]:
    schedule_file = get_schedule_file_path(profile_name)
    if not os.path.exists(schedule_file):
        return {"error": "No scheduled content found. Run 'schedule' command first."}

    try:
        from profiles import PROFILES
        profile_props = PROFILES[profile_name].get('properties', {})
        verbose = profile_props.get('verbose', False)
        headless = profile_props.get('headless', False)

        process_scheduled_tweets(profile_name, verbose=verbose, headless=headless)

        return {"success": True, "message": f"Posting session completed for {profile_name}"}

    except KeyboardInterrupt:
        return {"success": True, "message": "Posting stopped by user"}
    except Exception as e:
        return {"error": f"Error during content posting: {str(e)}"}
