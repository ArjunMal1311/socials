import os
import re
import json
import time

from typing import List, Dict, Any
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir

def parse_linkedin_relative_date(relative_date_str):
    if not relative_date_str or not isinstance(relative_date_str, str):
        return datetime.now().isoformat() + "Z"

    cleaned = relative_date_str.strip().replace('•', '').strip()

    try:
        match = re.match(r'(\d+)([mhdw])', cleaned.lower())
        if not match:
            return datetime.now().isoformat() + "Z"

        number = int(match.group(1))
        unit = match.group(2)

        now = datetime.now()

        if unit == 'm':
            delta = timedelta(minutes=number)
        elif unit == 'h':
            delta = timedelta(hours=number)
        elif unit == 'd':
            delta = timedelta(days=number)
        elif unit == 'w':
            delta = timedelta(weeks=number)
        else:
            return datetime.now().isoformat() + "Z"

        post_datetime = now - delta
        return post_datetime.isoformat() + "Z"

    except Exception:
        return datetime.now().isoformat() + "Z"

def scout_linkedin_profiles(linkedin_target_profiles: List[str], profile_name: str, max_posts_per_profile: int = 10, headless: bool = True, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    all_posts = []

    for profile_url in linkedin_target_profiles:
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        log(f"Processing profile: {profile_url}", verbose, status=status, log_caller_file="scout_utils.py")

        for i in range(min(max_posts_per_profile, 5)):
            post_data = {
                "source": "linkedin",
                "scraped_at": datetime.now().isoformat() + "Z",
                "data": {
                    "post_id": f"linkedin_dummy_{int(time.time())}_{i}",
                    "text": f"This is a sample LinkedIn post #{i+1} from profile {profile_url}. It contains some interesting content about technology and innovation in the industry.",
                    "author_name": f"User {profile_url.split('/')[-1].replace('-', ' ').title()}",
                    "profile_url": profile_url,
                    "post_date": (datetime.now().replace(hour=datetime.now().hour - i)).isoformat() + "Z",
                    "media_urls": []
                },
                "engagement": {
                    "likes": 25 + i * 5,
                    "comments": 3 + i,
                    "reposts": 1 + i
                }
            }
            all_posts.append(post_data)

        log(f"Generated {min(max_posts_per_profile, 5)} dummy posts from {profile_url}", verbose, status=status, log_caller_file="scout_utils.py")

    log(f"Total dummy posts generated: {len(all_posts)}", verbose, status=status, log_caller_file="scout_utils.py")

    return all_posts

def scout_linkedin_feed_posts(profile_name: str, max_posts: int = 10, headless: bool = True, status=None, verbose: bool = False, existing_driver=None) -> List[Dict[str, Any]]:
    all_posts = []
    processed_posts = []
    driver = existing_driver

    if driver is None:
        user_data_dir = get_browser_data_dir(profile_name)
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, status=status, headless=headless)
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="scout_utils.py")

    try:
        log("Navigating to LinkedIn feed...", verbose, status=status, log_caller_file="scout_utils.py")
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

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
            last_height = driver.execute_script("return arguments[0].scrollHeight", scroll_element)
            scroll_attempt = 0
            max_scroll_attempts = 2
            while True:
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_element)
                time.sleep(5)
                new_height = driver.execute_script("return arguments[0].scrollHeight", scroll_element)
                if new_height == last_height or scroll_attempt >= max_scroll_attempts:
                    break
                last_height = new_height
                scroll_attempt += 1
        log("Scraping LinkedIn feed posts...", verbose, status=status, log_caller_file="scout_utils.py")

        debug_dir = "tmp/debug"
        os.makedirs(debug_dir, exist_ok=True)

        posts_scoutd = 0
        scroll_attempts = 0
        max_scrolls = 5
        processed_post_ids = set()

        while posts_scoutd < max_posts and scroll_attempts < max_scrolls:
            try:
                posts = driver.find_elements(By.CSS_SELECTOR, "[data-view-name=\"feed-full-update\"]")
                log(f"Found {len(posts)} posts on page", verbose, status=status, log_caller_file="scout_utils.py")

                new_posts_found = False
                for post in posts:
                    if "Promoted" in post.get_attribute("outerHTML"):
                        log("Skipping promoted post.", verbose, status=status, log_caller_file="scout_utils.py")
                        continue

                    if posts_scoutd >= max_posts:
                        break

                    try:
                        post_id = f"post_{hash(post.text[:100])}"

                        if post_id in processed_post_ids:
                            continue

                        processed_post_ids.add(post_id)

                        html_content = post.get_attribute("outerHTML")
                        html_file = os.path.join(debug_dir, f"post_{posts_scoutd + 1}_{int(time.time())}.html")

                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)

                        all_posts.append({"html_file": html_file, "post_id": post_id})
                        posts_scoutd += 1
                        new_posts_found = True
                        log(f"Saved HTML for post {posts_scoutd}/{max_posts}: {html_file}", verbose, status=status, log_caller_file="scout_utils.py")
                    except Exception as e:
                        log(f"Error saving post HTML: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
                        continue

                if posts_scoutd >= max_posts:
                    break

                if not new_posts_found and scroll_attempts >= 2:
                    log("No new posts found in last scroll, stopping", verbose, status=status, log_caller_file="scout_utils.py")
                    break


            except Exception as e:
                log(f"Error during scrolling: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
                break

        log(f"Scoutd {len(all_posts)} LinkedIn feed posts", verbose, status=status, log_caller_file="scout_utils.py")

        log("Processing saved HTML files...", verbose, status=status, log_caller_file="scout_utils.py")
        processed_posts = []
        for post_info in all_posts:
            try:
                html_file = post_info["html_file"]
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                post_data = extract_post_data_from_html(html_content)
                if post_data:
                    processed_posts.append(post_data)
                    log(f"Processed post from {os.path.basename(html_file)}", verbose, status=status, log_caller_file="scout_utils.py")

            except Exception as e:
                log(f"Error processing HTML file {post_info.get('html_file', 'unknown')}: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
                continue

        log(f"Successfully processed {len(processed_posts)} posts from HTML", verbose, status=status, log_caller_file="scout_utils.py")


    except Exception as e:
        log(f"Error in feed scraping: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
    finally:
        if existing_driver is None and driver:
            driver.quit()

    return processed_posts

def extract_post_data_from_html(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        post_wrapper = soup.select_one('[data-view-name="feed-full-update"]')
        if not post_wrapper:
            return None

        post_id = f"linkedin_feed_{int(time.time() * 1000000)}"
        post_urn = ""
        
        author_name = ""
        profile_url = ""
        post_text = ""
        post_date = datetime.now().isoformat() + "Z"
        media_urls = []
        likes_count = 0
        comments_count = 0
        reposts_count = 0

        text_element = post_wrapper.select_one('[data-view-name="feed-commentary"]')
        if text_element:
            post_text = text_element.get_text(strip=True)

        author_name_elem = post_wrapper.select_one('[data-view-name="feed-header-text"] strong')
        if author_name_elem:
            author_name = author_name_elem.get_text(strip=True)

        profile_url_elem = post_wrapper.select_one('a[data-view-name="feed-actor-image"]')
        if profile_url_elem:
            profile_url = profile_url_elem.get('href', '').split('?')[0]

        date_element = post_wrapper.select_one('svg[id="globe-americas-small"]')
        if date_element:
            parent_span_p = date_element.find_parent(['span', 'p'])
            if parent_span_p:
                relative_date = parent_span_p.get_text(strip=True)
                post_date = parse_linkedin_relative_date(relative_date)

        img_elements = post_wrapper.select('[data-view-name="image"] img')
        for img in img_elements:
            media_url = img.get('src')
            if media_url and "http" in media_url:
                media_urls.append(media_url)
        video_elements = post_wrapper.select('video')
        for video in video_elements:
            media_url = video.get('src')
            if media_url and "http" in media_url:
                media_urls.append(media_url)

        likes_elem = post_wrapper.select_one('[data-view-name="feed-reaction-count"]')
        if likes_elem:
            likes_text = likes_elem.get_text(strip=True)
            likes_match = re.search(r'(\d+)', likes_text)
            if likes_match:
                likes_count = int(likes_match.group(1))

        comments_elem = post_wrapper.select_one('[data-view-name="feed-comment-count"]')
        if comments_elem:
            comments_text = comments_elem.get_text(strip=True)
            comments_match = re.search(r'(\d+)', comments_text)
            if comments_match:
                comments_count = int(comments_match.group(1))

        reposts_elem = post_wrapper.select_one('[data-view-name="feed-repost-count"]')
        if reposts_elem:
            reposts_text = reposts_elem.get_text(strip=True)
            reposts_match = re.search(r'(\d+)', reposts_text)
            if reposts_match:
                reposts_count = int(reposts_match.group(1))

        if not post_text:
            return None

        post_urn = ""
        tracking_scope_element = post_wrapper.select_one('[data-view-tracking-scope]')
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
                            post_urn = "urn:li:activity:" + urn_match.group(1)
                except json.JSONDecodeError:
                    log("JSON Parse failed for data-view-tracking-scope, trying fallback...", verbose=False, is_error=False, log_caller_file="scout_utils.py")

        if not post_urn:
            html = post_wrapper.get_attribute("outerHTML")
            fallback_match = re.search(r'(?:activity|ugcPost):(\d{19})', html)
            if fallback_match:
                post_urn = "urn:li:" + fallback_match.group(0)

        return {
            "source": "linkedin",
            "scraped_at": datetime.now().isoformat() + "Z",
            "data": {
                "post_id": post_id,
                "post_urn": post_urn,
                "text": post_text,
                "author_name": author_name,
                "profile_url": profile_url,
                "post_date": post_date,
                "media_urls": media_urls
            },
            "engagement": {
                "likes": likes_count,
                "comments": comments_count,
                "reposts": reposts_count
            }
        }

    except Exception as e:
        log(f"Error extracting post data from HTML: {e}", verbose=False, is_error=True, log_caller_file="scout_utils.py")
        return None