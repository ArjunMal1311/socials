import os
import sys
import json
import time
import subprocess

from profiles import PROFILES

from datetime import datetime
from rich.status import Status
from rich.console import Console
from services.support import path_config
from services.support.logger_util import _log as log

console = Console()

def load_schedule(profile_name: str) -> list:
    schedule_path = path_config.get_schedule_file_path(profile_name)
    if not os.path.exists(schedule_path):
        return []
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_schedule(profile_name: str, schedule: list) -> None:
    schedule_path = path_config.get_schedule_file_path(profile_name)
    tmp_path = schedule_path + ".tmp"
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, schedule_path)


def post_tweet(profile_key: str, tweet_text: str, community_name: str = None, verbose: bool = False) -> bool:
    cmd = [
        "python3",
        os.path.join(os.path.dirname(__file__), '..', 'replies.py'),
        "--profile", profile_key,
    ]
    if community_name:
        cmd.extend([
            "--post-to-community",
            "--post-to-community-tweet", tweet_text,
            "--community-name", community_name,
        ])
    else:
        cmd.extend([
            "--post-tweet", tweet_text,
        ])

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            log(result.stdout.strip(), verbose=verbose, log_caller_file="post_watcher.py")
        if result.stderr:
            log(result.stderr.strip(), verbose=verbose, is_error=True, log_caller_file="post_watcher.py")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to post tweet for profile '{profile_key}': {e.stderr}", verbose=verbose, is_error=True, log_caller_file="post_watcher.py")
        return False


