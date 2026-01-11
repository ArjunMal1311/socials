import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log

def create_linkedin_post(driver, text, media_urls=None, verbose=False, status=None):
    try:
        log("Looking for 'Start a post' button...", verbose, status, log_caller_file="post_utils.py")

        post_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Start a post')]")
        if not post_buttons:
            post_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Start a post'], button[aria-label*='Create a post']")
        if not post_buttons:
            post_buttons = driver.find_elements(By.CSS_SELECTOR, "button[data-test-id*='share'], button[data-test-id*='post']")
        if not post_buttons:
            post_buttons = driver.find_elements(By.CSS_SELECTOR, ".share-box button, .feed-shared-control button")

        if post_buttons:
            log(f"Found {len(post_buttons)} post button(s), clicking first one", verbose, status, log_caller_file="post_utils.py")
            post_buttons[0].click()
            time.sleep(3)
        else:
            log("Could not find post button on current page, refreshing and trying again", verbose, status, log_caller_file="post_utils.py")
            driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)

            post_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Start a post')]")
            if not post_buttons:
                post_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Start a post']")

            if post_buttons:
                log(f"Found {len(post_buttons)} post button(s) after refresh, clicking first one", verbose, status, log_caller_file="post_utils.py")
                post_buttons[0].click()
                time.sleep(3)
            else:
                log("Available buttons on page:", verbose, status, log_caller_file="post_utils.py")
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                for i, btn in enumerate(all_buttons[:10]):
                    try:
                        text = btn.text.strip()[:50] if btn.text.strip() else "no text"
                        aria = btn.get_attribute("aria-label")[:50] if btn.get_attribute("aria-label") else "no aria"
                        log(f"Button {i}: text='{text}', aria='{aria}'", verbose, status, log_caller_file="post_utils.py")
                    except:
                        pass
                raise Exception("Could not find post creation button")

        log("Looking for text editor...", verbose, status, log_caller_file="post_utils.py")
        text_editor = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".ql-editor[data-test-ql-editor-contenteditable='true'], [contenteditable='true'][aria-label*='Text editor']"))
        )

        log("Clicking on text editor...", verbose, status, log_caller_file="post_utils.py")
        text_editor.click()
        time.sleep(2)

        log(f"Setting text content using JavaScript: {text[:50]}...", verbose, status, log_caller_file="post_utils.py")

        try:
            safe_text = text.replace('"', '\\"').replace("'", "\\'").replace('\n', '</p><p>')
            driver.execute_script(f"""
                arguments[0].innerHTML = '<p>{safe_text}</p>';
                arguments[0].focus();
            """, text_editor)

            time.sleep(1)

            entered_text = driver.execute_script("return arguments[0].textContent;", text_editor)
            log(f"Text editor content after input: {entered_text[:50] if entered_text else 'empty'}", verbose, status, log_caller_file="post_utils.py")

        except Exception as e:
            log(f"JavaScript text input failed, trying send_keys fallback: {e}", verbose, status, log_caller_file="post_utils.py")

            try:
                clean_text = ''.join(c for c in text if ord(c) < 0x10000)[:500]
                text_editor.send_keys(clean_text)
                log("Fallback send_keys worked for BMP-compatible text", verbose, status, log_caller_file="post_utils.py")
            except Exception as e2:
                log(f"Both text input methods failed: JS={e}, send_keys={e2}", verbose, is_error=True, log_caller_file="post_utils.py")
                raise Exception(f"Could not input text: {e}")

        log("Post text entered successfully", verbose, status, log_caller_file="post_utils.py")
        time.sleep(2)
        time.sleep(2)

        if media_urls:
            log("Adding media to post...", verbose, status, log_caller_file="post_utils.py")
            media_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Add media'], button[aria-label*='Add a photo']")

            if media_buttons:
                media_buttons[0].click()
                time.sleep(2)

                file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    for media_url in media_urls:
                        if media_url.startswith('http'):
                            continue

                        if os.path.exists(media_url):
                            file_inputs[0].send_keys(media_url)
                            time.sleep(3)
                            log(f"Added media: {media_url}", verbose, status, log_caller_file="post_utils.py")
                        else:
                            log(f"Media file not found: {media_url}", verbose, is_error=True, log_caller_file="post_utils.py")

                    time.sleep(5)

                    try:
                        next_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Next'], .share-box-footer__primary-btn"))
                        )
                        next_button.click()
                        log("Clicked Next button after media upload", verbose, status, log_caller_file="post_utils.py")
                        time.sleep(2)
                    except Exception as e:
                        log(f"Next button not found or not needed: {e}", verbose, status, log_caller_file="post_utils.py")
                else:
                    log("Could not find file input for media", verbose, is_error=True, log_caller_file="post_utils.py")

        log("Clicking post button...", verbose, status, log_caller_file="post_utils.py")
        post_submit_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Post'], button.share-actions__primary-action")

        if post_submit_buttons:
            post_button = None
            for btn in post_submit_buttons:
                if btn.is_enabled() and btn.is_displayed():
                    post_button = btn
                    break

            if post_button:
                post_button.click()
                time.sleep(5)

                success_indicators = driver.find_elements(By.CSS_SELECTOR, ".share-toast, [data-test-id*='success']")
                if success_indicators:
                    log("Post published successfully", verbose, status, log_caller_file="post_utils.py")
                    return True
                else:
                    log("Post may have been published (no clear success indicator)", verbose, status, log_caller_file="post_utils.py")
                    return True
            else:
                log("Post button not enabled", verbose, is_error=True, log_caller_file="post_utils.py")
                return False
        else:
            log("Could not find post submit button", verbose, is_error=True, log_caller_file="post_utils.py")
            return False

    except Exception as e:
        log(f"Error creating LinkedIn post: {e}", verbose, is_error=True, log_caller_file="post_utils.py")
        return False
