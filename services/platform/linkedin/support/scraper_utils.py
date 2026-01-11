import re
import time

from datetime import datetime
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir

def parse_engagement_number(num_str: str) -> int:
    if not num_str:
        return 0

    num_str = num_str.strip().upper()
    if 'K' in num_str:
        return int(float(num_str.replace('K', '')) * 1000)
    elif 'M' in num_str:
        return int(float(num_str.replace('M', '')) * 1000000)
    else:
        try:
            return int(float(num_str))
        except:
            return 0

def scrape_linkedin_profiles(linkedin_target_profiles: List[str], profile_name: str, max_posts_per_profile: int = 10, headless: bool = True, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    all_posts = []

    user_data_dir = get_browser_data_dir(profile_name)
    driver = None

    try:
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless, verbose=verbose)
        for msg in setup_messages:
            log(msg, verbose, status=status, log_caller_file="scraper_utils.py")
        log("Navigating to LinkedIn home...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get("https://www.linkedin.com")
        time.sleep(3)

        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            log("Redirected to login page. Waiting 30 seconds for manual login...", verbose, status=status, log_caller_file="scraper_utils.py")
            time.sleep(30)
            log("Resuming automated process after manual login window.", verbose, status=status, log_caller_file="scraper_utils.py")
        except:
            log("Already logged in or not redirected to login page.", verbose, status=status, log_caller_file="scraper_utils.py")

        for profile_url in linkedin_target_profiles:
            try:
                log(f"Scraping profile: {profile_url}", verbose, status=status, log_caller_file="scraper_utils.py")

                if not profile_url.startswith('http'):
                    profile_url = f"https://www.linkedin.com/in/{profile_url}"

                activity_url = f"{profile_url}/recent-activity/all/"
                driver.get(activity_url)
                time.sleep(5)

                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                )

                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)

                posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2")

                log(f"Found {len(posts)} potential posts on {profile_url}", verbose, status=status, log_caller_file="scraper_utils.py")

                posts_scraped = 0
                for post in posts[:max_posts_per_profile]:
                    try:
                        post_data = extract_linkedin_post_data(post, profile_url, verbose, status)
                        if post_data:
                            all_posts.append(post_data)
                            posts_scraped += 1
                    except Exception as e:
                        log(f"Error extracting post data: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                        continue

                log(f"Successfully scraped {posts_scraped} posts from {profile_url}", verbose, status=status, log_caller_file="scraper_utils.py")

                time.sleep(2)

            except Exception as e:
                log(f"Error scraping profile {profile_url}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                continue

        log(f"Total posts scraped: {len(all_posts)}", verbose, status=status, log_caller_file="scraper_utils.py")

    except Exception as e:
        log(f"Error during LinkedIn scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, status=status, log_caller_file="scraper_utils.py")

    return all_posts

def scrape_linkedin_feed_posts(profile_name: str, max_posts: int = 10, headless: bool = True, status=None, verbose: bool = False, existing_driver=None) -> List[Dict[str, Any]]:
    all_posts = []

    if existing_driver:
        driver = existing_driver
        manage_driver = False
        log("Using existing driver for scraping", verbose, status=status, log_caller_file="scraper_utils.py")
    else:
        user_data_dir = get_browser_data_dir(profile_name)
        driver = None
        manage_driver = True

        try:
            driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless, verbose=verbose)
            for msg in setup_messages:
                log(msg, verbose, status=status, log_caller_file="scraper_utils.py")
        except Exception as e:
            log(f"Error setting up driver for scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
            return []

    try:
        log("Navigating to LinkedIn feed...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(5)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )

        log("Scrolling to load feed posts...", verbose, status=status, log_caller_file="scraper_utils.py")
        for scroll in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        posts = driver.find_elements(By.CSS_SELECTOR, "div.feed-shared-update-v2:not(.feed-shared-update-v2--aggregated), div.feed-shared-control-menu__trigger")
        posts = [post for post in posts if not post.find_elements(By.CSS_SELECTOR, ".feed-shared-aggregated-content, .update-components-feed-discovery-entity")]
        log(f"Found {len(posts)} potential feed posts", verbose, status=status, log_caller_file="scraper_utils.py")

        posts_scraped = 0
        for i, post in enumerate(posts[:max_posts]):
            try:
                if verbose and i % 5 == 0:
                    log(f"Processing post {i+1}/{min(len(posts), max_posts)}", verbose, status=status, log_caller_file="scraper_utils.py")

                post_data = extract_linkedin_post_data(post, profile_url="", extract_engagement=False, verbose=verbose, status=status)
                if post_data and post_data.get("data", {}).get("text"):
                    all_posts.append(post_data)
                    posts_scraped += 1
                    if posts_scraped >= max_posts:
                        break
            except Exception as e:
                log(f"Error extracting feed post data: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                continue

        log(f"Successfully scraped {posts_scraped} feed posts", verbose, status=status, log_caller_file="scraper_utils.py")

    except Exception as e:
        log(f"Error during LinkedIn feed scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
    finally:
        if driver and manage_driver:
            driver.quit()
            log("WebDriver closed.", verbose, status=status, log_caller_file="scraper_utils.py")

    return all_posts

def extract_linkedin_post_data(post_element, profile_url: str = "", extract_engagement: bool = True, verbose: bool = False, status=None) -> Dict[str, Any]:
    try:
        post_data = {
            "source": "linkedin_feed" if not extract_engagement else "linkedin",
            "scraped_at": datetime.now().isoformat() + "Z",
            "data": {
                "post_id": "",
                "text": "",
                "author_name": "",
                "profile_url": "",
                "post_date": ""
            }
        }

        if extract_engagement:
            post_data["engagement"] = {
                "likes": 0,
                "comments": 0,
                "reposts": 0
            }
            post_data["data"]["profile_url"] = profile_url
            post_data["data"]["media_urls"] = []

        try:
            full_text = post_element.text
            if full_text and len(full_text.strip()) > 10:
                text_content = full_text.strip()
                text_lower = text_content.lower()
                skip_patterns = [
                    "recommended for you",
                    "people skilled in",
                    "also follow these",
                    "show more",
                    "company • management consulting"
                ]
                if any(pattern in text_lower for pattern in skip_patterns) and len(text_content.split('\n')) < 5:
                    return None
                post_data["data"]["text"] = text_content
        except:
            text_elements = post_element.find_elements(By.CSS_SELECTOR, "[data-test-id='feed-shared-text'], .feed-shared-text, .feed-shared-update-v2__description, .feed-shared-text__text")
            if text_elements:
                text_content = text_elements[0].text.strip()
                text_lower = text_content.lower()
                skip_patterns = [
                    "recommended for you",
                    "people skilled in",
                    "also follow these",
                    "show more",
                    "company • management consulting"
                ]
                if any(pattern in text_lower for pattern in skip_patterns) and len(text_content.split('\n')) < 5:
                    return None
                post_data["data"]["text"] = text_content

        try:
            author_elements = post_element.find_elements(By.CSS_SELECTOR, "[data-test-id='feed-shared-actor__name'], .feed-shared-actor__name, .update-components-actor__name")
            if author_elements:
                post_data["data"]["author_name"] = author_elements[0].text.strip()
        except:
            pass

        try:
            profile_links = post_element.find_elements(By.CSS_SELECTOR, "a[href*='linkedin.com/in/'], a[href*='linkedin.com/company/']")
            for link in profile_links:
                href = link.get_attribute("href")
                if href and ("linkedin.com/in/" in href or "linkedin.com/company/" in href):
                    post_data["data"]["profile_url"] = href.split('?')[0].split('#')[0]  # Clean URL
                    break
        except:
            pass

        if extract_engagement:
            try:
                engagement_text = post_element.text
                if verbose:
                    log(f"Post engagement text: '{engagement_text[:200]}...'", verbose, status=status, log_caller_file="scraper_utils.py")

                buttons = post_element.find_elements(By.CSS_SELECTOR, "button[aria-label*='reaction'], button[aria-label*='react'], button[data-reaction-details]")
                for button in buttons:
                    aria_label = button.get_attribute("aria-label") or ""
                    if verbose:
                        log(f"Button aria-label: '{aria_label}'", verbose, status=status, log_caller_file="scraper_utils.py")

                    reactions_match = re.search(r'(\d+(?:\.\d+)?[KkMm]?)\s*reactions?', aria_label, re.IGNORECASE)
                    if reactions_match:
                        post_data["engagement"]["likes"] = parse_engagement_number(reactions_match.group(1))
                        if verbose:
                            log(f"Found reactions: {post_data['engagement']['likes']}", verbose, status=status, log_caller_file="scraper_utils.py")
                        break

                likes_match = re.search(r'(\d+(?:\.\d+)?[KkMm]?)\s*(?:like|likes)', engagement_text, re.IGNORECASE)
                if likes_match and not post_data["engagement"]["likes"]:
                    post_data["engagement"]["likes"] = parse_engagement_number(likes_match.group(1))

                comments_match = re.search(r'(\d+(?:\.\d+)?[KkMm]?)\s*(?:comment|comments)', engagement_text, re.IGNORECASE)
                if comments_match:
                    post_data["engagement"]["comments"] = parse_engagement_number(comments_match.group(1))

                reposts_match = re.search(r'(\d+(?:\.\d+)?[KkMm]?)\s*(?:repost|reposts|share|shares)', engagement_text, re.IGNORECASE)
                if reposts_match:
                    post_data["engagement"]["reposts"] = parse_engagement_number(reposts_match.group(1))

                if verbose and not post_data["engagement"]["likes"]:
                    log(f"No likes found in text or aria-label: '{engagement_text}'", verbose, status=status, log_caller_file="scraper_utils.py")

            except Exception as e:
                log(f"Error extracting engagement: {e}", verbose, status=status, log_caller_file="scraper_utils.py")

            media_elements = post_element.find_elements(By.CSS_SELECTOR, "img, video")
            for media in media_elements:
                media_url = media.get_attribute("src")
                if (media_url and
                    not media_url.startswith("data:") and
                    not "static.licdn.com" in media_url and
                    not media_url.endswith(('.svg', '.ico'))):
                    post_data["data"]["media_urls"].append(media_url)

        if post_data["data"]["text"]:
            if extract_engagement:
                post_data["data"]["post_id"] = f"linkedin_{int(time.time())}_{hash(str(post_data['data']['text'])[:50]) % 10000}"
            else:
                post_data["data"]["post_id"] = f"feed_{int(time.time())}_{hash(post_data['data']['text'][:50]) % 10000}"

            post_data["data"]["post_date"] = datetime.now().isoformat() + "Z"

            if not post_data["data"]["profile_url"]:
                post_data["data"]["profile_url"] = ""

        return post_data

    except Exception as e:
        log(f"Error extracting LinkedIn post data: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return None