def process_profile(profile_key: str, start_dt: datetime, verbose: bool = False) -> int:
    posts_to_process = load_schedule(profile_key)
    if not isinstance(posts_to_process, list):
        if verbose:
            log(f"{profile_key}: schedule not found or invalid at {path_config.get_schedule_file_path(profile_key)} (Expected a list, got {type(posts_to_process)}).", verbose, log_caller_file="post_watcher.py")
        return 0

    if verbose:
        log(f"{profile_key}: scanning schedule at {path_config.get_schedule_file_path(profile_key)} (start_dt={start_dt.isoformat()})", verbose, log_caller_file="post_watcher.py")

    posted_count = 0
    updated_posts = []

    for post in posts_to_process:
        if not isinstance(post, dict):
            if verbose:
                log(f"{profile_key}: non-dict post, skipping", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        community_name = post.get("community-tweet")
        already_posted = post.get("community_posted") is True
        tweet_text = post.get("x_captions", "").strip() or post.get("scheduled_tweet", "").strip()
        scheduled_time_str = post.get("scheduled_time", "").strip()

        if not scheduled_time_str:
            if verbose:
                log(f"{profile_key}: post has no scheduled_time, skipping", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        try:
            post_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                post_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                if verbose:
                    log(f"{profile_key}: invalid scheduled_time format '{scheduled_time_str}', skipping", verbose, log_caller_file="post_watcher.py")
                updated_posts.append(post)
                continue

        if post_dt.date() != datetime.now().date():
            if verbose:
                log(f"{profile_key}: NOT-TODAY skip {post_dt.isoformat()} (community={community_name})", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        if post_dt < start_dt:
            if verbose:
                log(f"{profile_key}: BEFORE-START skip {post_dt.isoformat()} < {start_dt.isoformat()} (community={community_name})", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        now_dt = datetime.now()
        if post_dt > now_dt:
            if verbose:
                log(f"{profile_key}: WAIT {post_dt.isoformat()} > {now_dt.isoformat()} (community={community_name})", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        if already_posted:
            if verbose:
                log(f"{profile_key}: already posted item at {post_dt.isoformat()}, skipping", verbose, log_caller_file="post_watcher.py")
            updated_posts.append(post)
            continue

        if not tweet_text:
            log(f"Skipping empty tweet for '{profile_key}' at {post_dt.strftime('%Y-%m-%d %H:%M')}.", verbose, is_error=True, log_caller_file="post_watcher.py")
            post["community_posted"] = True
            post["community_posted_at"] = datetime.now().isoformat()
            updated_posts.append(post)
            continue
        
        if community_name:
            log(f"Posting community tweet for '{profile_key}' in '{community_name}' at {post_dt.strftime('%Y-%m-%d %H:%M')}.", verbose, log_caller_file="post_watcher.py")
            success = post_tweet(profile_key, tweet_text, community_name, verbose=verbose)
        else:
            log(f"Posting regular tweet for '{profile_key}' at {post_dt.strftime('%Y-%m-%d %H:%M')}.", verbose, log_caller_file="post_watcher.py")
            success = post_tweet(profile_key, tweet_text, verbose=verbose)

        if success:
            posted_count += 1
            post["community_posted"] = True
            post["community_posted_at"] = datetime.now().isoformat()
        updated_posts.append(post)

    if posted_count > 0:
        save_schedule(profile_key, updated_posts)

    return posted_count


def has_future_posts(profile_key: str, start_dt: datetime, verbose: bool = False) -> bool:
    posts_to_check = load_schedule(profile_key)
    if not isinstance(posts_to_check, list):
        return False

    now_dt = datetime.now()

    for post in posts_to_check:
        if not isinstance(post, dict):
            continue

        is_community_tweet = post.get("community-tweet")
        
        if post.get("community_posted") is True:
            continue

        scheduled_time_str = post.get("scheduled_time", "").strip()
        if not scheduled_time_str:
            continue

        try:
            post_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                post_dt = datetime.strptime(scheduled_time_str, "%Y-%m-%d %H:%M")
            except ValueError:
                continue

        if post_dt.date() != datetime.now().date():
            if verbose:
                log(f"{profile_key}: NOT-TODAY skip {post_dt.isoformat()} (community={is_community_tweet})", verbose, log_caller_file="post_watcher.py")
            continue

        if post_dt >= start_dt and post_dt >= now_dt:
            if verbose:
                log(f"{profile_key}: future post pending at {post_dt.isoformat()} (community={is_community_tweet})", verbose, log_caller_file="post_watcher.py")
            return True
    return False


def run_watcher(profile_keys: list[str], interval_seconds: int, run_once: bool, verbose: bool = False):
    if not profile_keys:
        log("No profiles provided.", verbose, is_error=True, log_caller_file="post_watcher.py")
        sys.exit(1)

    for key in profile_keys:
        if key not in PROFILES:
            log(f"Warning: Profile key '{key}' not found in PROFILES. Continuing...", verbose, is_error=True, log_caller_file="post_watcher.py")

    log("Community Post Watcher started. Press Ctrl+C to stop.", verbose, log_caller_file="post_watcher.py")

    def scan_and_post() -> tuple[int, bool]:
        total_posted = 0
        any_future_pending = False
        with Status("[white]Scanning schedules for community tweets...[/white]", spinner="dots", console=console) as status:
            for key in profile_keys:
                status.update(f"[white]Processing {key}...[/white]")
                try:
                    total_posted += process_profile(key, start_dt, verbose=verbose)
                    if has_future_posts(key, start_dt, verbose=verbose):
                        any_future_pending = True
                except Exception as e:
                    log(f"Error processing profile '{key}': {e}", verbose, is_error=True, log_caller_file="post_watcher.py")
            status.stop()
        if total_posted:
            log(f"Posted {total_posted} post(s).", verbose, log_caller_file="post_watcher.py")
        else:
            log("No posts to make.", verbose, log_caller_file="post_watcher.py")
        return total_posted, any_future_pending

    if run_once:
        _, any_future = scan_and_post()
        if not any_future:
            log("No future posts remaining. Exiting.", verbose, log_caller_file="post_watcher.py")
        return

    start_dt = datetime.now()
    try:
        while True:
            _, any_future = scan_and_post()
            if not any_future:
                log("No future posts remaining. Exiting watcher.", verbose, log_caller_file="post_watcher.py")
                break
            wait_seconds = max(5, interval_seconds)
            with Status("[white]Waiting before next scan...[/white]", spinner="dots", console=console) as wait_status:
                for remaining in range(wait_seconds, 0, -1):
                    wait_status.update(f"[white]Waiting {remaining} seconds before next scan...[/white]")
                    time.sleep(1)
                wait_status.stop()
    except KeyboardInterrupt:
        log("Community Post Watcher stopped.", verbose, log_caller_file="post_watcher.py")
