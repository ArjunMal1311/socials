import os
import json
import random

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from profiles import PROFILES

from services.support.storage.base_storage import BaseStorage
from services.support.logger_util import _log as log


from services.support.path_config import get_schedule_file_path, get_suggestions_dir
from services.platform.x.support.process_scheduled_tweets import process_scheduled_tweets

def run_content_scheduling(profile_name: str, storage_generated: Optional[BaseStorage] = None, storage_new: Optional[BaseStorage] = None) -> Dict[str, Any]:
    profile_props = PROFILES[profile_name].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)

    generated_posts = []
    if storage_generated and storage_new:
        log(f"Fetching approved generated captions from database for {profile_name}", verbose, log_caller_file="scheduling_utils.py")
        approved_generated_captions = storage_generated.pull_approved_content(batch_id="", verbose=verbose) # batch_id is not relevant for pulling all approved
        for item in approved_generated_captions:
            generated_posts.append({
                'content_id': item.get('content_id'),
                'generated_caption': item.get('generated_caption', ''),
                'platform': 'x',
                'downloaded_media_paths': item.get('media_urls', []),
                'type': 'generated_caption',
                'db_id': item.get('id')
            })

        log(f"Fetching approved new content from database for {profile_name}", verbose, log_caller_file="scheduling_utils.py")
        approved_new_content_raw = storage_new.get_batch_content(batch_id="", verbose=verbose)
        approved_new_content = [item for item in approved_new_content_raw if item.get('approved') and item.get('review_status') == 'approved']


        for item in approved_new_content:
            if item.get('approved'):
                generated_posts.append({
                    'content_id': item.get('generated_text_id'),
                    'generated_caption': item.get('generated_text', ''),
                    'platform': 'x',
                    'downloaded_media_paths': [],
                    'type': 'new_content',
                    'db_id': item.get('id')
                })

        if not generated_posts:
            return {"error": "No approved content found in the database. Please review and approve content first."}

    else:
        suggestions_dir = get_suggestions_dir(profile_name)
        approved_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_') and f.endswith('.json')]
        approved_files.sort(reverse=True)

        approved_content_from_files = []
        for file in approved_files:
            try:
                with open(os.path.join(suggestions_dir, file), 'r') as f:
                    data = json.load(f)
                    if 'generated_posts' in data:
                        for post in data['generated_posts']:
                            if post.get('generated_caption') and post.get('finalized') is False:
                                approved_content_from_files.append({
                                    'content_id': post.get('tweet_id'),
                                    'generated_caption': post.get('generated_caption', ''),
                                    'platform': 'x',
                                    'downloaded_media_paths': post.get('downloaded_media_paths', []),
                                    'type': 'generated_caption'
                                })
            except Exception as e:
                log(f"Error loading suggestions file {file}: {e}", verbose, log_caller_file="scheduling_utils.py")

        new_tweets_files = [f for f in os.listdir(suggestions_dir) if f.startswith('new_tweets_content_x_') and f.endswith('.json')]
        new_tweets_files.sort(reverse=True)

        for file in new_tweets_files:
            try:
                with open(os.path.join(suggestions_dir, file), 'r') as f:
                    data = json.load(f)
                    if 'new_tweets' in data:
                        for tweet in data['new_tweets']:
                            if tweet.get('approved') and tweet.get('scheduled') is not True:
                                approved_content_from_files.append({
                                    'content_id': tweet.get('id'),
                                    'generated_caption': tweet.get('text', ''),
                                    'platform': 'x',
                                    'downloaded_media_paths': [],
                                    'type': 'new_content'
                                })
            except Exception as e:
                log(f"Error loading new tweets file {file}: {e}", verbose, log_caller_file="scheduling_utils.py")

        generated_posts = approved_content_from_files

        if not generated_posts:
            return {"error": "No approved content found in files. Run 'generate' and 'review' commands first."}

        profile_props = PROFILES[profile_name].get('properties', {})
        global_props = profile_props.get('global', {})
        verbose = global_props.get('verbose', False)

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

    try:
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

def run_content_posting(profile_name: str, storage_generated: Optional[BaseStorage] = None, storage_new: Optional[BaseStorage] = None) -> Dict[str, Any]:
    schedule_file = get_schedule_file_path(profile_name)
    if not os.path.exists(schedule_file):
        return {"error": "No scheduled content found. Run 'schedule' command first."}

    try:
        profile_props = PROFILES[profile_name].get('properties', {})
        global_props = profile_props.get('global', {})
        verbose = global_props.get('verbose', False)
        headless = profile_props.get('headless', False)

        with open(schedule_file, 'r') as f:
            all_scheduled = json.load(f)
        
        posts_to_process = [post for post in all_scheduled if not post.get('community_posted')]

        if not posts_to_process:
            return {"success": True, "message": "No new posts to process for posting."}

        processed_results = process_scheduled_tweets(profile_name, verbose=verbose, headless=headless)

        if processed_results.get("success"):
            posted_content_ids = processed_results.get("posted_content_ids", [])
            if storage_generated and storage_new:
                for post in all_scheduled:
                    if post.get('content_id') in posted_content_ids:
                        if post.get('type') == 'generated_caption':
                            storage_generated.update_status(content_id=post['content_id'], status='posted', verbose=verbose)
                        elif post.get('type') == 'new_content':
                            storage_new.update_status(generated_text_id=post['content_id'], status='posted', additional_updates={'approved': True}, verbose=verbose)

            for post in all_scheduled:
                if post.get('content_id') in posted_content_ids:
                    post['community_posted'] = True
                    post['community_posted_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with open(schedule_file, 'w') as f:
                json.dump(all_scheduled, f, indent=2)

            return {"success": True, "message": f"Posting session completed for {profile_name}. {len(posted_content_ids)} posts were posted."}
        else:
            return {"error": f"Posting failed: {processed_results.get('error', 'Unknown error')}"}

    except KeyboardInterrupt:
        return {"success": True, "message": "Posting stopped by user"}
    except Exception as e:
        return {"error": f"Error during content posting: {str(e)}"}
