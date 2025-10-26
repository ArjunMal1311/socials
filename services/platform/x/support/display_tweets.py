import re
import os

from datetime import datetime
from rich.console import Console
from services.support.path_config import get_schedule_dir
from services.platform.x.support.load_tweet_schedules import load_tweet_schedules

console = Console()

def _log(message: str, verbose: bool, is_error: bool = False):
    if verbose or is_error:
        log_message = message
        if is_error and not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red" if is_error else "white"
        console.print(f"[display_tweets.py] {timestamp}|[{color}]{log_message}[/{color}]")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[display_tweets.py] {timestamp}|[{color}]{message}[/{color}]")

def display_scheduled_tweets(profile_name="Default", verbose: bool = False):
    _log(f"Displaying scheduled tweets for profile: {profile_name}", verbose)
    scheduled_tweets = load_tweet_schedules(profile_name, verbose=verbose)
    if not scheduled_tweets:
        _log("No tweets scheduled yet.", verbose)
        return
    
    schedule_folder = get_schedule_dir(profile_name)
    if not os.path.exists(schedule_folder):
        _log(f"Schedule folder not found at {schedule_folder}. Local media will not be displayed.", verbose)

    for i, tweet in enumerate(scheduled_tweets):
        _log(f"--- Tweet {i+1} ---", verbose)
        _log(f"Scheduled Time: {tweet['scheduled_time']}", verbose)
        _log(f"Tweet Text: {tweet['scheduled_tweet']}", verbose)
        media_url = tweet.get('scheduled_image')
        if media_url:
            if media_url.startswith('http'):
                _log(f"Media URL: {media_url}", verbose)
            else:
                if os.path.exists(schedule_folder):
                    local_media_path = os.path.join(schedule_folder, media_url)
                    if os.path.exists(local_media_path):
                        _log(f"Local Media Path: {local_media_path}", verbose)
                    else:
                        _log(f"Local media file not found: {media_url} in {schedule_folder}", verbose)
                else:
                    _log(f"Cannot display local media: Schedule folder {schedule_folder} does not exist.", verbose) 