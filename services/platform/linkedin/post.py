# socials linkedin <profile> post

import os
import sys
import json
import time
import argparse

from profiles import PROFILES

from datetime import datetime
from dotenv import load_dotenv

from rich.console import Console
from rich.status import Status

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_linkedin_profile_dir, initialize_directories

from services.platform.linkedin.support.post_utils import create_linkedin_post

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="LinkedIn Post CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Browser profile name to use.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True, log_caller_file="post.py")
        sys.exit(1)

    profile_props = PROFILES[args.profile].get('properties', {})
    global_props = profile_props.get('global', {})
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    browser_profile = args.profile

    posts_file = os.path.join(get_linkedin_profile_dir(args.profile), "posts.json")
    if not os.path.exists(posts_file):
        log(f"posts.json not found at {posts_file}", verbose=verbose, is_error=True, log_caller_file="post.py")
        sys.exit(1)

    try:
        with open(posts_file, 'r', encoding='utf-8') as f:
            posts_data = json.load(f)
    except Exception as e:
        log(f"Error reading posts.json: {e}", verbose=verbose, is_error=True, log_caller_file="post.py")
        sys.exit(1)

    if not posts_data or not isinstance(posts_data, list):
        log("posts.json must contain a non-empty array of post objects", verbose=verbose, is_error=True, log_caller_file="post.py")
        sys.exit(1)

    user_data_dir = get_browser_data_dir(browser_profile)
    driver = None
    try:
        with Status("[white]Setting up WebDriver...[/white]", spinner="dots", console=console) as status:
            driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile, headless=headless)
            for msg in setup_messages:
                log(msg, verbose, status, log_caller_file="post.py")
            status.update("[white]WebDriver setup complete.[/white]")

        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

        for i, post_obj in enumerate(posts_data):
            text = post_obj.get('text', '').strip()
            media_urls = post_obj.get('media_urls', [])

            if not text:
                log(f"Skipping post {i+1}: empty text", verbose=verbose, is_error=True, log_caller_file="post.py")
                continue

            log(f"Creating post {i+1}: {text[:50]}...", verbose, status=status, log_caller_file="post.py")

            success = create_linkedin_post(driver, text, media_urls, verbose, status)

            post_obj['success'] = success
            post_obj['posted_at'] = datetime.now().isoformat() + "Z"

            if success:
                log(f"Successfully posted to LinkedIn", verbose, log_caller_file="post.py")
            else:
                log(f"Failed to post to LinkedIn", verbose, is_error=True, log_caller_file="post.py")

            if i < len(posts_data) - 1:
                log(f"Waiting for 30 seconds before next post...", verbose, log_caller_file="post.py")
                time.sleep(30)

        with open(posts_file, 'w', encoding='utf-8') as f:
            json.dump(posts_data, f, indent=2, ensure_ascii=False)

        log(f"Posting session completed. Processed {len(posts_data)} posts.", verbose, log_caller_file="post.py")

    except Exception as e:
        log(f"An error occurred: {e}", verbose=True, is_error=True, log_caller_file="post.py")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
