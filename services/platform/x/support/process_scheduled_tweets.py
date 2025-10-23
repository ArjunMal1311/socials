import os
import time
import re

from datetime import datetime
from rich.text import Text
from rich.status import Status
from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from services.support.web_driver_handler import setup_driver
from selenium.webdriver.support import expected_conditions as EC
from services.platform.x.support.schedule_tweet import schedule_tweet
from services.platform.x.support.load_tweet_schedules import load_tweet_schedules

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False):
    if is_error:
        if status:
            status.stop()
        log_message = message
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[process_scheduled_tweets.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[process_scheduled_tweets.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def process_scheduled_tweets(profile_name="Default", verbose: bool = False, headless: bool = True):
    _log(f"Processing scheduled tweets for profile: {profile_name}", verbose)
    user_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'browser-data', profile_name))
    driver = None
    try:
        with Status("[white]Initializing WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless)
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

        scheduled_tweets = load_tweet_schedules(profile_name)

        if not scheduled_tweets:
            _log("No tweets scheduled yet.", verbose)
            return

        with Status("[white]Scheduling tweets...[/white]", spinner="dots", console=console) as status:
            for tweet in scheduled_tweets:
                scheduled_time = tweet['scheduled_time']
                tweet_text = tweet['scheduled_tweet']
                media_file = tweet.get('scheduled_image')
                
                status.update(f"[white]Attempting to schedule tweet for {scheduled_time} with text '{tweet_text}'[/white]")

                schedule_tweet(driver, tweet_text, media_file, scheduled_time, profile_name, status)
                time.sleep(5)
        _log("All scheduled tweets processed!", verbose)

    except Exception as e:
        _log(f"An error occurred during tweet processing: {e}", verbose, is_error=True)
    finally:
        if driver:
            driver.quit()
            _log("WebDriver closed.", verbose)
