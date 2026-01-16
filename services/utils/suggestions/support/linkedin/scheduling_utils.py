import os
import json
import random

from typing import Dict, Any
from datetime import datetime, timedelta

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_schedule_file_path, get_suggestions_dir, get_browser_data_dir

from services.platform.linkedin.post import create_linkedin_post
from services.utils.suggestions.support.linkedin.scraping_utils import get_latest_linkedin_suggestions_file

def run_linkedin_content_scheduling(profile_name: str) -> Dict[str, Any]:
    suggestions_dir = get_suggestions_dir(profile_name)
    approved_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_linkedin_') and f.endswith('.json')]
    approved_files.sort(reverse=True)

    approved_content = []
    for file in approved_files:
        try:
            with open(os.path.join(suggestions_dir, file), 'r') as f:
                data = json.load(f)
                if 'approved_content' in data:
                    approved_content.extend(data['approved_content'])
        except Exception as e:
            log(f"Error loading suggestions file {file}: {e}", verbose=False, log_caller_file="scheduling_utils.py")

    if not approved_content:
        suggestions_file = get_latest_linkedin_suggestions_file(profile_name)
        if not suggestions_file:
            return {"error": "No suggestions content found. Run 'generate' and 'review' commands first."}

        try:
            with open(suggestions_file, 'r') as f:
                suggestions_data = json.load(f)

            generated_posts = suggestions_data.get('generated_posts', [])
            if not generated_posts:
                return {"error": "No generated posts found in the file."}
        except Exception as e:
            return {"error": f"Error loading suggestions file: {e}"}
    else:
        generated_posts = []
        for item in approved_content:
            if item['type'] == 'approved_post':
                post = item['content']
                generated_posts.append({
                    'generated_caption': post.get('generated_caption', ''),
                    'platform': item['platform'],
                    'downloaded_media_paths': post.get('downloaded_media_paths', [])
                })
            elif item['type'] == 'new_content':
                content = item['content']
                generated_posts.append({
                    'generated_caption': content.get('text', ''),
                    'platform': item['platform'],
                    'downloaded_media_paths': []
                })

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

    try:
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
                "scheduled_post": post['generated_caption'],
                "scheduled_image": media_paths,
                "posted": False,
                "posted_at": None,
                "platform": "linkedin"
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

def run_linkedin_content_posting(profile_name: str) -> Dict[str, Any]:
    schedule_file = get_schedule_file_path(profile_name)
    if not os.path.exists(schedule_file):
        return {"error": "No scheduled content found. Run 'schedule' command first."}

    try:
        profile_props = PROFILES[profile_name].get('properties', {})
        verbose = profile_props.get('verbose', False)
        headless = profile_props.get('headless', False)

        user_data_dir = get_browser_data_dir(profile_name)
        driver = setup_driver(user_data_dir, profile=profile_name, headless=headless, verbose=verbose)

        with open(schedule_file, 'r') as f:
            schedule_data = json.load(f)

        posted_count = 0
        for entry in schedule_data:
            if entry.get('posted', False) or entry.get('platform') != 'linkedin':
                continue

            scheduled_time = datetime.strptime(entry['scheduled_time'], "%Y-%m-%d %H:%M:%S")
            if datetime.now() < scheduled_time:
                continue

            post_text = entry.get('scheduled_post', '')
            media_urls = entry.get('scheduled_image', [])

            if post_text:
                success = create_linkedin_post(driver, post_text, media_urls, verbose=verbose)
                if success:
                    entry['posted'] = True
                    entry['posted_at'] = datetime.now().isoformat()
                    posted_count += 1
                else:
                    break

        with open(schedule_file, 'w') as f:
            json.dump(schedule_data, f, indent=2)

        if driver:
            driver.quit()

        return {"success": True, "message": f"Posted {posted_count} LinkedIn posts"}

    except KeyboardInterrupt:
        return {"success": True, "message": "Posting stopped by user"}
    except Exception as e:
        return {"error": f"Error during content posting: {str(e)}"}
