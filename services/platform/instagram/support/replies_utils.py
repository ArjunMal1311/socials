import os
import time
import json

from rich.status import Status
from rich.console import Console

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_instagram_profile_dir

from profiles import PROFILES

from services.platform.instagram.support.video_utils import download_instagram_videos
from services.platform.instagram.support.scout_utils import scout_instagram_reels_comments, move_to_next_reel

from services.support.storage.storage_factory import get_storage

console = Console()

def generate_instagram_replies(comments_data: list, video_path: str = None, verbose: bool = False, profile: str = None, replies: list = None):
    try:
        api_key_pool = APIKeyPool()
        api_call_tracker = APICallTracker()
        rate_limiter = RateLimiter()

        top_comments = comments_data[:10]
        comments_json = json.dumps(top_comments, indent=2)

        sample_section = ''
        if replies:
            approved_examples = []
            for r in replies:
                if r.get('approved') and r.get('reply'):
                    context_text = r.get('reel_text', 'Previous Context')
                    approved_examples.append(f"Content: {context_text}\nApproved Reply: {r['reply']}")
            
            if approved_examples:
                sample_section = 'Sample approved content-reply pairs from this account:\n' + '\n---\n'.join(approved_examples) + '\n\n'

        if profile and profile in PROFILES and 'prompts' in PROFILES[profile] and 'reply_generation' in PROFILES[profile]['prompts']:
            custom_prompt = PROFILES[profile]['prompts']['reply_generation']
        else:
            custom_prompt = "Generate a single, highly engaging, and relevant reply that could be posted by me as a person"

        prompt_text = f"""{custom_prompt}
            {sample_section}

            Analyze the following Instagram Reel comments and the video content.
            Make the reply concise, witty, and positive. Avoid generic phrases.

            Top comments (JSON):
            {comments_json}
        """

        if video_path and os.path.exists(video_path):
            prompt_text += f"\nVideo content (visual context) is available."
            prompt_text += "\nFocus replies on humor and positivity related to the visual content."

        prompt_text += "\n\nImportant: Generate exactly ONE reply. Do not provide multiple options or explanations. Do not include quotes around your reply. Take inspiration from the sample_section for writing style and tone."
        prompt_text += "\nJust write a single direct reply."

        profile_props = PROFILES.get(profile, {}).get('properties', {})
        global_props = profile_props.get('global', {})
        model_name = global_props.get('model_name', 'gemini-2.5-flash-lite')

        reply, _ = generate_gemini(
            media_path=video_path if video_path and os.path.exists(video_path) else None,
            api_key_pool=api_key_pool,
            api_call_tracker=api_call_tracker,
            rate_limiter=rate_limiter,
            prompt_text=prompt_text,
            model_name=model_name,
            status=None,
            verbose=verbose
        )

        if reply:
            return reply.strip().replace('"', '').replace('"', '')
        
        return "Error: No reply generated"

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

    user_data_dir = get_browser_data_dir(PROFILES[profile].get('properties', {}).get('global', {}).get('browser_profile', profile), platform="instagram")
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
        replies_context = []
        try:
            storage = get_storage('instagram', profile, 'action', verbose)
            if storage and hasattr(storage, 'get_all_approved_and_posted_reels'):
                replies_context = storage.get_all_approved_and_posted_reels(verbose)
                log(f"Loaded {len(replies_context)} approved and posted reels for context", verbose, log_caller_file="replies_utils.py")
        except Exception as e:
            log(f"Warning: Could not initialize Instagram storage for context: {e}", verbose, log_caller_file="replies_utils.py")

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
            log(f"Processing Reel {i+1}/{number_of_reels}", verbose, log_caller_file="replies_utils.py")

            html_dump_path = os.path.join(profile_base_dir, "instagram_comments_dump.html")

            with Status(f"[white]Running Instagram Replies: Scraping comments for {profile}...[/white]", spinner="dots", console=console) as status:
                comments, reel_url = scout_instagram_reels_comments(
                    driver=driver,
                    max_comments=max_comments,
                    status=status,
                    html_dump_path=html_dump_path,
                    verbose=verbose,
                    reel_index=i
                )
            status.stop()

            if reel_url and comments:
                log(f"Scraped {len(comments)} comments from {reel_url}.", verbose, log_caller_file="replies_utils.py")

                video_path = None
                if download_reels:
                    videos_props = PROFILES[profile].get('properties', {}).get('platform', {}).get('instagram', {}).get('videos', {})
                    output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')
                    restrict_filenames = videos_props.get('restrict_filenames', True)

                    with Status(f"[white]Downloading Instagram Reel: {reel_url}...[/white]", spinner="dots", console=console) as status:
                        video_path, cdn_link = download_instagram_videos(reel_url, profile, output_format, restrict_filenames, status, verbose=verbose, extract_cdn_links=True, use_reels_dir=True)
                    status.stop()

                    if video_path and cdn_link:
                        log(f"Downloaded reel to: {video_path}", verbose, log_caller_file="replies_utils.py")

                with Status("[white]Generating reply...[/white]", spinner="dots", console=console) as status:
                    generated_reply = generate_instagram_replies(
                        comments_data=comments,
                        video_path=video_path,
                        verbose=verbose,
                        profile=profile,
                        replies=replies_context
                    )
                    status.stop()

                if generated_reply and not generated_reply.startswith("Error"):
                    log("Generated Reply:", verbose, log_caller_file="replies_utils.py")
                    log(f"{generated_reply}", verbose, log_caller_file="replies_utils.py")

                    reply_data = {
                        "reel_number": i + 1,
                        "reel_url": reel_url,
                        "comments_count": len(comments),
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
