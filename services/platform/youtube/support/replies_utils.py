import re
import os
import time
import json
import httplib2
import subprocess
import google.generativeai as genai

from datetime import datetime
from rich.status import Status
from selenium import webdriver
from rich.console import Console
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from googleapiclient.discovery import build
from selenium.webdriver.common.by import By
from typing import Optional, List, Dict, Any
from googleapiclient.errors import HttpError
from selenium.webdriver.support.ui import WebDriverWait
from oauth2client.client import flow_from_clientsecrets
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if status and (is_error or verbose):
        status.stop()

    log_message = message
    if is_error:
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[replies_utils.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[replies_utils.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

CLIENT_SECRETS_FILE = "client_secret.json"
CREDENTIALS_FILE = "youtube-oauth2.json"
COMMENT_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def get_authenticated_youtube_service(profile_name="Default", verbose: bool = False):
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'schedule-videos', profile_name))
    
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        _log(f"Created profile directory for YouTube API: {profile_dir}", verbose)

    client_secrets_path = os.path.join(profile_dir, CLIENT_SECRETS_FILE)
    credentials_path = os.path.join(profile_dir, CREDENTIALS_FILE)

    if not os.path.exists(client_secrets_path):
        _log(f"Error: '{CLIENT_SECRETS_FILE}' not found in {profile_dir}", verbose, is_error=True)
        _log("Please download your OAuth 2.0 client secrets file from the Google API Console and place it in the specified profile directory.", verbose, is_error=True)
        return None

    flow = flow_from_clientsecrets(client_secrets_path, scope=COMMENT_SCOPE)
    storage = Storage(credentials_path)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        _log("OAuth2 credentials not found or invalid. Please run the authentication flow manually.", verbose)
        _log(f"Run: python services/support/refresh_youtube_auth.py {profile_name}", verbose)
        credentials = run_flow(flow, storage)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def _init_gemini_pro_model(api_key=None):
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No Gemini API key found. Set GEMINI_API_KEY environment variable or pass via argument.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")

def scrape_youtube_shorts_comments(
    profile_name: str,
    driver: webdriver.Chrome,
    max_comments: int = 50,
    status: Status = None,
    verbose: bool = False
):
    try:
        comment_button_xpath = '//div[@id="comments-button"]//button'
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, comment_button_xpath))
            ).click()
            if status:
                status.update("[white]Comments button clicked. Waiting for comments to load...[/white]")
            time.sleep(3)
            video_url = driver.current_url
        except TimeoutException:
            _log("Comments button not found or not clickable within timeout. Continuing without comments.", verbose)
            return [], None, None
        except NoSuchElementException:
            _log("Comments button element not found. Continuing without comments.", verbose)
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
            _log("Comments section (div id=\"contents\") not found within timeout. This might mean no comments are loaded or the XPath is incorrect.", verbose)
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
        _log(f"An error occurred during YouTube Shorts comment scraping: {e}", verbose, is_error=True)
        return [], None, None
    finally:
        pass

import subprocess

def move_to_next_short(driver, verbose: bool = False) -> bool:
    try:
        next_button_xpath = '//button[contains(@aria-label, "Next video") and .//div[contains(@class, "yt-spec-touch-feedback-shape--touch-response")]]'
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, next_button_xpath))
        ).click()
        time.sleep(3)
        return True
    except (TimeoutException, NoSuchElementException):
        _log("Next short button not found or not clickable. May be at the end of shorts.", verbose)
        return False
    except Exception as e:
        _log(f"Error moving to next short: {e}", verbose, is_error=True)
        return False

def download_youtube_short(video_url: str, profile_name: str, status: Status = None, verbose: bool = False) -> Optional[str]:
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'youtube', profile_name, 'shorts'))
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
        _log(f"Downloading video '{video_url}' to {output_dir}...", verbose)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if status:
            status.update(f"[green]Video download complete: {video_url}[/green]")
        else:
            _log(f"Video download complete: {video_url}", verbose)
        
        for f_name in os.listdir(output_dir):
            if f_name.startswith(video_id):
                return os.path.join(output_dir, f_name)
        return None

    except subprocess.CalledProcessError as e:
        _log(f"Error downloading video {video_url}: {e.stderr}", verbose, is_error=True)
        return None
    except Exception as e:
        _log(f"An unexpected error occurred during video download: {e}", verbose, is_error=True)
        return None

