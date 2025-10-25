import re
import os
import json
import time
import requests
import google.generativeai as genai

from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from rich.status import Status
from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from typing import Optional, List, Dict, Tuple, Any
from selenium.webdriver.support.ui import WebDriverWait
from services.support.path_config import get_instagram_reels_dir
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None, api_info: Optional[Dict[str, Any]] = None):
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_error:
        level = "ERROR"
        style = "bold red"
    else:
        level = "INFO"
        style = "white"
    
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    if api_info:
        api_message = api_info.get('message', '')
        if api_message:
            formatted_message += f" | API: {api_message}"
    
    if is_error or verbose:
        console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def _init_gemini_model(api_key=None):
    if not api_key:
        api_key = os.getenv("GEMINI_API")
    if not api_key:
        raise ValueError("No Gemini API key found. Set GEMINI_API environment variable or pass via argument.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")

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

    return comments

def scrape_instagram_reels_comments(driver: webdriver.Chrome, max_comments: int = 50, status: Status = None, html_dump_path: Optional[str] = None, verbose: bool = False) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    try:
        comment_button_xpath = "//div[@role='button' and @aria-haspopup='menu']"
        
        retries = 3
        for i in range(retries):
            try:
                comment_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, comment_button_xpath))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_button)
                WebDriverWait(driver, 5).until(EC.visibility_of(comment_button))
                comment_button.click()
                if status:
                    status.update("[white]Comments button clicked. Waiting for comments to load...[/white]")
                time.sleep(3)
                break
            except TimeoutException:
                _log(f"Attempt {i+1}/{retries}: Comments button not found or not clickable within timeout. Retrying...", verbose)
                time.sleep(2)
            except NoSuchElementException:
                _log(f"Attempt {i+1}/{retries}: Comments button element not found. Retrying...", verbose)
                time.sleep(2)
            except Exception as e:
                _log(f"Attempt {i+1}/{retries}: An unexpected error occurred while clicking comments button: {e}. Retrying...", verbose)
                time.sleep(2)
        else:
            _log("Failed to click comments button after multiple retries. Continuing without comments.", verbose)
            return [], None

        comments_data = []
        scroll_count = 0
        max_scrolls = 5

        _log("Attempting to find comments section...", verbose)
        comments_section_xpath = "//span[contains(text(),'Comments')]/parent::*/parent::*/following-sibling::div"
        try:
            comments_panel = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, comments_section_xpath))
            )
            _log("Comments section found.", verbose)
        except TimeoutException:
            _log("Comments section not found within timeout. This might mean no comments are loaded or the XPath is incorrect.", verbose)
            return [], None

        _log("Scrolling to load more comments...", verbose)
        while len(comments_data) < max_comments and scroll_count < max_scrolls:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", comments_panel)
            time.sleep(2)
            scroll_count += 1
        _log(f"Finished scrolling {scroll_count} times.", verbose)

        video_url = driver.current_url

        html_content = comments_panel.get_attribute("outerHTML")

        if html_dump_path:
            os.makedirs(os.path.dirname(html_dump_path), exist_ok=True)
            with open(html_dump_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            _log(f"Full comments HTML saved to: {html_dump_path}", verbose)

        cleaned_html = parse_instagram_comments_robust(html_content)
        structured_comments = extract_structured_comments(cleaned_html)

        return structured_comments, video_url

    except Exception as e:
        _log(f"An error occurred during Instagram Reels comment scraping: {e}", verbose, is_error=True)
        return [], None

def generate_instagram_replies(comments_data: list, video_path: str = None, api_key: str = None, verbose: bool = False):
    try:
        model = _init_gemini_model(api_key)

        top_comments = comments_data[:10]
        comments_json = json.dumps(top_comments, indent=2)

        prompt_parts = [
            "Analyze the following Instagram Reel comments and the video content.",
            "Generate a single, highly engaging, and relevant reply that could be posted by the channel owner.",
            "Make the reply concise, witty, and positive. Avoid generic phrases.",
            f"Top comments (JSON):\n{comments_json}"
        ]

        if video_path and os.path.exists(video_path):
            prompt_parts.append(f"Video content is available at: {video_path}")
            prompt_parts.append("The video is a short, engaging clip. Focus replies on humor and positivity.")

        response = model.generate_content(prompt_parts)
        return response.text

    except Exception as e:
        _log(f"Error generating Instagram reply with Gemini: {e}", verbose, is_error=True)
        return f"Error generating reply: {e}"

def post_instagram_reply(driver, reply_text: str, status: Status, verbose: bool = False):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if status:
                status.stop()

            _log(f"Generated Reply: {reply_text}", verbose)
            edited_reply = console.input("[bold yellow]Edit reply (press Enter to accept): [/bold yellow]")
            if not edited_reply:
                edited_reply = reply_text
            reply_text = edited_reply

            confirmation = console.input("[bold yellow]Are you sure you want to post this reply? (yes/no): [/bold yellow]")
            if confirmation.lower() != 'yes':
                _log("Reply not posted. User aborted.", verbose)
                if status:
                    status.start()
                return False

            if status:
                status.start() 

            initial_input_xpath = "//input[@placeholder='Add a comment…']"
            _log(f"Attempt {attempt + 1}/{max_retries}: Attempting to find initial comment input field with XPath: {initial_input_xpath}", verbose)
            initial_input_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, initial_input_xpath))
            )
            _log("Initial comment input field found and is clickable.", verbose)

            _log("Attempting to click initial comment input field.", verbose)
            ActionChains(driver).move_to_element(initial_input_element).click().perform()
            _log("Initial comment input field clicked. Waiting for contenteditable div...", verbose)
            time.sleep(1)

            comment_input_xpath = "//div[@aria-placeholder='Add a comment…' and @contenteditable='true']"
            _log(f"Attempt {attempt + 1}/{max_retries}: Attempting to find contenteditable div with XPath: {comment_input_xpath}", verbose)
            comment_input_div = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, comment_input_xpath))
            )
            _log("Contenteditable comment input div found and is clickable.", verbose)
            time.sleep(1)
        
            driver.execute_script("arguments[0].innerText = '';", comment_input_div)
            _log("Cleared existing content in contenteditable div.", verbose)
            time.sleep(0.5)

            _log(f"Attempting to send reply text character by character: '{reply_text}'", verbose)
            for char in reply_text:
                comment_input_div.send_keys(char)
                time.sleep(0.05) 
            _log("Reply text sent character by character.", verbose)
            time.sleep(1)

            post_button_xpath = "//div[contains(text(),'Post')]"
            _log(f"Attempting to find post button with XPath: {post_button_xpath}", verbose)
            post_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, post_button_xpath))
            )
            _log("Post button found and is clickable.", verbose)

            _log("Attempting to click post button using JavaScript.", verbose)
            driver.execute_script("arguments[0].click();", post_button)
            _log("Post button clicked via JavaScript.", verbose)

            if status:
                status.update(f"[green]Reply posted successfully![/green]")

            time.sleep(2)
            return True

        except (TimeoutException, NoSuchElementException) as e:
            _log(f"Attempt {attempt + 1}/{max_retries}: Selenium Error posting reply: {e}. Retrying...", verbose)
            time.sleep(3)
        except Exception as e:
            _log(f"Attempt {attempt + 1}/{max_retries}: An unexpected error occurred while posting reply: {e}. Retrying...", verbose, is_error=True)
            time.sleep(3)

    _log("Failed to post reply after multiple attempts.", verbose, is_error=True)
    return False

