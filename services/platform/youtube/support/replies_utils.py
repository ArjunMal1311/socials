import os
import time
import json
import httplib2
import subprocess

from rich.status import Status
from selenium import webdriver
from rich.console import Console
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from typing import Optional, List, Dict
from googleapiclient.discovery import build
from selenium.webdriver.common.by import By
from googleapiclient.errors import HttpError
from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from selenium.webdriver.support.ui import WebDriverWait
from oauth2client.client import flow_from_clientsecrets
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from services.support.path_config import get_youtube_schedule_videos_dir, get_youtube_shorts_dir, get_youtube_replies_for_review_dir

console = Console()

CLIENT_SECRETS_FILE = "client_secret.json"
CREDENTIALS_FILE = "youtube-oauth2.json"
COMMENT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def get_authenticated_youtube_service(profile_name="Default", verbose: bool = False):
    profile_dir = get_youtube_schedule_videos_dir(profile_name)
    
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        log(f"Created profile directory for YouTube API: {profile_dir}", verbose, log_caller_file="replies_utils.py")

    client_secrets_path = os.path.join(profile_dir, CLIENT_SECRETS_FILE)
    credentials_path = os.path.join(profile_dir, CREDENTIALS_FILE)

    if not os.path.exists(client_secrets_path):
        log(f"Error: '{CLIENT_SECRETS_FILE}' not found in {profile_dir}", verbose, is_error=True, log_caller_file="replies_utils.py")
        log("Please download your OAuth 2.0 client secrets file from the Google API Console and place it in the specified profile directory.", verbose, is_error=True, log_caller_file="replies_utils.py")
        return None

    flow = flow_from_clientsecrets(client_secrets_path, scope=COMMENT_SCOPE)
    storage = Storage(credentials_path)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        log("OAuth2 credentials not found or invalid. Please run the authentication flow manually.", verbose, log_caller_file="replies_utils.py")
        log(f"Run: python services/support/refresh_youtube_auth.py {profile_name}", verbose, log_caller_file="replies_utils.py")
        credentials = run_flow(flow, storage)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def scrape_youtube_shorts_comments(profile_name: str, driver: webdriver.Chrome, max_comments: int = 50, status: Status = None, verbose: bool = False):
    try:
        comment_button_xpath = '//button[contains(@aria-label, "comments")]'
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, comment_button_xpath))
            ).click()
            if status:
                status.update("[white]Comments button clicked. Waiting for comments to load...[/white]")
            time.sleep(3)
            video_url = driver.current_url
        except TimeoutException:
            log("Comments button not found or not clickable within timeout. Continuing without comments.", verbose, log_caller_file="replies_utils.py")
            return [], None, None
        except NoSuchElementException:
            log("Comments button element not found. Continuing without comments.", verbose, log_caller_file="replies_utils.py")
            return [], None, None

        comments_data = []
        scroll_count = 0
        max_scrolls = 5

        comments_section_xpath = '//div[@id="contents" and contains(@class, "ytd-item-section-renderer")]'
        try:
            comments_panel = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, comments_section_xpath))
            )
        except TimeoutException:
            log("Comments section (div id=\"contents\") not found within timeout. This might mean no comments are loaded or the XPath is incorrect.", verbose, log_caller_file="replies_utils.py")
            return [], None, None

        while len(comments_data) < max_comments and scroll_count < max_scrolls:
            comment_elements = comments_panel.find_elements(By.XPATH, './/ytd-comment-thread-renderer')
            for comment_element in comment_elements:
                try:
                    author_element = comment_element.find_element(By.CSS_SELECTOR, '#author-text span')
                    author = author_element.text.strip()

                    content_element = comment_element.find_element(By.CSS_SELECTOR, '#content-text span')
                    comment_text = content_element.text.strip()

                    likes = 0
                    try:
                        like_count_element = comment_element.find_element(By.CSS_SELECTOR, '#vote-count-middle')
                        likes_text = like_count_element.text.strip().replace(",", "") 
                        likes = int(likes_text) if likes_text.isdigit() else 0
                    except NoSuchElementException:
                        likes = 0
                    except ValueError:
                        likes = 0

                    comment_info = {"author": author, "comment": comment_text, "likes": likes}
                    if author and comment_text and comment_info not in comments_data:
                        comments_data.append(comment_info)
                        if status:
                            status.update(f"[white]Scraped {len(comments_data)} comments... (Last: {author} - {likes} likes)[/white]")

                except NoSuchElementException:
                    continue
            
            if len(comments_data) >= max_comments:
                break

            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", comments_panel)
            time.sleep(2)
            scroll_count += 1
        
        comments_data.sort(key=lambda x: x['likes'], reverse=True)

        if status:
            status.update(f"[green]Finished scraping. Scraped {len(comments_data)} comments.[/green]")
        return comments_data, driver, video_url

    except Exception as e:
        log(f"An error occurred during YouTube Shorts comment scraping: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return [], None, None
    finally:
        pass

import subprocess

def move_to_next_short(driver, verbose: bool = False) -> bool:
    try:
        next_button_xpath = '//button[@aria-label="Next video"]'
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, next_button_xpath))
        ).click()
        time.sleep(3)
        return True
    except (TimeoutException, NoSuchElementException):
        log("Next short button not found or not clickable. May be at the end of shorts.", verbose, log_caller_file="replies_utils.py")
        return False
    except Exception as e:
        log(f"Error moving to next short: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False

def download_youtube_short(video_url: str, profile_name: str, status: Status = None, verbose: bool = False) -> Optional[str]:
    output_dir = get_youtube_shorts_dir(profile_name)
    os.makedirs(output_dir, exist_ok=True)
    
    video_id = video_url.split('v=')[1].split('&')[0] if 'v=' in video_url else video_url.split('/')[-1]
    output_template = os.path.join(output_dir, f'{video_id}.%(ext)s')

    cmd = [
        "yt-dlp",
        "--extractor-args", "youtube:player_client=all",
        "-f", "bv*+ba/best",
        "--merge-output-format", "mp4",
        "--output", output_template,
        video_url
    ]

    if status:
        status.update(f"[white]Downloading video '{video_url}' to {output_dir}...[/white]")
    else:
        log(f"Downloading video '{video_url}' to {output_dir}...", verbose, log_caller_file="replies_utils.py")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if status:
            status.update(f"[green]Video download complete: {video_url}[/green]")
        else:
            log(f"Video download complete: {video_url}", verbose, log_caller_file="replies_utils.py")
        
        for f_name in os.listdir(output_dir):
            if f_name.startswith(video_id):
                return os.path.join(output_dir, f_name)
        return None

    except subprocess.CalledProcessError as e:
        log(f"Error downloading video {video_url}: {e.stderr}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return None
    except Exception as e:
        log(f"An unexpected error occurred during video download: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return None

def generate_youtube_replies(profile_name: str, comments_data: list, video_context: str, video_path: str, api_key_pool: APIKeyPool, api_call_tracker: APICallTracker, rate_limiter: RateLimiter, verbose: bool = False):
    top_n_comments = comments_data[:10]

    comments_json = json.dumps(top_n_comments, indent=2)

    prompt = f"""
    Given the YouTube Short video content and context: '{video_context}',
    and the following highly engaging comments (sorted by likes):
    {comments_json}

    Generate a single, highly engaging, and concise reply that resonates with the overall sentiment of these comments and the video content. The reply should be creative and encourage further interaction. Return only the reply text.
    """

    generated_reply = generate_gemini(
        media_path=video_path,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        prompt_text=prompt,
        model_name='gemini-2.5-flash',
        verbose=verbose
    )
    return generated_reply

def post_youtube_reply(driver, comment_id: str, reply_text: str, status: Status, verbose: bool = False):
    try:
        if status:
            status.update(f"[white]Attempting to post reply...[/white]")
        
        comment_input_xpath = '//div[@id="creation-box"]//yt-formatted-string[@contenteditable="true"]'
        
        comment_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, comment_input_xpath))
        )
        
        driver.execute_script("arguments[0].focus();", comment_input)
        time.sleep(1)
        
        comment_input.clear()
        comment_input.send_keys(reply_text)
        
        time.sleep(1)
        
        submit_button_xpath = '//div[@id="creation-box"]//ytd-button-renderer[@button-renderer]//yt-button-shape[contains(@class, "yt-spec-touch-feedback-shape--touch-response-inverse")]'
        
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
        ).click()
        
        if status:
            status.update(f"[green]Reply posted successfully![/green]")
        
        time.sleep(2)
        return True
        
    except (TimeoutException, NoSuchElementException) as e:
        log(f"Error posting reply: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False
    except Exception as e:
        log(f"An unexpected error occurred while posting reply: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False

def post_youtube_reply_api(profile_name: str, video_url: str, reply_text: str, status: Status = None, verbose: bool = False):
    try:
        if status:
            status.update(f"[white]Authenticating with YouTube API...[/white]")
        
        youtube = get_authenticated_youtube_service(profile_name, verbose)
        if not youtube:
            log("Failed to authenticate with YouTube API", verbose, is_error=True, log_caller_file="replies_utils.py")
            return False
        
        if status:
            status.update(f"[white]Extracting video ID from URL...[/white]")
        
        video_id = video_url.split('v=')[1].split('&')[0] if 'v=' in video_url else video_url.split('/')[-1]
        
        if status:
            status.update(f"[white]Posting comment via YouTube API...[/white]")
        
        comment_request = youtube.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": reply_text
                        }
                    }
                }
            }
        )
        
        response = comment_request.execute()
        
        if status:
            status.update(f"[green]Comment posted successfully via API![/green]")
        
        log(f"✅ Comment posted successfully! Comment ID: {response['id']}", verbose, log_caller_file="replies_utils.py")
        return True
        
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        reason = error_details.get('reason', 'Unknown error')
        log(f"YouTube API Error: {reason}", verbose, is_error=True, log_caller_file="replies_utils.py")
        if reason == 'quotaExceeded':
            log("YouTube API quota exceeded. Try again later.", verbose, is_error=True, log_caller_file="replies_utils.py")
        elif reason == 'forbidden':
            log("Access forbidden. Check your OAuth2 scopes and permissions.", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False
    except Exception as e:
        log(f"An unexpected error occurred while posting comment via API: {e}", verbose, is_error=True, log_caller_file="replies_utils.py")
        return False

def save_youtube_reply_for_review(profile_name: str, video_url: str, generated_reply: str, scraped_comments: List[Dict], video_path: str, verbose: bool = False):
    review_dir = get_youtube_replies_for_review_dir(profile_name)
    os.makedirs(review_dir, exist_ok=True)

    reply_id = f"yt_reply_{int(time.time())}"

    reply_data = {
        "id": reply_id,
        "video_url": video_url,
        "generated_reply": generated_reply,
        "scraped_comments": scraped_comments,
        "video_path": video_path,
        "status": "pending"
    }

    file_path = os.path.join(review_dir, f"{reply_id}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(reply_data, f, ensure_ascii=False, indent=4)
    log(f"Reply for '{video_url}' saved for review to {file_path}", verbose, log_caller_file="replies_utils.py")

def load_approved_youtube_replies(profile_name: str, verbose: bool = False) -> List[Dict]:
    review_dir = get_youtube_replies_for_review_dir(profile_name)
    approved_replies = []
    if not os.path.exists(review_dir):
        return approved_replies

    for filename in os.listdir(review_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(review_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                reply_data = json.load(f)
                if reply_data.get('status') == 'approved':
                    approved_replies.append(reply_data)
    return approved_replies

def mark_youtube_reply_as_posted(profile_name: str, reply_id: str, verbose: bool = False):
    review_dir = get_youtube_replies_for_review_dir(profile_name)
    file_path = os.path.join(review_dir, f"{reply_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r+', encoding='utf-8') as f:
            reply_data = json.load(f)
            reply_data['status'] = 'posted'
            f.seek(0)
            json.dump(reply_data, f, ensure_ascii=False, indent=4)
            f.truncate()
        log(f"Reply '{reply_id}' marked as posted.", verbose, log_caller_file="replies_utils.py")
    else:
        log(f"Reply file not found for ID: {reply_id}", verbose, is_error=True, log_caller_file="replies_utils.py")
