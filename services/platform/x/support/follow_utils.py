import time

from services.support.logger_util import _log as log

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def check_follow_status(driver, username, verbose=False, status=None):
    try:
        profile_url = f"https://x.com/{username}"
        log(f"Navigating to X profile: {profile_url}", verbose, status, log_caller_file="x_follow_utils.py")
        driver.get(profile_url)
        time.sleep(2)

        log(f"Checking for follow button on {username}'s profile...", verbose, status, log_caller_file="x_follow_utils.py")
        follow_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label, 'Follow @')]"))
        )

        aria_label = follow_button.get_attribute("aria-label")
        log(f"Follow button aria-label: '{aria_label}'", verbose, status, log_caller_file="x_follow_utils.py")

        if "Following" in aria_label:
            log(f"Currently following {username}", verbose, status, log_caller_file="x_follow_utils.py")
            return "following"
        elif "Follow" in aria_label:
            log(f"Not currently following {username}", verbose, status, log_caller_file="x_follow_utils.py")
            return "not_following"
        else:
            log(f"Unknown follow button state for {username}: {aria_label}", verbose, status, log_caller_file="x_follow_utils.py")
            return "unknown"
    except (TimeoutException, NoSuchElementException) as e:
        log(f"Follow button not found for {username}: {e}", verbose, is_error=True, status=status, log_caller_file="x_follow_utils.py")
        return "not_found"

def follow_user(driver, username, verbose=False, status=None):
    try:
        profile_url = f"https://x.com/{username}"
        log(f"Navigating to X profile: {profile_url}", verbose, status, log_caller_file="x_follow_utils.py")
        driver.get(profile_url)
        time.sleep(2)

        log(f"Looking for follow button on {username}'s profile...", verbose, status, log_caller_file="x_follow_utils.py")
        follow_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Follow @')]"))
        )

        aria_label = follow_button.get_attribute("aria-label")
        log(f"Found button with aria-label: '{aria_label}'", verbose, status, log_caller_file="x_follow_utils.py")

        if "Following" in aria_label:
            log(f"Already following {username}, skipping", verbose, status, log_caller_file="x_follow_utils.py")
            return False, "already_following"

        log(f"Clicking follow button for {username}...", verbose, status, log_caller_file="x_follow_utils.py")
        follow_button.click()
        time.sleep(1)

        log(f"Waiting for follow confirmation for {username}...", verbose, status, log_caller_file="x_follow_utils.py")
        try:
            following_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label, 'Following @')]"))
            )
            log(f"Successfully followed {username}", verbose, status, log_caller_file="x_follow_utils.py")
            return True, "followed"
        except TimeoutException:
            log(f"Follow confirmation not found for {username}", verbose, is_error=True, status=status, log_caller_file="x_follow_utils.py")
            return False, "follow_failed"

    except (TimeoutException, NoSuchElementException) as e:
        log(f"Error following {username}: {e}", verbose, is_error=True, status=status, log_caller_file="x_follow_utils.py")
        return False, "user_not_found"

def unfollow_user(driver, username, verbose=False, status=None):
    try:
        profile_url = f"https://x.com/{username}"
        log(f"Navigating to X profile: {profile_url}", verbose, status, log_caller_file="x_follow_utils.py")
        driver.get(profile_url)
        time.sleep(2)

        log(f"Looking for following button on {username}'s profile...", verbose, status, log_caller_file="x_follow_utils.py")
        following_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Following @')]"))
        )

        log(f"Clicking following button to initiate unfollow for {username}...", verbose, status, log_caller_file="x_follow_utils.py")
        following_button.click()
        time.sleep(1)

        log(f"Looking for unfollow confirmation button for {username}...", verbose, status, log_caller_file="x_follow_utils.py")
        try:
            confirm_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button//span[text()='Unfollow']"))
            )
            log(f"Clicking unfollow confirmation for {username}...", verbose, status, log_caller_file="x_follow_utils.py")
            confirm_button.click()
            time.sleep(1)
            log(f"Successfully unfollowed {username}", verbose, status, log_caller_file="x_follow_utils.py")
            return True, "unfollowed"
        except TimeoutException:
            log(f"Unfollow confirmation button not found for {username}", verbose, is_error=True, status=status, log_caller_file="x_follow_utils.py")
            return False, "unfollow_failed"

    except (TimeoutException, NoSuchElementException) as e:
        log(f"Error unfollowing {username}: {e}", verbose, is_error=True, status=status, log_caller_file="x_follow_utils.py")
        return False, "user_not_found"
