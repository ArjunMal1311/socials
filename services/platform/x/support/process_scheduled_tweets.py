import os
import json
import time

from rich.text import Text
from datetime import datetime
from rich.status import Status
from rich.console import Console

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_schedule_file_path

from services.platform.x.support.schedule_tweet import schedule_tweet
from services.platform.x.support.save_tweet_schedules import save_tweet_schedules

console = Console()

def process_scheduled_tweets(profile_name="Default", verbose: bool = False, headless: bool = True):
    log(f"Processing scheduled tweets for profile: {profile_name}", verbose, log_caller_file="process_scheduled_tweets.py")
    user_data_dir = get_browser_data_dir(profile_name)
    driver = None
    try:
        with Status("[white]Initializing WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless, verbose=verbose)
            for msg in setup_messages:
                status.update(Text(f"[white]{msg}[/white]"))
                time.sleep(0.1)
            status.update(Text("[white]WebDriver initialized.[/white]"))
            time.sleep(0.5)

            status.update(Text("Navigating to x.com/home...", style="white"))
            driver.get("https://x.com/home")
            status.update(Text("Checking for login redirect...", style="white"))

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.NAME, "text"))
                )
                status.update(Text("Redirected to login page. Waiting 30 seconds for manual login...", style="white"))
                time.sleep(30)
                status.update(Text("Resuming automated process after manual login window.", style="white"))
            except Exception:
                status.update(Text("Not redirected to login page or already logged in.", style="white"))
            time.sleep(1) 

        scheduled_tweets = load_tweet_schedules(profile_name, verbose=verbose)

        if not scheduled_tweets:
            log("No tweets scheduled yet.", verbose, log_caller_file="process_scheduled_tweets.py")
            return

        with Status("[white]Scheduling tweets...[/white]", spinner="dots", console=console) as status:
            for i, tweet in enumerate(scheduled_tweets):
                scheduled_time = tweet['scheduled_time']
                tweet_text = tweet['scheduled_tweet']
                media_file = tweet.get('scheduled_image')

                status.update(f"[white]Attempting to schedule tweet for {scheduled_time} with text '{tweet_text}'[/white]")

                success = schedule_tweet(driver, tweet_text, media_file, scheduled_time, profile_name, status, verbose=verbose)

                if success:
                    scheduled_tweets[i]['posted'] = True
                    scheduled_tweets[i]['posted_at'] = datetime.now().isoformat()
                    log(f"Tweet marked as posted: {scheduled_time}", verbose, log_caller_file="process_scheduled_tweets.py")
                else:
                    log(f"Failed to schedule tweet: {scheduled_time}", verbose, is_error=True, log_caller_file="process_scheduled_tweets.py")

                save_tweet_schedules(scheduled_tweets, profile_name, verbose=verbose)
                time.sleep(5)
        log("All scheduled tweets processed!", verbose, log_caller_file="process_scheduled_tweets.py")

    except Exception as e:
        log(f"An error occurred during tweet processing: {e}", verbose, is_error=True, log_caller_file="process_scheduled_tweets.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, log_caller_file="process_scheduled_tweets.py")

def load_tweet_schedules(profile_name="Default", verbose: bool = False, status=None):
    schedule_file_path = get_schedule_file_path(profile_name)
    
    if not os.path.exists(schedule_file_path):
        log("Schedule file not found, returning empty list", verbose, status=status, log_caller_file="load_tweet_schedules.py")
        return []
    
    with open(schedule_file_path, 'r') as f:
        try:
            schedules = json.load(f)
            return sorted(schedules, key=lambda x: datetime.strptime(x['scheduled_time'], '%Y-%m-%d %H:%M:%S'))
        except json.JSONDecodeError:
            log("Invalid JSON in schedule file, returning empty list", verbose, is_error=True, status=status, log_caller_file="load_tweet_schedules.py")

            return []
