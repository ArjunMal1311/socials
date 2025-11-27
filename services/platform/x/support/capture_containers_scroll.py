import time

from rich.console import Console
from selenium.webdriver.common.by import By
from services.support.logger_util import _log as log

console = Console()

def capture_containers_and_scroll(driver, raw_containers, processed_tweet_ids, no_new_content_count, scroll_count, verbose: bool = False, status=None):
    tweet_elements = driver.find_elements(By.CSS_SELECTOR, 'article[data-testid="tweet"]')
    log(f"DEBUG: Found {len(tweet_elements)} tweet articles.", verbose, status=status, log_caller_file="capture_containers_scroll.py")

    new_containers_found_in_this_pass = 0
    for tweet_element in tweet_elements:
        try:
            links = tweet_element.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
            
            if not links:
                log(f"DEBUG: Tweet article has no /status/ link. Text: {tweet_element.text[:50]}...", verbose, is_error=False, status=status, log_caller_file="capture_containers_scroll.py")
                continue
            
            url = None
            for link in links:
                href = link.get_attribute("href")
                if href and '/status/' in href and '/analytics' not in href:
                    url = href
                    break
            
            if not url:
                log(f"DEBUG: No valid tweet URL found in article. Text: {tweet_element.text[:50]}...", verbose, is_error=False, status=status, log_caller_file="capture_containers_scroll.py")
                continue

            tweet_id = url.split("/status/")[1].split("?")[0]
            if tweet_id in processed_tweet_ids:
                log(f"DEBUG: Skipping already processed tweet ID: {tweet_id}", verbose, is_error=False, status=status, log_caller_file="capture_containers_scroll.py")
                continue

            profile_image_url = ""
            try:
                profile_image_element = tweet_element.find_element(By.CSS_SELECTOR, 'a[href^="/"] img')
                profile_image_url = profile_image_element.get_attribute('src')
                log(f"DEBUG (capture_containers_and_scroll): Extracted profile_image_url: {profile_image_url}", verbose, status=status, log_caller_file="capture_containers_scroll.py")
            except Exception as img_e:
                log(f"DEBUG: Could not extract profile image for tweet ID {tweet_id}: {img_e}", verbose, is_error=False, status=status, log_caller_file="capture_containers_scroll.py")

            container_html = tweet_element.get_attribute('outerHTML')
            container_text = tweet_element.text

            log(f"DEBUG: New tweet found - URL: {url}, ID: {tweet_id}. Total processed: {len(processed_tweet_ids) + 1}", verbose, status=status, log_caller_file="capture_containers_scroll.py")
            processed_tweet_ids.add(tweet_id)
            raw_containers.append({
                'html': container_html,
                'text': container_text,
                'url': url,
                'tweet_id': tweet_id,
                'profile_image_url': profile_image_url
            })
            new_containers_found_in_this_pass += 1
        except Exception as e:
            log(f"[ERROR] Exception processing tweet article: {e}", verbose, is_error=True, status=status, log_caller_file="capture_containers_scroll.py")
            continue

    viewport_height = driver.execute_script("return window.innerHeight")
    current_position = driver.execute_script("return window.pageYOffset")
    scroll_amount = viewport_height * 0.8

    driver.execute_script(f"window.scrollTo(0, {current_position + scroll_amount})")
    time.sleep(0.5)

    if new_containers_found_in_this_pass == 0:
        no_new_content_count += 1
    else:
        no_new_content_count = 0
    
    return no_new_content_count, scroll_count, new_containers_found_in_this_pass