def move_to_next_reel(driver, verbose: bool = False) -> bool:
    try:
        comment_button_xpath = "//div[@role='button' and @aria-haspopup='menu']"
        
        retries = 3
        for i in range(retries):
            try:
                comment_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, comment_button_xpath))
                )
                if comment_button: 
                    comment_button.click()
                    _log("Comments section closed.", verbose)
                    time.sleep(2)
                    break
            except TimeoutException:
                _log(f"Attempt {i+1}/{retries}: Comments button not found or not clickable within timeout when trying to close. Retrying...", verbose)
                time.sleep(2)
            except NoSuchElementException:
                _log(f"Attempt {i+1}/{retries}: Comments button element not found when trying to close. Retrying...", verbose)
                time.sleep(2) 
        else:
            _log("Failed to close comments after multiple retries. Continuing without closing comments.", verbose)

        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ARROW_DOWN)
        _log("Moved to next reel using down arrow key.", verbose)
        time.sleep(6)
        return True
    except Exception as e:
        _log(f"Error moving to next Instagram Reel: {e}", verbose, is_error=True)
        return False

def download_instagram_reel(reel_url: str, profile_name: str, status: Status = None, verbose: bool = False) -> Optional[str]:
    output_dir = get_instagram_reels_dir(profile_name)
    os.makedirs(output_dir, exist_ok=True)

    if status:
        status.update(f"[white]Extracting video URL from {reel_url}...[/white]")

    try:
        direct_video_url = reel_url

        response = requests.get(direct_video_url, stream=True)
        response.raise_for_status()

        reel_id = reel_url.split('/')[-2] if reel_url.endswith('/') else reel_url.split('/')[-1]
        output_path = os.path.join(output_dir, f'{reel_id}.mp4')

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if status:
            status.update(f"[green]Reel downloaded: {output_path}[/green]")
        else:
            _log(f"Reel downloaded: {output_path}", verbose)
        return output_path

    except requests.exceptions.RequestException as e:
        _log(f"Error downloading Instagram Reel {reel_url}: {e}", verbose, is_error=True)
        return None
    except Exception as e:
        _log(f"An unexpected error occurred during reel download: {e}", verbose, is_error=True)
        return False
