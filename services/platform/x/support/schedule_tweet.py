import re
import os
import time

from datetime import datetime
from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from services.support.path_config import get_schedule_dir
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

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
        console.print(f"[schedule_tweet.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[schedule_tweet.py] {timestamp}|[{color}]{message}[/{color}]")
    elif status:
        status.update(message)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[schedule_tweet.py] {timestamp}|[{color}]{message}[/{color}]")

def schedule_tweet(driver, tweet_text, media_urls, scheduled_time, profile_name, status=None, verbose: bool = False):
    try:
        local_media_paths = None
        if media_urls:
            if isinstance(media_urls, str) and media_urls.startswith('http'):
                local_media_paths = [media_urls]
            else:
                schedule_folder = get_schedule_dir(profile_name)
                if isinstance(media_urls, str):
                    candidate_path = os.path.join(schedule_folder, media_urls)
                    _log(f"Looking for media file at: {candidate_path}", verbose, status)
                    if os.path.exists(candidate_path):
                        local_media_paths = [os.path.abspath(candidate_path)]
                    else:
                        local_media_paths = [media_urls]
                else:
                    local_media_paths = []
                    for fname in media_urls:
                        candidate_path = os.path.join(schedule_folder, fname)
                        _log(f"Looking for media file at: {candidate_path}", verbose, status)
                        if os.path.exists(candidate_path):
                            local_media_paths.append(os.path.abspath(candidate_path))
                        else:
                            local_media_paths.append(fname)

        _log("Navigating to tweet compose page...", verbose, status)
        driver.get('https://x.com/compose/tweet')
        time.sleep(3)
        tweet_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
        )
        tweet_input.clear()
        tweet_input.send_keys(tweet_text)
        time.sleep(2)

        if profile_name == "akg":
            tweet_input.send_keys(Keys.ENTER)
            _log("Pressed Enter for akg profile.", verbose, status)
            time.sleep(1)
        
        if local_media_paths:
            try:
                _log("Uploading media...", verbose, status)
                media_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]'))
                )
                for local_path in local_media_paths:
                    _log(f"Uploading media: {local_path}", verbose, status)
                    media_button.send_keys(local_path)
                    time.sleep(5)
                _log("Media uploaded.", verbose, status)
            except Exception as e:
                _log(f"Failed to upload media: {e}", verbose, is_error=True)
                raise

        _log("Clicking schedule option...", verbose, status)
        schedule_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="scheduleOption"]'))
        )
        schedule_option.click()
        time.sleep(2)

        scheduled_datetime = datetime.strptime(scheduled_time, '%Y-%m-%d %H:%M:%S')
        
        _log("Selecting scheduled date and time...", verbose, status)
        month_select = Select(WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'SELECTOR_1'))
        ))
        day_select = Select(driver.find_element(By.ID, 'SELECTOR_2'))
        year_select = Select(driver.find_element(By.ID, 'SELECTOR_3'))
        hour_select = Select(driver.find_element(By.ID, 'SELECTOR_4'))
        minute_select = Select(driver.find_element(By.ID, 'SELECTOR_5'))
        ampm_select = Select(driver.find_element(By.ID, 'SELECTOR_6'))

        month = scheduled_datetime.strftime('%B')
        day = str(int(scheduled_datetime.strftime('%d')))
        year = scheduled_datetime.strftime('%Y')
        hour = scheduled_datetime.strftime('%I').lstrip('0')
        minute = scheduled_datetime.strftime('%M')
        ampm = scheduled_datetime.strftime('%p')

        month_select.select_by_visible_text(month)
        time.sleep(1)
        day_select.select_by_visible_text(day)
        time.sleep(1)
        year_select.select_by_visible_text(year)
        time.sleep(1)
        hour_select.select_by_visible_text(hour)
        time.sleep(1)
        minute_select.select_by_visible_text(minute)
        time.sleep(1)
        ampm_select.select_by_visible_text(ampm)
        time.sleep(2)

        _log("Confirming scheduled time...", verbose, status)
        confirm_time_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="scheduledConfirmationPrimaryAction"]'))
        )
        confirm_time_button.click()
        time.sleep(2)

        _log("Clicking schedule button...", verbose, status)
        schedule_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
        )
        schedule_button.click()
        time.sleep(3)
        driver.get('https://x.com')
        time.sleep(3)
        _log(f"Successfully scheduled tweet for {scheduled_time}", verbose, status)
        return True
    except Exception as e:
        _log(f"Failed to schedule tweet: {e}", verbose, is_error=True)
        return False
