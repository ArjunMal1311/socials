import time

from rich.console import Console
from selenium.webdriver.common.by import By
from services.support.logger_util import _log as log
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from services.platform.x.support.process_container import process_container
from services.platform.x.support.capture_containers_scroll import capture_containers_and_scroll
from services.support.sheets_util import get_google_sheets_service, create_online_action_mode_sheet, save_action_mode_replies_to_sheet

console = Console()

def analyze_profile(driver, profile_name: str, target_profile_name: str, verbose: bool = False, status=None):
    log(f"Starting analysis for target profile: {target_profile_name}", verbose, log_caller_file="profile_analyzer.py")

    sheet_name = f"{profile_name}_profile_{target_profile_name}"
    log(f"Google Sheet name: {sheet_name}", verbose, log_caller_file="profile_analyzer.py")

    service = get_google_sheets_service(verbose=verbose, status=status)
    if not service:
        log("Failed to get Google Sheets service. Exiting.", verbose, is_error=True, log_caller_file="profile_analyzer.py")
        return

    create_online_action_mode_sheet(service, profile_name, verbose=verbose, status=status)

    profile_url = f"https://x.com/{target_profile_name}/with_replies"
    driver.get(profile_url)
    log(f"Navigated to {profile_url}", verbose, log_caller_file="profile_analyzer.py")

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
    )

    raw_containers = []
    processed_tweet_ids = set()
    no_new_content_count = 0
    scroll_count = 0
    max_scrolls = 20

    log("Starting to scrape tweets...", verbose, log_caller_file="profile_analyzer.py")

    while no_new_content_count < 3 and scroll_count < max_scrolls:
        initial_processed_count = len(processed_tweet_ids)
        no_new_content_count, scroll_count, new_containers_found_in_this_pass = capture_containers_and_scroll(
            driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose, status=status
        )
        scroll_count += 1
        log(f"Scrolled {scroll_count} times. New containers this pass: {new_containers_found_in_this_pass}. Total processed: {len(processed_tweet_ids)}", verbose, log_caller_file="profile_analyzer.py")
        time.sleep(1)

    log(f"Finished scraping. Total raw containers found: {len(raw_containers)}", verbose, log_caller_file="profile_analyzer.py")

    all_tweet_data = []
    for container in raw_containers:
        tweet_data = process_container(container, verbose=verbose)
        if tweet_data:
            all_tweet_data.append(tweet_data)

    log(f"Processed {len(all_tweet_data)} unique tweets.", verbose, log_caller_file="profile_analyzer.py")

    if all_tweet_data:
        save_action_mode_replies_to_sheet(service, profile_name, all_tweet_data, verbose=verbose, status=status)
        log(f"Successfully saved {len(all_tweet_data)} tweets to Google Sheet '{sheet_name}'.", verbose, log_caller_file="profile_analyzer.py")
    else:
        log("No tweets to save to Google Sheet.", verbose, log_caller_file="profile_analyzer.py")

    log(f"Profile analysis for {target_profile_name} completed.", verbose, log_caller_file="profile_analyzer.py")
