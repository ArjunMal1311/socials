# socials linkedin <profile> dm

import os
import sys
import json
import time
import argparse

from profiles import PROFILES

from datetime import datetime
from dotenv import load_dotenv

from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_linkedin_profile_dir, initialize_directories

from services.platform.linkedin.support.connection_utils import send_linkedin_dm

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="LinkedIn DM CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True)
        sys.exit(1)

    # profile parameters
    profile_props = PROFILES[args.profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    browser_profile = args.profile

    messages_file = os.path.join(get_linkedin_profile_dir(args.profile), "messages.json")
    if not os.path.exists(messages_file):
        log(f"messages.json not found at {messages_file}", verbose=verbose, is_error=True)
        sys.exit(1)

    try:
        with open(messages_file, 'r', encoding='utf-8') as f:
            messages_data = json.load(f)
    except Exception as e:
        log(f"Error reading messages.json: {e}", verbose=verbose, is_error=True)
        sys.exit(1)

    if not messages_data or not isinstance(messages_data, list):
        log("messages.json must contain a non-empty array of message objects", verbose=verbose, is_error=True)
        sys.exit(1)

    user_data_dir = get_browser_data_dir(browser_profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile, headless=headless)
            for msg in setup_messages:
                log(msg, verbose, status)
            status.update("[white]WebDriver setup complete.[/white]")

        for i, message_obj in enumerate(messages_data):
            username = message_obj.get('username')
            message = message_obj.get('message')

            if not username or not message:
                log(f"Skipping invalid message object at index {i}: missing username or message", verbose=verbose, is_error=True)
                continue

            profile_url = f"https://www.linkedin.com/in/{username}/"
            log(f"Sending DM to {username}", verbose, status=status)
            dm_success = send_linkedin_dm(driver, profile_url, message, verbose=verbose, status=status)

            message_obj['success'] = dm_success
            message_obj['sent_at'] = datetime.now().isoformat() + "Z"

            if dm_success:
                log(f"Successfully sent DM to {username}", verbose)
            else:
                log(f"Failed to send DM to {username}", verbose, is_error=True)

            if i < len(messages_data) - 1:
                log(f"Waiting for 10 seconds before next message...", verbose)
                time.sleep(10)

        with open(messages_file, 'w', encoding='utf-8') as f:
            json.dump(messages_data, f, indent=2, ensure_ascii=False)

        log(f"DM campaign completed. Processed {len(messages_data)} messages.", verbose)

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()

