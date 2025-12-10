from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from services.support.logger_util import _log as log
import time
import random

def send_connection_request(driver, profile_url: str, verbose: bool = False, status=None) -> bool:
    try:
        username = profile_url.split("linkedin.com/in/")[-1].strip('/')
        direct_invite_url = f"https://www.linkedin.com/preload/custom-invite/?vanityName={username}"
        
        log(f"Navigating to direct LinkedIn invite URL: {direct_invite_url}", verbose, status, log_caller_file="connection_utils.py")
        driver.get(direct_invite_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        time.sleep(5)

        log("Attempting to click 'Send without a note' button directly via JavaScript...", verbose, status, log_caller_file="connection_utils.py")
        
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Send without a note']"))
        )
        send_without_note_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Send without a note']"))
        )
        send_without_note_button.click()
        log("'Send without a note' button clicked using Selenium.", verbose, status, log_caller_file="connection_utils.py")
        time.sleep(5)
        
        log(f"Successfully sent connection request to {profile_url}", verbose=verbose, status=status, log_caller_file="connection_utils.py")
        return True
    except Exception as e:
        log(f"Error sending connection request to {profile_url}: {e}", verbose=verbose, is_error=True, status=status, log_caller_file="connection_utils.py")
        return False

def send_linkedin_dm(driver, profile_url: str, message: str, verbose: bool = False, status=None) -> bool:
    try:
        log(f"Navigating to LinkedIn profile: {profile_url}", verbose, status, log_caller_file="connection_utils.py")
        driver.get(profile_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        time.sleep(5)

        log(f"Attempting to click Message button on {profile_url}'s profile...", verbose, status, log_caller_file="connection_utils.py")
        message_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "(//button[starts-with(@aria-label, 'Message ')])[2]"))
        )
        try:
            message_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", message_button)
        log(f"Message button clicked for {profile_url}. Waiting for message composer...", verbose, status, log_caller_file="connection_utils.py")
        time.sleep(15)

        message_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-form__contenteditable[contenteditable='true'][role='textbox']"))
        )
        for char in message:
            message_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        log(f"Typed message into composer for {profile_url}.", verbose, status, log_caller_file="connection_utils.py")
        time.sleep(2)

        send_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".msg-form__send-button.artdeco-button.artdeco-button--1"))
        )
        send_button.click()
        log(f"Send button clicked for {profile_url}. DM sent.", verbose, status, log_caller_file="connection_utils.py")
        time.sleep(5)
        return True

    except Exception as e:
        log(f"Error sending DM to {profile_url}: {e}", verbose, is_error=True, status=status, log_caller_file="connection_utils.py")
        return False
