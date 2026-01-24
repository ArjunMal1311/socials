import os
import time

from datetime import datetime
from typing import List, Dict, Any

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir

def scrape_linkedin_profiles(linkedin_target_profiles: List[str], profile_name: str, max_posts_per_profile: int = 10, headless: bool = True, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    all_posts = []

    for profile_url in linkedin_target_profiles:
        if not profile_url.startswith('http'):
            profile_url = f"https://www.linkedin.com/in/{profile_url}"

        log(f"Processing profile: {profile_url}", verbose, status=status, log_caller_file="scraper_utils.py")

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

        log(f"Generated {min(max_posts_per_profile, 5)} dummy posts from {profile_url}", verbose, status=status, log_caller_file="scraper_utils.py")

    log(f"Total dummy posts generated: {len(all_posts)}", verbose, status=status, log_caller_file="scraper_utils.py")

    return all_posts

def scrape_linkedin_feed_posts(profile_name: str, max_posts: int = 10, headless: bool = True, status=None, verbose: bool = False, existing_driver=None) -> List[Dict[str, Any]]:
    all_posts = []
    driver = existing_driver

    if driver is None:
        user_data_dir = get_browser_data_dir(profile_name)
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, verbose=verbose, status=status, headless=headless)
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="scraper_utils.py")

    try:
        log("Navigating to LinkedIn feed...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

        log("Performing initial scrolls to load content...", verbose, status=status, log_caller_file="scraper_utils.py")
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        log("Scraping LinkedIn feed posts...", verbose, status=status, log_caller_file="scraper_utils.py")

        debug_dir = "tmp/debug"
        os.makedirs(debug_dir, exist_ok=True)

        posts_scraped = 0
        scroll_attempts = 0
        max_scrolls = 5
        processed_post_ids = set()

        while posts_scraped < max_posts and scroll_attempts < max_scrolls:
            try:
                posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")
                log(f"Found {len(posts)} posts on page", verbose, status=status, log_caller_file="scraper_utils.py")

                new_posts_found = False
                for post in posts:
                    if posts_scraped >= max_posts:
                        break

                    try:
                        post_id = f"post_{hash(post.text[:100])}"

                        if post_id in processed_post_ids:
                            continue

                        processed_post_ids.add(post_id)

                        html_content = post.get_attribute("outerHTML")
                        html_file = os.path.join(debug_dir, f"post_{posts_scraped + 1}_{int(time.time())}.html")

                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)

                        all_posts.append({"html_file": html_file, "post_id": post_id})
                        posts_scraped += 1
                        new_posts_found = True
                        log(f"Saved HTML for post {posts_scraped}/{max_posts}: {html_file}", verbose, status=status, log_caller_file="scraper_utils.py")
                    except Exception as e:
                        log(f"Error saving post HTML: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
                        continue

                if posts_scraped >= max_posts:
                    break

                if not new_posts_found and scroll_attempts >= 2:
                    log("No new posts found in last scroll, stopping", verbose, status=status, log_caller_file="scraper_utils.py")
                    break

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                scroll_attempts += 1

            except Exception as e:
                log(f"Error during scrolling: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
                break

        log(f"Scraped {len(all_posts)} LinkedIn feed posts", verbose, status=status, log_caller_file="scraper_utils.py")

        log("Processing saved HTML files...", verbose, status=status, log_caller_file="scraper_utils.py")
        processed_posts = []
        for post_info in all_posts:
            try:
                html_file = post_info["html_file"]
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()

                post_data = extract_post_data_from_html(html_content)
                if post_data:
                    processed_posts.append(post_data)
                    log(f"Processed post from {os.path.basename(html_file)}", verbose, status=status, log_caller_file="scraper_utils.py")

            except Exception as e:
                log(f"Error processing HTML file {post_info.get('html_file', 'unknown')}: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
                continue

        log(f"Successfully processed {len(processed_posts)} posts from HTML", verbose, status=status, log_caller_file="scraper_utils.py")

        try:
            import shutil
            if os.path.exists(debug_dir):
                shutil.rmtree(debug_dir)
                log(f"Cleaned up debug directory: {debug_dir}", verbose, status=status, log_caller_file="scraper_utils.py")
        except Exception as cleanup_error:
            log(f"Warning: Could not clean up debug directory: {cleanup_error}", verbose, is_error=True, log_caller_file="scraper_utils.py")

    except Exception as e:
        log(f"Error in feed scraping: {e}", verbose, is_error=True, log_caller_file="scraper_utils.py")
    finally:
        if existing_driver is None and driver:
            driver.quit()

    return processed_posts


def extract_post_data_from_html(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        post_id = f"linkedin_feed_{int(time.time() * 1000000)}"

        author_name = ""
        profile_url = ""
        post_text = ""
        post_date = datetime.now().isoformat() + "Z"
        media_urls = []

        likes_count = 0
        comments_count = 0
        reposts_count = 0

        try:
            author_link = soup.select_one("a[href*='/in/']")
            if author_link:
                profile_url = author_link.get('href', '')
                author_name_elem = author_link.select_one("span[dir='ltr'] span[aria-hidden='true']") or \
                                 author_link.select_one("span.update-components-actor__title span[dir='ltr']")
                if author_name_elem:
                    author_name = author_name_elem.get_text(strip=True)
        except Exception:
            pass

        try:
            text_selectors = [
                "div.feed-shared-update-v2__description",
                "p._57a17605.e8f8b838.dfcecb14",
                ".feed-shared-update-v2__commentary",
                ".update-components-text"
            ]

            for selector in text_selectors:
                text_element = soup.select_one(selector)
                if text_element:
                    text = text_element.get_text(strip=True)
                    if text:
                        post_text = text
                        break
        except Exception:
            pass

        try:
            date_element = soup.select_one("time")
            if date_element:
                post_date = date_element.get('datetime') or datetime.now().isoformat() + "Z"
        except Exception:
            pass

        try:
            img_elements = soup.select("img[data-delayed-url], img[src*='media.licdn.com']")[:3]
            for img in img_elements:
                media_url = img.get('data-delayed-url') or img.get('src', '')
                if media_url and "http" in media_url and "media.licdn.com" in media_url:
                    media_urls.append(media_url)

            video_elements = soup.select("video")[:1]
            for video in video_elements:
                media_url = video.get('src') or video.get('poster', '')
                if media_url and "http" in media_url:
                    media_urls.append(media_url)

        except Exception:
            pass

        try:
            reactions_elem = soup.select_one(".social-details-social-counts__reactions-count")
            if reactions_elem:
                likes_count = int(reactions_elem.get_text(strip=True) or 0)

            comments_count = 0
            comments_selectors = [
                "button[aria-label*='comments on']",
                "button[aria-label*='comment on']",
                ".social-details-social-counts__comments button"
            ]
            
            for selector in comments_selectors:
                comments_elem = soup.select_one(selector)
                if comments_elem:
                    aria_label = comments_elem.get('aria-label', '')
                    import re
                    match = re.search(r'(\d+)\s+comments?', aria_label, re.IGNORECASE)
                    if match:
                        comments_count = int(match.group(1))
                        break

            reposts_count = 0
            reposts_selectors = [
                "button[aria-label*='reposts of']",
                "button[aria-label*='repost of']",
                ".social-details-social-counts__reposts button"
            ]
            
            for selector in reposts_selectors:
                reposts_elem = soup.select_one(selector)
                if reposts_elem:
                    aria_label = reposts_elem.get('aria-label', '')
                    match = re.search(r'(\d+)\s+reposts?', aria_label, re.IGNORECASE)
                    if match:
                        reposts_count = int(match.group(1))
                        break

        except Exception:
            pass

        if not post_text:
            return None

        try:
            post_urn = soup.select_one("div.feed-shared-update-v2")["data-urn"]
        except:
            post_urn = None

        return {
            "source": "linkedin_feed",
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
        return None