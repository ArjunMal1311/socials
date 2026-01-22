import os
import time

from rich.console import Console
from selenium.webdriver.common.by import By
from services.support.logger_util import _log as log
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from services.support.web_driver_handler import setup_driver
from selenium.webdriver.support import expected_conditions as EC
from services.support.path_config import get_browser_data_dir

console = Console()

# path to download files should be configured directly in chromium
# search in settings downloads and change path
# also for downloading so that ads dont block use ad-blocker extension
# (make the process more efficient and reliable)
def download_twitter_videos(tweet_urls: list[str], download_dir: str, profile_name="Default", headless=True, verbose: bool = False) -> list[str]:
    user_data_dir = get_browser_data_dir(profile_name)
    driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless, verbose=verbose)
    for msg in setup_messages:
        log(msg, verbose, log_caller_file="video_download.py")
        time.sleep(0.1)

    time.sleep(10)
    original_window = driver.current_window_handle
    current_tabs = []
    
    os.makedirs(download_dir, exist_ok=True)

    initial_files = set(os.listdir(download_dir))
    downloaded_video_paths = []

    for url in tweet_urls:
        log(f"Processing Downloads for URL: {url}", verbose, log_caller_file="video_download.py")
        log(f"Downloading video from: {url}", verbose, log_caller_file="video_download.py")
        try:
            driver.execute_script("window.open('');")
            new_tab = driver.window_handles[-1]
            current_tabs.append(new_tab)
            driver.switch_to.window(new_tab)
            driver.get('https://savetwitter.net/en')
            time.sleep(2)
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 's_input'))
            )
            driver.execute_script("arguments[0].value = arguments[1];", input_field, url)
            download_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'btn-red'))
            )
            download_button.click()
            
            try:
                error_div = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'error')]//p[contains(text(), 'Video not found')]" ))
                )
                log(f"Video not found for URL: {url}, skipping to next URL", verbose, is_error=False, log_caller_file="video_download.py")
                continue
            except TimeoutException:
                try:
                    best_quality_link = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@class, 'tw-button-dl')][1]" ))
                    )
                    best_quality_link.click()
                    time.sleep(2)
                except TimeoutException:
                    log(f"Download already initiated for {url}, continuing to next URL", verbose, log_caller_file="video_download.py")
            
            max_wait_time = 20
            wait_interval = 2
            waited_time = 0
            
            while waited_time < max_wait_time:
                current_files = set(os.listdir(download_dir))
                new_files = current_files - initial_files
                
                downloading_files = [f for f in new_files if f.endswith('.crdownload') or f.endswith('.tmp')]
                
                if downloading_files:
                    log(f"Download still in progress: {downloading_files}", verbose, log_caller_file="video_download.py")
                    time.sleep(wait_interval)
                    waited_time += wait_interval
                    continue
                
                completed_files = [f for f in new_files if f.endswith('.mp4')]
                if completed_files:
                    new_file = completed_files[0]
                    break
                
                time.sleep(wait_interval)
                waited_time += wait_interval
            
            if new_file is None:
                log(f"Download timed out for URL: {url}", verbose, is_error=False, log_caller_file="video_download.py")
                continue
                
            log(f"New file downloaded: {new_file}", verbose, log_caller_file="video_download.py")
            
            initial_files.add(new_file)
            downloaded_video_paths.append(os.path.join(download_dir, new_file))
            
            tweet_id = url.split('/')[-1]
            mapping = f'{new_file} -> {tweet_id}\n'

            with open('tmp/downloaded_videos.txt', 'a') as f:
                f.write(mapping)
            log(f"Video downloaded and mapped: {mapping.strip()}", verbose, log_caller_file="video_download.py")

        except Exception as e:
            log(f"Error processing URL {url}: {str(e)}", verbose, is_error=True, log_caller_file="video_download.py")
        finally:
            try:
                driver.close()
                if new_tab in current_tabs:
                    current_tabs.remove(new_tab)
            except:
                pass
            driver.switch_to.window(original_window)

    driver.quit()
    return downloaded_video_paths
