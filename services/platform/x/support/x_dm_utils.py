from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from services.support.logger_util import _log as log
import time

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
