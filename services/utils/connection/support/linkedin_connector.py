import time

from typing import List

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir

from services.platform.linkedin.support.connection_utils import send_connection_request

def process_linkedin_connections(usernames: List[str], profile_name: str, verbose: bool = False, status=None, limit: int = 15) -> dict:
    if not usernames:
        log("No LinkedIn usernames to process", verbose, log_caller_file="linkedin_connector.py")
        return {"total": 0, "successful": 0, "failed": 0}

    log(f"Processing {len(usernames)} LinkedIn connection requests", verbose, status=status, log_caller_file="linkedin_connector.py")

    user_data_dir = get_browser_data_dir(profile_name)
    driver = None

    try:
        log("Setting up WebDriver for LinkedIn connections...", verbose, status=status, log_caller_file="linkedin_connector.py")
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=False)  # Keep visible for connections
        for msg in setup_messages:
            log(msg, verbose, status=status, log_caller_file="linkedin_connector.py")

        successful = 0
        failed = 0

        for i, username in enumerate(usernames, 1):
            # Check if we've reached the limit
            if successful >= limit:
                log(f"Reached connection limit of {limit}. Stopping.", verbose, status=status, log_caller_file="linkedin_connector.py")
                break

            profile_url = f"https://www.linkedin.com/in/{username}/"
            log(f"[{i}/{len(usernames)}] Processing connection request to: {profile_url}", verbose, status=status, log_caller_file="linkedin_connector.py")

            success = send_connection_request(driver, profile_url, verbose=verbose, status=status)

            if success:
                successful += 1
                log(f"✓ Successfully sent connection request to {username}", verbose, status=status, log_caller_file="linkedin_connector.py")
            else:
                failed += 1
                log(f"✗ Failed to send connection request to {username}", verbose, is_error=True, status=status, log_caller_file="linkedin_connector.py")

            # Only wait if we're continuing and haven't reached the limit
            if i < len(usernames) and successful < limit:
                wait_time = 25
                log(f"Waiting {wait_time} seconds before next request...", verbose, status=status, log_caller_file="linkedin_connector.py")
                time.sleep(wait_time)

        log(f"LinkedIn connection processing complete: {successful} successful, {failed} failed", verbose, status=status, log_caller_file="linkedin_connector.py")

        return {
            "total": len(usernames),
            "successful": successful,
            "failed": failed
        }

    except Exception as e:
        log(f"Error during LinkedIn connection processing: {e}", verbose, is_error=True, status=status, log_caller_file="linkedin_connector.py")
        return {
            "total": len(usernames),
            "successful": 0,
            "failed": len(usernames),
            "error": str(e)
        }
    finally:
        if driver:
            driver.quit()
