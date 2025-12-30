import os
import time
import random

from typing import Optional, Tuple

from services.support.logger_util import _log as log

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _resolve_credentials(profile_name: Optional[str]) -> Tuple[str, str, str, str]:
    prefix = (profile_name or '').strip().upper()
    if not prefix:
        return "", "", "", ""
    consumer_key = os.getenv(f"{prefix}_X_CONSUMER_KEY") or ""
    consumer_secret = os.getenv(f"{prefix}_X_CONSUMER_SECRET") or ""
    access_token = os.getenv(f"{prefix}_X_ACCESS_TOKEN") or ""
    access_token_secret = os.getenv(f"{prefix}_X_ACCESS_TOKEN_SECRET") or ""
    return consumer_key, consumer_secret, access_token, access_token_secret

def _get_tweepy_client(profile_name: Optional[str], verbose: bool = False):
    try:
        import tweepy
    except Exception as e:
        log(f"tweepy is not installed: {e} Install with: pip install tweepy", verbose, is_error=True, log_caller_file="x_dm_utils.py")
        return None

    consumer_key, consumer_secret, access_token, access_token_secret = _resolve_credentials(profile_name)

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        scope_hint = (profile_name or '').strip().upper() or 'PROFILE'
        log(
            f"Twitter API keys missing for profile {scope_hint}.\n" +
            f"Set these environment variables: {scope_hint}_X_CONSUMER_KEY, {scope_hint}_X_CONSUMER_SECRET, {scope_hint}_X_ACCESS_TOKEN, {scope_hint}_X_ACCESS_TOKEN_SECRET",
            verbose, is_error=True, log_caller_file="x_dm_utils.py"
        )
        return None

    try:
        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        return client
    except Exception as e:
        log(f"Failed to create tweepy client: {e}", verbose, is_error=True, log_caller_file="x_dm_utils.py")
        return None

def check_dm_button(driver, username: str, verbose: bool = False, status=None) -> bool:
    profile_url = f"https://x.com/{username}"
    try:
        log(f"Navigating to X profile: {profile_url}", verbose, status, log_caller_file="x_dm_utils.py")
        driver.get(profile_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        time.sleep(5)

        log(f"Checking for DM button on {username}'s profile...", verbose, status, log_caller_file="x_dm_utils.py")
        try:
            dm_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//button[@data-testid='sendDMFromProfile']"))
            )
            if dm_button.is_displayed():
                log(f"DM button found for {username}.", verbose, status, log_caller_file="x_dm_utils.py")
                return True
            else:
                log(f"DM button not displayed for {username}.", verbose, status, log_caller_file="x_dm_utils.py")
                return False
        except:
            log(f"DM button not found for {username}.", verbose, status, log_caller_file="x_dm_utils.py")
            return False

    except Exception as e:
        log(f"Error checking DM button for {username}: {e}", verbose, is_error=True, status=status, log_caller_file="x_dm_utils.py")
        return False

def send_dm(driver, username: str, message: str, verbose: bool = False, status=None) -> bool:
    profile_url = f"https://x.com/{username}"
    try:
        log(f"Navigating to X profile: {profile_url}", verbose, status, log_caller_file="x_dm_utils.py")
        driver.get(profile_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        time.sleep(5)

        log(f"Attempting to click DM button on {username}'s profile...", verbose, status, log_caller_file="x_dm_utils.py")
        dm_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='sendDMFromProfile']"))
        )
        dm_button.click()
        log(f"DM button clicked for {username}. Waiting for message composer...", verbose, status, log_caller_file="x_dm_utils.py")
        time.sleep(10)

        message_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="dm-composer-textarea"]'))
        )
        for char in message:
            message_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        log(f"Typed message into composer for {username}.", verbose, status, log_caller_file="x_dm_utils.py")
        time.sleep(2)

        send_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="dm-composer-send-button"]'))
        )
        send_button.click()
        log(f"Send button clicked for {username}. DM sent.", verbose, status, log_caller_file="x_dm_utils.py")
        time.sleep(5)
        return True

    except Exception as e:
        log(f"Error sending DM to {username}: {e}", verbose, is_error=True, status=status, log_caller_file="x_dm_utils.py")
        return False

def send_dm_api(profile_name: str, recipient_username: str, message: str, verbose: bool = False) -> bool:
    log(f"Attempting to send DM via API to {recipient_username} for profile {profile_name}", verbose, log_caller_file="x_dm_utils.py")
    client = _get_tweepy_client(profile_name, verbose=verbose)
    if not client:
        return False

    try:
        response = client.get_user(username=recipient_username)
        if response.data:
            recipient_id = response.data.id
            log(f"Resolved username {recipient_username} to ID {recipient_id}", verbose, log_caller_file="x_dm_utils.py")
        else:
            log(f"Could not resolve username {recipient_username} to a user ID.", verbose, is_error=True, log_caller_file="x_dm_utils.py")
            return False

        dm_response = client.create_direct_message(participant_id=recipient_id, text=message)
        log(f"API DM sent response: {dm_response}", verbose, log_caller_file="x_dm_utils.py")
        if dm_response.data:
            log(f"Successfully sent DM to {recipient_username} via API.", verbose, log_caller_file="x_dm_utils.py")
            return True
        else:
            log(f"Failed to send DM to {recipient_username} via API. Response: {dm_response}", verbose, is_error=True, log_caller_file="x_dm_utils.py")
            return False
    except Exception as e:
        log(f"Error sending DM via API to {recipient_username}: {e}", verbose, is_error=True, log_caller_file="x_dm_utils.py")
        return False
