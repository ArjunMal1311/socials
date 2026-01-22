import os
import json
import time
from datetime import datetime

import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.api_call_tracker import APICallTracker
from services.support.api_key_pool import APIKeyPool
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_gemini_log_file_path, get_linkedin_profile_dir

from services.platform.linkedin.support.scraper_utils import scrape_linkedin_feed_posts

def run_linkedin_reply_mode(profile_name: str, browser_profile_name: str, max_posts: int = 10, verbose: bool = False, headless: bool = True, status=None):
    user_data_dir = get_browser_data_dir(browser_profile_name)

    try:
        driver, setup_messages = setup_driver(user_data_dir, profile=browser_profile_name, verbose=verbose, status=status, headless=headless)
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="reply_utils.py")

        log("Scraping LinkedIn home feed posts...", verbose, status, log_caller_file="reply_utils.py")
        feed_posts = scrape_linkedin_feed_posts(browser_profile_name, max_posts=max_posts, verbose=verbose, status=status, headless=headless, existing_driver=driver)

        if not feed_posts:
            log("No posts found in LinkedIn feed", verbose, is_error=True, log_caller_file="reply_utils.py")
            driver.quit()
            return None, []

        log(f"Found {len(feed_posts)} posts, generating replies...", verbose, status, log_caller_file="reply_utils.py")

        api_key_pool = APIKeyPool(verbose=verbose)
        log(f"API key pool size: {api_key_pool.size()}", verbose, status, log_caller_file="reply_utils.py")

        if api_key_pool.size() == 0:
            log("No API keys available for reply generation", verbose, is_error=True, log_caller_file="reply_utils.py")
            log(f"GEMINI_API env var: {os.getenv('GEMINI_API')}", verbose, status, log_caller_file="reply_utils.py")
            driver.quit()
            return None, []

        replies_data = []
        for i, post in enumerate(feed_posts):
            try:
                reply_text = generate_linkedin_reply(post, api_key_pool, profile_name, verbose, status)
                if reply_text:
                    reply_data = {
                        "post_id": post.get("data", {}).get("post_id", f"linkedin_{i}"),
                        "post_text": post.get("data", {}).get("text", ""),
                        "profile_url": post.get("data", {}).get("profile_url", ""),
                        "generated_reply": reply_text,
                        "approved": False,
                        "posted": False,
                        "created_at": datetime.now().isoformat() + "Z"
                    }
                    replies_data.append(reply_data)
                    log(f"Generated reply for post {i+1}/{len(feed_posts)}", verbose, status, log_caller_file="reply_utils.py")
                else:
                    log(f"Failed to generate reply for post {i+1}", verbose, is_error=True, log_caller_file="reply_utils.py")

            except Exception as e:
                log(f"Error generating reply for post {i+1}: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
                continue

        replies_file = os.path.join(get_linkedin_profile_dir(profile_name), "replies.json")
        os.makedirs(os.path.dirname(replies_file), exist_ok=True)

        with open(replies_file, 'w', encoding='utf-8') as f:
            json.dump(replies_data, f, indent=2, ensure_ascii=False)

        return driver, replies_data

    except Exception as e:
        log(f"Error in reply generation: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
        if 'driver' in locals():
            driver.quit()
        return None, []


def post_approved_linkedin_replies(driver, profile_name: str, verbose: bool = False, status=None):
    replies_file = os.path.join(get_linkedin_profile_dir(profile_name), "replies.json")

    if not os.path.exists(replies_file):
        log(f"Replies file not found: {replies_file}", verbose, is_error=True, log_caller_file="reply_utils.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    with open(replies_file, 'r', encoding='utf-8') as f:
        try:
            replies_data = json.load(f)
        except Exception as e:
            log(f"Failed to read replies file: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
            return {"processed": 0, "posted": 0, "failed": 0}

    processed = 0
    posted = 0
    failed = 0

    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    for reply_data in replies_data:
        if not reply_data.get("approved", False) or reply_data.get("posted", False):
            continue

        processed += 1

        try:
            log(f"Posting reply to post: {reply_data['post_id']}", verbose, status, log_caller_file="reply_utils.py")

            reply_text = reply_data["generated_reply"]
            post_text = reply_data["post_text"]

            found_post = False
            max_scrolls = 10

            for scroll_attempt in range(max_scrolls):
                if found_post:
                    break

                posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")

                for post in posts:
                    try:
                        post_content = post.text
                        if post_text[:100] in post_content or post_content[:100] in post_text:
                            log(f"Found matching post, attempting to comment", verbose, status, log_caller_file="reply_utils.py")

                            comment_button = post.find_element(By.CSS_SELECTOR, "button[aria-label='Comment']")
                            comment_button.click()
                            time.sleep(2)

                            comment_input = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".ql-editor[data-test-ql-editor-contenteditable='true']"))
                            )

                            safe_text = reply_text.replace('"', '\\"').replace("'", "\\'").replace('\n', '</p><p>')
                            driver.execute_script(f"""
                                arguments[0].innerHTML = '<p>{safe_text}</p>';
                                arguments[0].focus();
                            """, comment_input)

                            time.sleep(2)

                            submit_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".comments-comment-box__submit-button--cr"))
                            )
                            submit_button.click()
                            time.sleep(3)

                            reply_data["posted"] = True
                            reply_data["posted_at"] = datetime.now().isoformat() + "Z"
                            posted += 1
                            found_post = True
                            log(f"Successfully posted reply to {reply_data['post_id']}", verbose, status, log_caller_file="reply_utils.py")
                            break

                    except Exception as e:
                        continue

                if not found_post and scroll_attempt < max_scrolls - 1:
                    log(f"Post not found, scrolling down (attempt {scroll_attempt + 1}/{max_scrolls})", verbose, status, log_caller_file="reply_utils.py")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

            if not found_post:
                log(f"Could not find matching post for reply {reply_data['post_id']}", verbose, is_error=True, log_caller_file="reply_utils.py")
                failed += 1

        except Exception as e:
            log(f"Error posting reply to {reply_data['post_id']}: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
            failed += 1
            continue

    with open(replies_file, 'w', encoding='utf-8') as f:
        json.dump(replies_data, f, indent=2, ensure_ascii=False)

    return {"processed": processed, "posted": 0, "failed": failed}


def generate_linkedin_reply(post_data, api_key_pool, profile_name, verbose=False, status=None):
    api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())

    try:
        post_text = post_data.get("data", {}).get("text", "")
        if not post_text:
            return None

        profile_config = PROFILES.get(profile_name, {})
        properties = profile_config.get('properties', {})
        global_props = properties.get('global', {})
        model_name = global_props.get('model_name', 'gemini-2.5-flash-lite')
        prompts = profile_config.get('prompts', {})
        reply_prompt = prompts.get('reply_generation', 'Generate a professional LinkedIn reply to this post. Keep it concise, engaging, and add value to the conversation.')

        log(f"Using model: {model_name}", verbose, status, log_caller_file="reply_utils.py")

        api_key = api_key_pool.get_key()
        log(f"Got API key: {api_key[-10:] if api_key else 'None'}", verbose, status, log_caller_file="reply_utils.py")
        if not api_key:
            log("No API key available from pool", verbose, is_error=True, log_caller_file="reply_utils.py")
            return None

        can_call, reason = api_call_tracker.can_make_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key[-4:])
        if not can_call:
            log(f"Rate limit: {reason}", verbose, is_error=True, log_caller_file="reply_utils.py")
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        prompt = f"""
        {reply_prompt}

        Post to reply to: "{post_text}"

        Generate exactly ONE reply. Keep it professional, engaging, and under 200 characters. Do not include quotes around your reply.
        """

        response = model.generate_content(prompt)
        reply_text = response.text.strip()

        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key[-4:], success=True)

        return reply_text

    except Exception as e:
        log(f"Error generating reply: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key[-4:] if 'api_key' in locals() else "unknown", success=False)
        return None
