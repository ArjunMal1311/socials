import os

from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_dir
from services.platform.x.support.load_tweet_schedules import load_tweet_schedules

console = Console()

def display_scheduled_tweets(profile_name="Default", verbose: bool = False):
    log(f"Displaying scheduled tweets for profile: {profile_name}", verbose, log_caller_file="display_tweets.py")
    scheduled_tweets = load_tweet_schedules(profile_name, verbose=verbose)
    if not scheduled_tweets:
        log("No tweets scheduled yet.", verbose, log_caller_file="display_tweets.py")
        return
    
    schedule_folder = get_schedule_dir(profile_name)
    if not os.path.exists(schedule_folder):
        log(f"Schedule folder not found at {schedule_folder}. Local media will not be displayed.", verbose, log_caller_file="display_tweets.py")

    for i, tweet in enumerate(scheduled_tweets):
        log(f"--- Tweet {i+1} ---", verbose, log_caller_file="display_tweets.py")
        log(f"Scheduled Time: {tweet['scheduled_time']}", verbose, log_caller_file="display_tweets.py")
        log(f"Tweet Text: {tweet['scheduled_tweet']}", verbose, log_caller_file="display_tweets.py")
        media_url = tweet.get('scheduled_image')
        if media_url:
            if media_url.startswith('http'):
                log(f"Media URL: {media_url}", verbose, log_caller_file="display_tweets.py")
            else:
                if os.path.exists(schedule_folder):
                    local_media_path = os.path.join(schedule_folder, media_url)
                    if os.path.exists(local_media_path):
                        log(f"Local Media Path: {local_media_path}", verbose, log_caller_file="display_tweets.py")
                    else:
                        log(f"Local media file not found: {media_url} in {schedule_folder}", verbose, log_caller_file="display_tweets.py")
                else:
                    log(f"Cannot display local media: Schedule folder {schedule_folder} does not exist.", verbose, log_caller_file="display_tweets.py") 