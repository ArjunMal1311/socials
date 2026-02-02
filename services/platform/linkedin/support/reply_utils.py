import re
import os
import json
import time
import google.generativeai as genai

from bs4 import BeautifulSoup
from datetime import datetime
from profiles import PROFILES

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.web_driver_handler import setup_driver
from services.support.api_call_tracker import APICallTracker
from services.support.storage.storage_factory import get_storage
from services.support.path_config import get_browser_data_dir, get_gemini_log_file_path, get_linkedin_replies_dir

from services.platform.linkedin.support.scraper_utils import scrape_linkedin_feed_posts

def run_linkedin_reply_mode(profile_name: str, browser_profile_name: str, max_posts: int = 10, verbose: bool = False, headless: bool = True, status=None, browser_data_dir: str = None):
    user_data_dir = browser_data_dir or get_browser_data_dir(browser_profile_name)
    log(f"LinkedIn Mode: user_data_dir is {user_data_dir}", verbose, status, log_caller_file="reply_utils.py")

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
        if api_key_pool.size() == 0:
            log("No API keys available for reply generation", verbose, is_error=True, log_caller_file="reply_utils.py")
            driver.quit()
            return None, []

        storage = get_storage('linkedin', profile_name, 'action', verbose)
        all_replies = []
        if storage:
            all_replies = storage.get_all_approved_and_posted_replies(verbose)
            log(f"Loaded {len(all_replies)} approved and posted replies for context", verbose, status, log_caller_file="reply_utils.py")
        else:
            log("Warning: Could not initialize storage for approved replies context", verbose, status, log_caller_file="reply_utils.py")

        replies_data = []
        for i, post in enumerate(feed_posts):
            generated_reply = generate_linkedin_reply(post, api_key_pool, profile_name, all_replies, verbose=verbose, status=status)

            reply_data = {
                "post_id": post.get("data", {}).get("post_id", f"linkedin_{i}"),
                "post_urn": post.get("data", {}).get("post_urn"),
                "post_text": post.get("data", {}).get("text", ""),
                "profile_url": post.get("data", {}).get("profile_url", ""),
                "author_name": post.get("data", {}).get("author_name", ""),
                "post_date": post.get("data", {}).get("post_date", ""),
                "media_urls": post.get("data", {}).get("media_urls", []),
                "engagement": post.get("engagement", {}),
                "generated_reply": generated_reply,
                "approved": False,
                "posted": False,
                "created_at": datetime.now().isoformat() + "Z"
            }
            replies_data.append(reply_data)

        replies_file = os.path.join(get_linkedin_replies_dir(profile_name), "replies.json")
        os.makedirs(os.path.dirname(replies_file), exist_ok=True)

        with open(replies_file, 'w', encoding='utf-8') as f:
            json.dump(replies_data, f, indent=2, ensure_ascii=False)

        return driver, replies_data

    except Exception as e:
        log(f"Error in reply generation: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
        if 'driver' in locals():
            driver.quit()
        return None, []


def post_approved_linkedin_replies(driver, profile_name: str, verbose: bool = False, status=None, replies_file_path: str = None):
    if replies_file_path:
        replies_file = replies_file_path
    else:
        replies_file = os.path.join(get_linkedin_replies_dir(profile_name), "replies.json")

    if not os.path.exists(replies_file):
        log(f"Replies file not found: {replies_file}", verbose, is_error=True, log_caller_file="reply_utils.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    with open(replies_file, 'r', encoding='utf-8') as f:
        try:
            replies_data = json.load(f)
        except Exception as e:
            log(f"Failed to read replies file: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
            return {"processed": 0, "posted": 0, "failed": 0}

    api_key_pool = APIKeyPool(verbose=verbose)
    if api_key_pool.size() == 0:
        log("No API keys available for reply generation", verbose, is_error=True, log_caller_file="reply_utils.py")
        return {"processed": 0, "posted": 0, "failed": 0}

    processed = 0
    posted = 0
    failed = 0


    for reply_data in replies_data:
        if not reply_data.get("approved", False) or reply_data.get("posted", False):
            continue

        processed += 1

        try:
            log(f"Posting reply to post: {reply_data['post_id']}", verbose, status, log_caller_file="reply_utils.py")

            reply_text = reply_data["generated_reply"]
            post_urn = reply_data.get("post_urn")

            if not post_urn:
                log(f"No URN found for post {reply_data['post_id']}, skipping", verbose, is_error=True, log_caller_file="reply_utils.py")
                failed += 1
                continue

            found_post = False
            max_scrolls = 10

            log("Loading posts by scrolling down to expand feed...", verbose, status, log_caller_file="reply_utils.py")

            scroll_element = None
            try:
                scroll_element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "workspace"))
                )
            except:
                try:
                    scroll_element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "main.scaffold-layout__main"))
                    )
                except:
                    scroll_element = driver.find_element(By.TAG_NAME, "body")

            if scroll_element:
                driver.execute_script("arguments[0].scrollTo(0, 0);", scroll_element)
                time.sleep(2)
            else:
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)

            if scroll_element:
                pass

            for scroll_attempt in range(max_scrolls):
                if found_post:
                    break

                posts = driver.find_elements(By.CSS_SELECTOR, "[data-view-name=\"feed-full-update\"]")
                log(f"Scroll attempt {scroll_attempt + 1}/{max_scrolls}: Checking {len(posts)} posts in current view for URN {post_urn}", verbose, status, log_caller_file="reply_utils.py")

                for post in posts:
                    try:
                        current_post_outer_html = post.get_attribute("outerHTML")
                        current_urn = ""
                        tracking_scope_element = BeautifulSoup(current_post_outer_html, 'html.parser').select_one('[data-view-tracking-scope]')
                        if tracking_scope_element:
                            data_view_tracking_scope = tracking_scope_element.get('data-view-tracking-scope', '')
                            if data_view_tracking_scope:
                                try:
                                    json_data = json.loads(data_view_tracking_scope)
                                    if isinstance(json_data, list) and len(json_data) > 0 and "breadcrumb" in json_data[0] and \
                                       "content" in json_data[0]["breadcrumb"] and "data" in json_data[0]["breadcrumb"]["content"]:
                                        buffer_data = json_data[0]["breadcrumb"]["content"]["data"]
                                        decoded_string = "".join([chr(b) for b in buffer_data])
                                        urn_match = re.search(r'activity:(\d{19})', decoded_string)
                                        if urn_match:
                                            current_urn = "urn:li:activity:" + urn_match.group(1)
                                except json.JSONDecodeError:
                                    pass

                        if not current_urn:
                            fallback_match = re.search(r'(?:activity|ugcPost):(\d{19})', current_post_outer_html)
                            if fallback_match:
                                current_urn = "urn:li:" + fallback_match.group(0)


                        if current_urn == post_urn:
                            log(f"Found matching post by URN {current_urn}, attempting to comment", verbose, status, log_caller_file="reply_utils.py")
                        elif current_urn:
                            log(f"Post URN {current_urn} does not match target {post_urn}", verbose, status, log_caller_file="reply_utils.py")
                        else:
                            log(f"No URN found for current post", verbose, status, log_caller_file="reply_utils.py")

                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", post)
                            time.sleep(2)

                            comment_button = post.find_element(By.CSS_SELECTOR, "button[data-view-name='feed-comment-button']")
                            log(f"Clicking comment button for post {reply_data['post_id']}", verbose, status, log_caller_file="reply_utils.py")
                            comment_button.click()
                            time.sleep(6)  # Increased wait time for comment box to appear

                            log(f"Clicked comment button, looking for comment input", verbose, status, log_caller_file="reply_utils.py")

                            try:
                                all_contenteditable = driver.find_elements(By.CSS_SELECTOR, "[contenteditable=\"true\"]")
                                comment_inputs = []
                                for elem in all_contenteditable:
                                    try:
                                        comment_container = elem.find_element(By.XPATH, "ancestor-or-self::*[contains(@data-view-name, 'comment') or contains(@class, 'comments-comment-box') or contains(@class, 'comment-box')][1]")
                                        if comment_container:
                                            comment_inputs.append(elem)
                                    except:
                                        continue

                                if comment_inputs:
                                    active_input = None
                                    for inp in comment_inputs:
                                        if inp == driver.switch_to.active_element:
                                            active_input = inp
                                            break
                                    if not active_input and post:
                                        post_location = post.location
                                        closest_input = None
                                        min_distance = float('inf')

                                        for inp in comment_inputs:
                                            try:
                                                inp_location = inp.location
                                                distance = abs(inp_location['y'] - post_location['y'])
                                                if distance < min_distance:
                                                    min_distance = distance
                                                    closest_input = inp
                                            except:
                                                continue

                                        active_input = closest_input
                                    if not active_input and comment_inputs:
                                        active_input = comment_inputs[-1]

                                    if active_input:
                                        comment_input = active_input
                                    else:
                                        raise Exception("No suitable comment input found")
                                else:
                                    raise Exception("No comment inputs found in comment containers")

                            except Exception as e:
                                try:
                                    comment_input = WebDriverWait(driver, 15).until(
                                        lambda d: d.find_element(By.CSS_SELECTOR, "[data-view-name=\"comment-box\"] [contenteditable=\"true\"]")
                                    )
                                except Exception as e2:
                                    log(f"Failed to find comment input with direct fallback: {e2}", verbose, is_error=True, log_caller_file="reply_utils.py")
                                    continue

                            safe_text = reply_text.replace('"', '\\"').replace("'", "\\'").replace('\n', '</p><p>')
                            driver.execute_script(f"""
                                arguments[0].innerHTML = '<p>{safe_text}</p>';
                                arguments[0].focus();
                            """, comment_input)

                            time.sleep(4)


                            try:
                                comment_container = comment_input.find_element(By.XPATH, "ancestor::*[contains(@data-view-name, 'comment') or contains(@class, 'comments-comment-box') or contains(@class, 'comment-box')][1]")

                                submit_button = WebDriverWait(comment_container, 15).until(
                                    lambda c: c.find_element(By.CSS_SELECTOR, "button[data-view-name=\"comment-post\"]") or
                                              c.find_element(By.CSS_SELECTOR, "button[data-test-id=\"comment-submit\"]") or
                                              c.find_element(By.CSS_SELECTOR, ".comments-comment-box__submit-button") or
                                              c.find_element(By.CSS_SELECTOR, "button[type=\"submit\"]") or
                                              c.find_element(By.CSS_SELECTOR, "button[data-view-name=\"comment-submit\"]") or
                                              c.find_element(By.CSS_SELECTOR, "button[aria-label=\"Post comment\"]") or
                                              c.find_element(By.CSS_SELECTOR, "button[aria-label=\"Post\"]") or
                                              c.find_element(By.CSS_SELECTOR, "button:last-child")
                                )
                            except Exception as e:
                                try:
                                    all_submit_buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-view-name=\"comment-post\"], button[data-test-id=\"comment-submit\"], .comments-comment-box__submit-button, button[type=\"submit\"], button[aria-label=\"Post comment\"], button[aria-label=\"Post\"]")

                                    if all_submit_buttons:
                                        comment_input_location = comment_input.location
                                        closest_button = None
                                        min_distance = float('inf')

                                        for btn in all_submit_buttons:
                                            try:
                                                btn_location = btn.location
                                                distance = abs(btn_location['y'] - comment_input_location['y'])
                                                if distance < min_distance:
                                                    min_distance = distance
                                                    closest_button = btn
                                            except:
                                                continue

                                        if closest_button:
                                            submit_button = closest_button
                                        else:
                                            raise Exception("No suitable submit button found")
                                    else:
                                        raise Exception("No submit buttons found globally")

                                except Exception as e2:
                                    log(f"Failed to find submit button with any method: {e2}", verbose, is_error=True, log_caller_file="reply_utils.py")
                                    continue
                            submit_button.click()
                            time.sleep(6)

                            reply_data["posted"] = True
                            reply_data["posted_at"] = datetime.now().isoformat() + "Z"
                            posted += 1
                            found_post = True
                            log(f"Successfully posted reply to {reply_data['post_id']}", verbose, status, log_caller_file="reply_utils.py")
                            break

                    except Exception as e:
                        continue

                if not found_post and scroll_attempt < max_scrolls - 1:
                    log(f"Post not found, scrolling down very slowly (attempt {scroll_attempt + 1}/{max_scrolls})", verbose, status, log_caller_file="reply_utils.py")
                    driver.execute_script("window.scrollBy(0, 300);")
                    time.sleep(8)

            if not found_post:
                log(f"Could not find matching post for reply {reply_data['post_id']} (URN: {post_urn}) after {max_scrolls} scroll attempts", verbose, is_error=True, log_caller_file="reply_utils.py")
                failed += 1

        except Exception as e:
            log(f"Error posting reply to {reply_data['post_id']}: {e}", verbose, is_error=True, log_caller_file="reply_utils.py")
            failed += 1
            continue

    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    with open(replies_file, 'w', encoding='utf-8') as f:
        json.dump(replies_data, f, indent=2, ensure_ascii=False, default=serialize_datetime)

    return {"processed": processed, "posted": posted, "failed": failed}


def generate_linkedin_reply(post_data, api_key_pool, profile_name, all_replies=None, verbose=False, status=None):
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

        context_section = ""
        if all_replies:
            context_replies = "\n".join([f"- {reply.get('generated_reply', '')}" for reply in all_replies if reply.get('generated_reply')])
            if context_replies:
                context_section = f"""
                Previously approved/posted replies for context (avoid generating similar responses):
                {context_replies}
            """

        prompt = f"""
        {reply_prompt}

        {context_section}
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
