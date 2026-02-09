import os
import time
import json

from rich.status import Status
from rich.console import Console

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from typing import Optional, List, Dict, Tuple, Any

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_instagram_profile_dir

from profiles import PROFILES
from services.platform.instagram.support.scraper_utils import scrape_instagram_reels_comments, move_to_next_reel
from services.platform.instagram.support.video_utils import download_instagram_reel

console = Console()

def generate_instagram_replies(comments_data: list, video_path: str = None, verbose: bool = False, profile: str = None):
    try:
        api_key_pool = APIKeyPool()
        api_call_tracker = APICallTracker()
        rate_limiter = RateLimiter()

        top_comments = comments_data[:10]
        comments_json = json.dumps(top_comments, indent=2)

        if profile and profile in PROFILES and 'prompts' in PROFILES[profile] and 'reply_generation' in PROFILES[profile]['prompts']:
            custom_prompt = PROFILES[profile]['prompts']['reply_generation']
            if custom_prompt.strip():
                prompt_text = custom_prompt
            else:
                prompt_text = (
                    "Analyze the following Instagram Reel comments and the video content.\n"
                    "Generate a single, highly engaging, and relevant reply that could be posted by the channel owner.\n"
                    "Make the reply concise, witty, and positive. Avoid generic phrases.\n\n"
                    f"Top comments (JSON):\n{comments_json}"
                )
        else:
            prompt_text = (
                "Analyze the following Instagram Reel comments and the video content.\n"
                "Generate a single, highly engaging, and relevant reply that could be posted by the channel owner.\n"
                "Make the reply concise, witty, and positive. Avoid generic phrases.\n\n"
                f"Top comments (JSON):\n{comments_json}"
            )

        if video_path and os.path.exists(video_path):
            prompt_text += f"\n\nVideo content is available at: {video_path}"
            prompt_text += "\nThe video is a short, engaging clip. Focus replies on humor and positivity."

        max_api_retries = 3
        for api_attempt in range(max_api_retries):
            try:
                reply, _ = generate_gemini(
                    media_path=video_path if video_path and os.path.exists(video_path) else None,
                    api_key_pool=api_key_pool,
                    api_call_tracker=api_call_tracker,
                    rate_limiter=rate_limiter,
                    prompt_text=prompt_text,
                    model_name='gemini-2.5-flash-lite',
                    status=None,
                    verbose=verbose
                )

                if reply:
                    return reply
                else:
                    log(f"API attempt {api_attempt + 1}: No reply generated", verbose, log_caller_file="replies_utils.py")
                    continue

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "exceeded" in error_str.lower():
                    log(f"API attempt {api_attempt + 1}: Rate limit/quota exceeded, trying next API key", verbose, log_caller_file="replies_utils.py")
                    if api_attempt < max_api_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        return f"Error: All API keys exhausted due to rate limits"
                else:
                    log(f"API attempt {api_attempt + 1}: Unexpected error: {error_str}", verbose, is_error=True, log_caller_file="replies_utils.py")
                    return f"Error: {error_str}"

        return f"Error: No reply generated after {max_api_retries} API attempts"

    except Exception as e:
        log(f"Error generating Instagram reply with Gemini: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return f"Error generating reply: {e}"

def post_instagram_reply(driver, reply_text: str, status: Status, verbose: bool = False):
    try:
        if status:
            status.stop()

        comment_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and @aria-haspopup='menu']"))
        )
        comment_element.click()
        log("Comments section opened successfully.", verbose, log_caller_file="replies_utils.py")
        time.sleep(2)

        initial_input_xpath = "//input[@placeholder='Add a comment…']"
        log(f"Attempting to find initial comment input field with XPath: {initial_input_xpath}", verbose, log_caller_file="replies_utils.py")
        initial_input_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, initial_input_xpath))
        )
        log("Initial comment input field found and is clickable.", verbose, log_caller_file="replies_utils.py")

        ActionChains(driver).move_to_element(initial_input_element).click().perform()
        log("Initial comment input field clicked. Waiting for contenteditable div...", verbose, log_caller_file="replies_utils.py")
        time.sleep(1)

        comment_input_xpath = "//div[@aria-placeholder='Add a comment…' and @contenteditable='true']"
        log(f"Attempting to find contenteditable div with XPath: {comment_input_xpath}", verbose, log_caller_file="replies_utils.py")
        comment_input_div = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, comment_input_xpath))
        )
        log("Contenteditable comment input div found and is clickable.", verbose, log_caller_file="replies_utils.py")
        time.sleep(1)

        driver.execute_script("arguments[0].innerText = '';", comment_input_div)
        log("Cleared existing content in contenteditable div.", verbose, log_caller_file="replies_utils.py")
        time.sleep(0.5)

        log(f"Sending reply text character by character: '{reply_text}'", verbose, log_caller_file="replies_utils.py")
        for char in reply_text:
            comment_input_div.send_keys(char)
            time.sleep(0.05)
        log("Reply text sent character by character.", verbose, log_caller_file="replies_utils.py")
        time.sleep(1)

        post_button_xpath = "//div[contains(text(),'Post')]"
        log(f"Attempting to find post button with XPath: {post_button_xpath}", verbose, log_caller_file="replies_utils.py")
        post_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, post_button_xpath))
        )
        log("Post button found and is clickable.", verbose, log_caller_file="replies_utils.py")

        driver.execute_script("arguments[0].click();", post_button)
        log("Post button clicked via JavaScript.", verbose, log_caller_file="replies_utils.py")

        if status:
            status.update(f"[green]Reply posted successfully![/green]")

        time.sleep(2)
        return True

    except Exception as e:
        log(f"An unexpected error occurred while posting reply: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False

def generate_replies_for_approval(profile, max_comments, number_of_reels, download_reels, verbose, headless):
    generated_replies = []

    user_data_dir = get_browser_data_dir(PROFILES[profile].get('properties', {}).get('global', {}).get('browser_profile', profile))
    profile_base_dir = get_instagram_profile_dir(profile)
    os.makedirs(profile_base_dir, exist_ok=True)

    with Status(f"[white]Initializing WebDriver for profile '{profile}'...[/white]", spinner="dots", console=console) as status:
        driver, setup_messages = setup_driver(user_data_dir, profile=profile, headless=headless)
        for msg in setup_messages:
            status.update(f"[white]{msg}[/white]")
            time.sleep(0.1)
        status.update("[white]WebDriver initialized.[/white]")
    status.stop()

    if not driver:
        log("WebDriver could not be initialized. Aborting.", verbose, is_error=True, log_caller_file="replies_utils.py")
        return [], None

    try:
        with Status("[white]Navigating to Instagram Reels...[/white]", spinner="dots", console=console) as status:
            driver.get("https://www.instagram.com/reels/")
            time.sleep(5)

            if not headless:
                try:
                    driver.execute_script("window.focus();")
                    time.sleep(1)
                except Exception:
                    pass
        status.stop()

        for i in range(number_of_reels):
            video_path = None
            log(f"--- Processing Reel {i+1}/{number_of_reels} ---", verbose, log_caller_file="replies_utils.py")

            html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")

            with Status(f"[white]Running Instagram Replies: Scraping comments for {profile}...[/white]", spinner="dots", console=console) as status:
                structured_comments_for_gemini, reel_url = scrape_instagram_reels_comments(
                    driver=driver,
                    max_comments=max_comments,
                    status=status,
                    html_dump_path=html_dump_path,
                    verbose=verbose,
                    reel_index=i
                )
            status.stop()

            if reel_url and structured_comments_for_gemini:
                log(f"Scraped {len(structured_comments_for_gemini)} comments from {reel_url}.", verbose, log_caller_file="replies_utils.py")

                video_path = None
                if download_reels:
                    videos_props = PROFILES[profile].get('properties', {}).get('platform', {}).get('instagram', {}).get('videos', {})
                    output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')
                    restrict_filenames = videos_props.get('restrict_filenames', True)

                    with Status(f"[white]Downloading Instagram Reel: {reel_url}...[/white]", spinner="dots", console=console) as status:
                        video_path, cdn_link = download_instagram_reel(reel_url, profile, output_format, restrict_filenames, status, verbose=verbose)
                    status.stop()

                    if video_path and cdn_link:
                        log(f"Downloaded reel to: {video_path}", verbose, log_caller_file="replies_utils.py")

                with Status("[white]Generating reply...[/white]", spinner="dots", console=console) as status:
                    generated_reply = generate_instagram_replies(
                        comments_data=structured_comments_for_gemini,
                        video_path=video_path,
                        verbose=verbose,
                        profile=profile
                    )
                    status.stop()

                if generated_reply and not generated_reply.startswith("Error"):
                    log("Generated Reply:", verbose, log_caller_file="replies_utils.py")
                    log(f"{generated_reply}", verbose, log_caller_file="replies_utils.py")

                    reply_data = {
                        "reel_number": i + 1,
                        "reel_url": reel_url,
                        "comments_count": len(structured_comments_for_gemini),
                        "generated_reply": generated_reply,
                        "video_path": video_path,
                        "cdn_link": cdn_link,
                        "approved": False
                    }
                    generated_replies.append(reply_data)
                else:
                    log(f"Failed to generate reply: {generated_reply}", verbose, is_error=True, log_caller_file="replies_utils.py")
            else:
                log("No comments scraped or no reel URL found to generate replies for.", verbose, log_caller_file="replies_utils.py")

            if i < number_of_reels - 1:
                if not move_to_next_reel(driver, verbose=verbose):
                    log("Could not move to the next reel. Ending process.", verbose, log_caller_file="replies_utils.py")
                    break

    except Exception as e:
        log(f"An unexpected error occurred: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        if driver:
            driver.quit()
        return [], None

    return generated_replies, driver


def post_approved_replies(driver, approved_replies, verbose, headless):
    posted = 0
    failed = 0

    if not approved_replies:
        log("No replies to post.", verbose, log_caller_file="replies_utils.py")
        return {"posted": 0, "failed": 0}

    try:
        for reply_data in approved_replies:
            try:
                log(f"Navigating to reel {reply_data['reel_number']}: {reply_data['reel_url']}", verbose, log_caller_file="replies_utils.py")
                driver.get(reply_data["reel_url"])
                time.sleep(3)

                with Status(f"[white]Posting reply to reel {reply_data['reel_number']}...[/white]", spinner="dots", console=console) as status:
                    success = post_instagram_reply(driver, reply_data["generated_reply"], status, verbose=verbose)
                status.stop()

                if success:
                    posted += 1
                    log(f"Successfully posted reply to reel {reply_data['reel_number']}", verbose, log_caller_file="replies_utils.py")
                else:
                    failed += 1
                    log(f"Failed to post reply to reel {reply_data['reel_number']}", verbose, is_error=True, log_caller_file="replies_utils.py")

            except Exception as e:
                failed += 1
                log(f"Error posting reply to reel {reply_data['reel_number']}: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")

    except Exception as e:
        log(f"An unexpected error occurred during posting: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return {"posted": posted, "failed": len(approved_replies) - posted}

    return {"posted": posted, "failed": failed}
