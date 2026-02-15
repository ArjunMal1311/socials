import re
import os
import time

from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse

from rich.status import Status
from rich.console import Console

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from typing import Optional, List, Dict, Tuple, Any, Callable

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir

from services.platform.instagram.support.video_utils import download_instagram_videos

console = Console()

def parse_instagram_comments_robust(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(True):
        if tag.name == 'span' and re.search(r'\d+\s*likes', tag.get_text(strip=True)):
            pass 
        elif 'class' in tag.attrs:
            del tag['class']
        
        if 'style' in tag.attrs:
            del tag['style']
    
    for svg_tag in soup.find_all('svg'):
        svg_tag.decompose()
    
    for img_tag in soup.find_all('img'):
        img_tag.decompose()

    return str(soup)

def extract_structured_comments(cleaned_html_content: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(cleaned_html_content, 'html.parser')
    comments = []

    main_comment_entry_divs = soup.find_all(
        lambda tag: tag.name == 'div' and tag.find('time') and tag.find('span', string=re.compile(r'\d+[.,]?\d*\s*likes'))
    )

    for main_comment_entry_div in main_comment_entry_divs:
        username = None
        username_link = main_comment_entry_div.find('a', href=re.compile(r'^/'), role='link')
        if username_link and username_link.find('span'): 
            username = username_link.get_text(strip=True)

        timestamp = None
        time_tag = main_comment_entry_div.find('time')
        if time_tag:
            timestamp = time_tag.get('datetime')

        comment_text = None
        username_span_container = username_link.find_parent('span').find_parent('div') if username_link else None
        if username_span_container:
            comment_text_sibling_div = username_span_container.find_next_sibling('div')
            if comment_text_sibling_div:
                comment_text_span = comment_text_sibling_div.find('span', dir='auto')
                if comment_text_span and not comment_text_span.find('a'): 
                    comment_text = comment_text_span.get_text(strip=True)
        
        likes = 0
        likes_span = main_comment_entry_div.find('span', string=re.compile(r'\d+[.,]?\d*\s*likes'))
        if likes_span:
            likes_text = likes_span.get_text(strip=True).replace(',', '')
            match = re.search(r'\d+', likes_text)
            if match:
                likes = int(match.group())


        if username and comment_text:
            comments.append({
                'username': username,
                'timestamp': timestamp,
                'comment_text': comment_text,
                'likes': likes
            })

    seen = set()
    unique_comments = []
    for c in comments:
        comment_id = (c['username'], c['timestamp'], c['comment_text'])
        if comment_id not in seen:
            seen.add(comment_id)
            unique_comments.append(c)

    return unique_comments

def scout_instagram_reels_comments(driver: webdriver.Chrome, max_comments: int = 50, status: Status = None, html_dump_path: Optional[str] = None, verbose: bool = False, reel_index: int = 0) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    try:
        try:
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            log("Pressed ESC to close any existing comments section", verbose, log_caller_file="scout_utils.py")
            time.sleep(1)
        except Exception:
            pass

        try:
            video_element = driver.find_element(By.XPATH, "//video | //div[contains(@class, 'video')] | //div[@role='button' and contains(@aria-label, 'Video')]")
            if video_element:
                video_element.click()
                log("Clicked video area to close existing comments section", verbose, log_caller_file="scout_utils.py")
                time.sleep(1)
        except Exception:
            pass

        comment_button_xpath = "//div[@role='button' and @aria-haspopup='menu']"

        all_comment_buttons = driver.find_elements(By.XPATH, comment_button_xpath)
        log(f"Found {len(all_comment_buttons)} comment buttons on page, using button at index {reel_index}", verbose, log_caller_file="scout_utils.py")

        if len(all_comment_buttons) > reel_index:
            comment_button = all_comment_buttons[reel_index]
        elif all_comment_buttons:
            comment_button = all_comment_buttons[-1]
            log(f"Reel index {reel_index} out of range, using last button", verbose, log_caller_file="scout_utils.py")
        else:
            log("No comment buttons found", verbose, is_error=True, log_caller_file="scout_utils.py")
            return [], None

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_button)
        WebDriverWait(driver, 5).until(EC.visibility_of(comment_button))
        comment_button.click()
        if status:
            status.update("[white]Comments button clicked. Waiting for comments to load...[/white]")
        time.sleep(5)

        comments_data = []
        scroll_count = 0
        max_scrolls = 1

        log("Attempting to find comments section...", verbose, log_caller_file="scout_utils.py")
        comments_section_xpath = "//span[contains(text(),'Comments')]/parent::*/parent::*/following-sibling::div"
        try:
            comments_panel = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, comments_section_xpath))
            )
            log("Comments section found.", verbose, log_caller_file="scout_utils.py")
        except Exception:
            log("Comments section not found within timeout. This might mean no comments are loaded or the XPath is incorrect.", verbose, log_caller_file="scout_utils.py")
            return [], None

        log("Scrolling to load more comments...", verbose, log_caller_file="scout_utils.py")
        while len(comments_data) < max_comments and scroll_count < max_scrolls:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", comments_panel)
            time.sleep(2)
            scroll_count += 1
        log(f"Finished scrolling {scroll_count} times.", verbose, log_caller_file="scout_utils.py")

        video_url = driver.current_url
        html_content = comments_panel.get_attribute("outerHTML")

        if html_dump_path:
            os.makedirs(os.path.dirname(html_dump_path), exist_ok=True)
            with open(html_dump_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            log(f"Full comments HTML saved to: {html_dump_path}", verbose, log_caller_file="scout_utils.py")

        cleaned_html = parse_instagram_comments_robust(html_content)
        structured_comments = extract_structured_comments(cleaned_html)

        return structured_comments, video_url

    except Exception as e:
        log(f"An error occurred during Instagram Reels comment scraping: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
        return [], None

def extract_current_reel_url(driver) -> Optional[str]:
    try:
        current_url = driver.current_url
        
        def is_valid_reel_path(path_parts):
            if len(path_parts) >= 2:
                if path_parts[0] in ['reels', 'p']:
                    if path_parts[1] not in ['audio', 'videos', 'series']:
                        return True
            return False

        parsed = urlparse(current_url)
        path = parsed.path.strip('/')
        path_parts = path.split('/')

        if is_valid_reel_path(path_parts):
            return current_url
        try:
            reel_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/reels/') or contains(@href, '/p/')]")
            valid_links = []
            for link in reel_links:
                href = link.get_attribute('href')
                if not href: continue
                
                check_path = urlparse(href).path.strip('/')
                check_parts = check_path.split('/')
                
                if is_valid_reel_path(check_parts):
                    valid_links.append(href)
            
            if valid_links:
                for link in reversed(valid_links):
                    return link
        except Exception:
            pass

    except Exception as e:
        log(f"Error extracting reel URL: {e}", False, log_caller_file="scout_utils.py")
    return None

def _format_reel_data(reel_url: str, local_path: str, cdn_link: Optional[str], comments_data: List[Dict[str, Any]], profile_name: str) -> Dict[str, Any]:
    scraped_at_str = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    reel_id = ""
    if '/reels/' in reel_url:
        reel_id = reel_url.split('/reels/')[1].split('/')[0]

    return {
        "source": "instagram",
        "scraped_at": scraped_at_str,
        "engagement": {
            "comments": len(comments_data)
        },
        "data": {
            "reel_id": reel_id,
            "reel_url": reel_url,
            "local_path": local_path,
            "cdn_link": cdn_link,
            "filename": os.path.basename(local_path) if local_path else "",
            "media_urls": [cdn_link] if cdn_link else [],
            "profile_name": profile_name,
            "comments_data": comments_data
        }
    }

def move_to_next_reel(driver, verbose: bool = False) -> bool:
    try:
        current_url = driver.current_url
        log(f"Current reel URL before navigation: {current_url}", verbose, log_caller_file="scout_utils.py")

        next_element = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Navigate to next Reel' and @role='button']"))
        )
        next_element.click()

        log("Moved to next reel.", verbose, log_caller_file="scout_utils.py")
        time.sleep(3)

        new_url = driver.current_url
        if new_url != current_url:
            log(f"Successfully navigated to new reel: {new_url}", verbose, log_caller_file="scout_utils.py")

            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@role='button' and @aria-haspopup='menu']"))
                )
                log("New reel fully loaded (comment button present)", verbose, log_caller_file="scout_utils.py")
                time.sleep(2)
            except Exception as e:
                log(f"Warning: Could not confirm new reel loaded: {e}", verbose, log_caller_file="scout_utils.py")

            return True
        else:
            log("URL didn't change, checking if reel content changed...", verbose, log_caller_file="scout_utils.py")

            try:
                current_reel_element = driver.find_element(By.XPATH, "//div[@role='button' and @aria-haspopup='menu']")
                if current_reel_element:
                    log("Found reel element, navigation likely worked despite same URL", verbose, log_caller_file="scout_utils.py")
                    return True
            except Exception:
                log("Could not find reel element, navigation may have failed", verbose, log_caller_file="scout_utils.py")

        return False

    except Exception as e:
        log(f"Error moving to next Instagram Reel: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
    return False

def scout_instagram_reels(profile_name: str, count: int, max_comments: int, verbose: bool = False, headless: bool = True, status: Optional[Status] = None, process_item_callback: Optional[Callable] = None) -> Tuple[Optional[Any], List[Dict[str, Any]]]:
    browser_data_dir = get_browser_data_dir(profile_name, "instagram")
    
    try:
        if status:
            status.update(f"[white]Initializing WebDriver for profile '{profile_name}'...[/white]")
        
        driver, _ = setup_driver(browser_data_dir, profile=profile_name, headless=headless)
        
        if not driver:
            log("WebDriver could not be initialized for Instagram.", verbose, is_error=True, log_caller_file="scout_utils.py")
            return None, []

        if status:
            status.update("[white]Navigating to Instagram Reels...[/white]")
        
        driver.get("https://www.instagram.com/reels/")
        time.sleep(5)

        scouted_reels = []
        reel_attempt = 0

        while len(scouted_reels) < count and reel_attempt < count * 2:
            reel_attempt += 1
            log(f"--- Processing Instagram Reel Attempt {reel_attempt} ({len(scouted_reels) + 1}/{count}) ---", verbose, log_caller_file="scout_utils.py")

            reel_url = extract_current_reel_url(driver)
            if not reel_url:
                log(f"Could not extract reel URL for reel {reel_attempt}, skipping", verbose, log_caller_file="scout_utils.py")
                if not move_to_next_reel(driver, verbose=verbose):
                    log("Could not move to next reel. Ending scouting process.", verbose, log_caller_file="scout_utils.py")
                    break
                continue

            log(f"Found reel URL: {reel_url}", verbose, log_caller_file="scout_utils.py")

            if status:
                status.update(f"[white]Scouting comments from Instagram reel {len(scouted_reels) + 1}...[/white]")
            
            comments_data, _ = scout_instagram_reels_comments(
                driver=driver,
                max_comments=max_comments,
                status=status,
                html_dump_path=None,
                verbose=verbose,
                reel_index=len(scouted_reels)
            )

            reel_data = {
                'reel_id': reel_url.split('/reels/')[1].split('/')[0] if '/reels/' in reel_url else f'reel_{len(scouted_reels)}',
                'reel_url': reel_url,
                'comments_data': comments_data,
                'comments': len(comments_data),
                'scraped_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                'profile_name': profile_name
            }

            if process_item_callback:
                try:
                    reel_data = process_item_callback(reel_data, driver)
                except Exception as e:
                    log(f"Error in item processing callback: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")

            scouted_reels.append(reel_data)
            log(f"Successfully processed reel {len(scouted_reels)}", verbose, log_caller_file="scout_utils.py")

            if len(scouted_reels) < count:
                if not move_to_next_reel(driver, verbose=verbose):
                    log("Could not move to next reel. Ending scouting process.", verbose, log_caller_file="scout_utils.py")
                    break

        log(f"Completed Instagram scouting: {len(scouted_reels)} reels processed", verbose, log_caller_file="scout_utils.py")
        return driver, scouted_reels

    except Exception as e:
        log(f"Error during unified Instagram scouting: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
        return None, []

def scout_profile_posts(profile_name: str, target_profile: str, count: int, verbose: bool = False, headless: bool = True, status: Optional[Status] = None) -> Tuple[Optional[Any], List[Dict[str, Any]]]:
    browser_data_dir = get_browser_data_dir(profile_name, "instagram")
    
    try:
        if status:
            status.update(f"[white]Initializing WebDriver for profile '{profile_name}'...[/white]")
        
        driver, _ = setup_driver(browser_data_dir, profile=profile_name, headless=headless)
        
        if not driver:
            log("WebDriver could not be initialized for Instagram.", verbose, is_error=True, log_caller_file="scout_utils.py")
            return None, []

        if status:
            status.update(f"[white]Navigating to Instagram profile '{target_profile}'...[/white]")
        
        driver.get(f"https://www.instagram.com/{target_profile}/")
        time.sleep(5)

        scouted_posts = []
        collected_urls = set()
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        posts_xpath = "//a[contains(@href, '/reel/') or contains(@href, '/p/')]"
        
        scroll_attempts = 0
        max_scroll_attempts = count // 3 + 5 

        while len(scouted_posts) < count and scroll_attempts < max_scroll_attempts:
            if status:
                status.update(f"[white]Scanning feed... Found {len(scouted_posts)}/{count} posts[/white]")

            links = driver.find_elements(By.XPATH, posts_xpath)
            
            new_batch_found = False
            for link in links:
                if len(scouted_posts) >= count:
                    break
                
                try:
                    href = link.get_attribute('href')
                    if not href or href in collected_urls:
                        continue
                    
                    collected_urls.add(href)
                    
                    caption = ""
                    try:
                        img_tag = link.find_element(By.TAG_NAME, "img")
                        if img_tag:
                            caption = img_tag.get_attribute("alt") or ""
                    except Exception:
                        pass
                    
                    post_data = {
                        'post_url': href,
                        'id': href.split('/')[-2] if href.strip('/').count('/') >= 1 else '',
                        'scraped_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                        'profile_name': target_profile,
                        'caption': caption
                    }
                    
                    scouted_posts.append(post_data)
                    new_batch_found = True
                    log(f"Found post: {href}", verbose, log_caller_file="scout_utils.py")
                    
                except Exception as e:
                    log(f"Error extracting element data: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")

            if len(scouted_posts) >= count:
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height and not new_batch_found:
                scroll_attempts += 1
            elif new_batch_found:
                scroll_attempts = 0
                
            last_height = new_height
            
        return driver, scouted_posts

    except Exception as e:
        log(f"Error during profile scouting: {e}", verbose, is_error=True, log_caller_file="scout_utils.py")
        return None, []

def process_reel_for_standalone(reel_data: dict, driver, profile: str, output_format: str, restrict_filenames: bool, verbose: bool) -> dict:
    reel_url = reel_data['reel_url']
    comments_data = reel_data['comments_data']
    
    with Status(f"[white]Downloading reel ({reel_url})...[/white]", spinner="dots", console=console) as status:
        downloaded_path, cdn_link = download_instagram_videos(
            video_urls=reel_url,
            profile_name=profile,
            output_format=output_format,
            restrict_filenames=restrict_filenames,
            status=status,
            verbose=verbose,
            extract_cdn_links=True,
            use_reels_dir=True
        )
    status.stop()

    if downloaded_path:
        log(f"Successfully downloaded: {os.path.basename(downloaded_path)}", verbose, log_caller_file="scout_utils.py")
        return _format_reel_data(reel_url, downloaded_path, cdn_link, comments_data, profile)
    else:
        log(f"Failed to download reel ({reel_url})", verbose, log_caller_file="scout_utils.py")
        return reel_data