def generate_youtube_replies(profile_name: str, comments_data: list, video_context: str, video_path: str, api_key: str = None, verbose: bool = False):
    model = _init_gemini_pro_model(api_key)
    top_n_comments = comments_data[:10]

    comments_json = json.dumps(top_n_comments, indent=2)

    prompt = f"""
    Given the YouTube Short video content and context: '{video_context}',
    and the following highly engaging comments (sorted by likes):
    {comments_json}

    Generate a single, highly engaging, and concise reply that resonates with the overall sentiment of these comments and the video content. The reply should be creative and encourage further interaction. Return only the reply text.
    """

    uploaded_file = None
    try:
        if video_path:
            base_filename = os.path.basename(video_path)
            sanitized_display_name = re.sub(r'\s*\(.*?\)|\s*\[.*?\]', '', base_filename).strip()
            _log(f"[Gemini] Uploading media: {video_path}", verbose)
            uploaded_file = genai.upload_file(path=video_path, display_name=sanitized_display_name)
            
            timeout_seconds = 600
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                file_status = genai.get_file(uploaded_file.name)
                if file_status.state.name == "ACTIVE":
                    _log(f"[Gemini] File {uploaded_file.display_name} ({file_status.name}) is now ACTIVE.", verbose)
                    break
                elif file_status.state == "FAILED":
                    _log(f"Gemini file upload failed for {uploaded_file.display_name} ({file_status.name}).", verbose, is_error=True)
                    return None
                _log(f"[Gemini] Waiting for file {uploaded_file.display_name} ({file_status.state.name}) to become ACTIVE (current state: {file_status.state})... This can take several minutes for large videos.", verbose)
                time.sleep(5)
            else:
                _log(f"Gemini file {uploaded_file.display_name} ({uploaded_file.name}) did not become ACTIVE within {timeout_seconds} seconds. Aborting content generation.", verbose, is_error=True)
                return None

        content = [prompt]
        if uploaded_file:
            content.append(uploaded_file)

        _log(f"[Gemini] Generating content for {uploaded_file.display_name if uploaded_file else 'text-only'}", verbose)
        response = model.generate_content(content)
        
        generated_reply = response.text
        return generated_reply
    except Exception as e:
        _log(f"Error generating reply: {e}", verbose, is_error=True)
        return f"Error generating reply: {e}"
    finally:
        if uploaded_file:
            genai.delete_file(uploaded_file.name)
            _log(f"[Gemini] Deleted uploaded file: {uploaded_file.display_name}", verbose)

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
        _log(f"Error posting reply: {e}", verbose, is_error=True)
        return False
    except Exception as e:
        _log(f"An unexpected error occurred while posting reply: {e}", verbose, is_error=True)
        return False

def post_youtube_reply_api(profile_name: str, video_url: str, reply_text: str, status: Status = None, verbose: bool = False):
    try:
        if status:
            status.update(f"[white]Authenticating with YouTube API...[/white]")
        
        youtube = get_authenticated_youtube_service(profile_name, verbose)
        if not youtube:
            _log("Failed to authenticate with YouTube API", verbose, is_error=True)
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
        
        _log(f"✅ Comment posted successfully! Comment ID: {response['id']}", verbose)
        return True
        
    except HttpError as e:
        error_details = e.error_details[0] if e.error_details else {}
        reason = error_details.get('reason', 'Unknown error')
        _log(f"YouTube API Error: {reason}", verbose, is_error=True)
        if reason == 'quotaExceeded':
            _log("YouTube API quota exceeded. Try again later.", verbose, is_error=True)
        elif reason == 'forbidden':
            _log("Access forbidden. Check your OAuth2 scopes and permissions.", verbose, is_error=True)
        return False
    except Exception as e:
        _log(f"An unexpected error occurred while posting comment via API: {e}", verbose, is_error=True)
        return False

def save_youtube_reply_for_review(profile_name: str, video_url: str, generated_reply: str, scraped_comments: List[Dict], video_path: str, verbose: bool = False):
    review_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'youtube', profile_name, 'replies_for_review'))
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
    _log(f"Reply for '{video_url}' saved for review to {file_path}", verbose)

def load_approved_youtube_replies(profile_name: str, verbose: bool = False) -> List[Dict]:
    review_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'youtube', profile_name, 'replies_for_review'))
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
    review_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'youtube', profile_name, 'replies_for_review'))
    file_path = os.path.join(review_dir, f"{reply_id}.json")
    if os.path.exists(file_path):
        with open(file_path, 'r+', encoding='utf-8') as f:
            reply_data = json.load(f)
            reply_data['status'] = 'posted'
            f.seek(0)
            json.dump(reply_data, f, ensure_ascii=False, indent=4)
            f.truncate()
        _log(f"Reply '{reply_id}' marked as posted.", verbose)
    else:
        _log(f"Reply file not found for ID: {reply_id}", verbose, is_error=True)
