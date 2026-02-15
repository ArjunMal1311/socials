import os
import time

from rich.console import Console

from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_file_path, get_project_root

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

console = Console()

def upload_media(driver, media_file, profile_name="Default", status=None, verbose: bool = False):
    local_media_path = None
    if media_file:
        if isinstance(media_file, str) and media_file.startswith('http'):
            local_media_path = media_file
        else:
            candidate_path = os.path.join(get_project_root(), media_file)
            if verbose:
                log(f"Looking for media file at: {candidate_path}", verbose, log_caller_file="post_to_community.py")
            if os.path.exists(candidate_path):
                local_media_path = os.path.abspath(candidate_path)
            else:
                local_media_path = media_file

    if local_media_path:
        try:
            if status:
                log("Uploading media...", verbose, status=status, log_caller_file="post_to_community.py")
            else:
                log("Uploading media...", verbose, log_caller_file="post_to_community.py")
            media_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]'))
            )
            media_button.send_keys(local_media_path)
            time.sleep(5)
            if status:
                log("Media uploaded.", verbose, status=status, log_caller_file="post_to_community.py")
            else:
                log("Media uploaded.", verbose, log_caller_file="post_to_community.py")
        except Exception as e:
            if status:
                log(f"Failed to upload media: {e}", verbose, is_error=True, log_caller_file="post_to_community.py")
            else:
                log(f"Failed to upload media: {e}", verbose, is_error=True, log_caller_file="post_to_community.py")
            raise

def post_to_community_tweet(driver, tweet_text, community_name, media_file=None, profile_name="Default", status=None, verbose: bool = False):
    try:
        if status:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        driver.get('https://x.com/compose/tweet')
        time.sleep(3)

        tweet_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
        )
        tweet_input.clear()
        tweet_input.send_keys(tweet_text)
        time.sleep(2)

        upload_media(driver, media_file, profile_name, status, verbose)

        if status:
            log(f"Selecting community '{community_name}'...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Selecting community '{community_name}'...", verbose, status=status, log_caller_file="post_to_community.py")
        
        choose_audience_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Choose audience"]'))
        )
        choose_audience_button.click()
        time.sleep(2)

        community_xpath = f"//span[text()='{community_name}']"
        community_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, community_xpath))
        )
        community_element.click()
        time.sleep(2)
        
        if status:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        post_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
        )
        post_button.click()
        time.sleep(3)

        driver.get('https://x.com')
        time.sleep(3)
        if status:
            log(f"Successfully posted tweet to community '{community_name}'", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Successfully posted tweet to community '{community_name}'", verbose, status=status, log_caller_file="post_to_community.py")
        return True
    except Exception as e:
        log(f"Failed to post tweet to community: {e}", verbose, is_error=True, status=status, log_caller_file="post_to_community.py")
        return False

def post_regular_tweet(driver, tweet_text, media_file=None, profile_name="Default", status=None, verbose: bool = False):
    try:
        if status:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        driver.get('https://x.com/compose/tweet')
        time.sleep(3)

        tweet_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
        )
        tweet_input.clear()
        tweet_input.send_keys(tweet_text)
        time.sleep(2)

        upload_media(driver, media_file, profile_name, status, verbose)

        if status:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        post_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
        )
        post_button.click()
        time.sleep(3)

        driver.get('https://x.com')
        time.sleep(3)
        if status:
            log(f"Successfully posted regular tweet.", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Successfully posted regular tweet.", verbose, status=status, log_caller_file="post_to_community.py")
        return True
    except Exception as e:
        log(f"Failed to post regular tweet: {e}", verbose, is_error=True, status=status, log_caller_file="post_to_community.py")
        return False
