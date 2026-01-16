import os
import glob
import subprocess

from selenium import webdriver
from rich.console import Console
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from services.support.logger_util import _log as log

console = Console()

def setup_driver(user_data_dir, incognito=False, profile="Default", headless=False, prefs: dict = None, additional_arguments: list = None, verbose: bool = False, status=None):
    options = Options()
    status_messages = []

    user_data_dir = os.path.abspath(user_data_dir)

    kill_chrome_processes_by_user_data_dir(user_data_dir, verbose, status)
    log(f"Killed Chrome processes for {user_data_dir}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")

    profile_path = os.path.join(user_data_dir, profile)
    cleanup_chrome_locks(profile_path, verbose, status)
    log(f"Cleaned up Chrome lock files in {profile_path}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")

    log(f"Attempting to set up driver with user_data_dir: {user_data_dir} and profile: {profile}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")

    if headless:
        options.add_argument('--headless=new')
        
    if prefs:
        options.add_experimental_option("prefs", prefs)

    if additional_arguments:
        for arg in additional_arguments:
            options.add_argument(arg)

    try:
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, mode=0o777, exist_ok=True)
        log(f"Using Chrome data directory: {user_data_dir}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")
    except Exception as e:
        error_msg = f"Failed to create Chrome data directory: {str(e)}"
        log(error_msg, verbose, is_error=True, status=status, api_info=None, log_caller_file="web_driver_handler.py")
        raise

    options.add_argument(f'--user-data-dir={user_data_dir}')
    options.add_argument(f'--profile-directory={profile}')

    if incognito:
        options.add_argument('--incognito')

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920x1080')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    chromium_paths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        '/usr/lib/chromium/chromium',
        '/usr/lib/chromium-browser/chromium-browser'
    ]

    chromium_binary = None
    for path in chromium_paths:
        if os.path.exists(path):
            chromium_binary = path
            break

    if not chromium_binary:
        error_msg = "Chromium binary not found. Please install Chromium."
        log(error_msg, verbose, is_error=True, status=status, api_info=None, log_caller_file="web_driver_handler.py")
        raise Exception(error_msg)

    options.binary_location = chromium_binary
    log(f"Using Chromium binary at: {chromium_binary}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    })

    driver.set_window_size(1920, 1080)
    driver.set_page_load_timeout(60)
    driver.implicitly_wait(30)

    log("Chromium WebDriver created successfully", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")
    return driver, status_messages


def cleanup_chrome_locks(profile_path, verbose: bool = False, status=None):
    lock_patterns = [
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        ".org.chromium.Chromium.*"
    ]
    for pattern in lock_patterns:
        for f in glob.glob(os.path.join(profile_path, pattern)):
            try:
                os.remove(f)
                log(f"Removed leftover lock: {f}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")
            except Exception as e:
                log(f"Could not remove {f}: {e}", verbose, is_error=True, status=status, api_info=None, log_caller_file="web_driver_handler.py")


def kill_chrome_processes_by_user_data_dir(user_data_dir, verbose: bool = False, status=None):
    try:
        abs_user_data_dir = os.path.abspath(user_data_dir)
        command = f"lsof -t {abs_user_data_dir} | xargs -r ps -o pid=,comm="
        process = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        pids_to_kill = []
        for line in process.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 2:
                pid, comm = parts[0], parts[1]
                if (comm == 'chrome' or comm == 'chromium') and pid.isdigit():
                    pids_to_kill.append(pid)

        if pids_to_kill:
            pid_list = " ".join(pids_to_kill)
            kill_command = f"kill -9 {pid_list}"
            subprocess.run(kill_command, shell=True, capture_output=True, text=True)
            log(f"Killed Chrome/Chromium processes: {pid_list} using directory: {user_data_dir}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")
            return True
        else:
            log(f"No Chrome/Chromium processes found using directory: {user_data_dir}", verbose, status=status, api_info=None, log_caller_file="web_driver_handler.py")
            return False
    except Exception as e:
        log(f"Error killing Chrome processes: {e}", verbose, is_error=True, status=status, api_info=None, log_caller_file="web_driver_handler.py")
        return False

