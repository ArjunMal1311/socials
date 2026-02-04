import os
import sys
import json

from datetime import datetime
from typing import List, Dict, Any

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))))

from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir

from services.platform.reddit.support.scraper_utils import run_reddit_scraper

console = Console()

def run_reddit_suggestions_workflow(profile_name: str, max_posts: int = 15, verbose: bool = False, headless: bool = True) -> Dict[str, Any]:
    if profile_name not in PROFILES:
        return {"error": f"Profile '{profile_name}' not found"}

    log(f"Starting Reddit suggestions scraping workflow for profile: {profile_name}", verbose, log_caller_file="scraping_utils.py")

    with Status(f"[white]Scraping Reddit posts for suggestions...[/white]", spinner="dots", console=console) as status:
        scraped_posts = run_reddit_scraper(profile_name, status=status, verbose=verbose)

    if not scraped_posts:
        return {"error": "No Reddit posts were scraped"}

    if len(scraped_posts) > max_posts:
        scraped_posts = scraped_posts[:max_posts]

    log(f"Total Reddit posts scraped: {len(scraped_posts)}", verbose, log_caller_file="scraping_utils.py")

    saved_file = save_reddit_scraped_content(scraped_posts, profile_name, verbose)

    result = {
        "success": True,
        "total_posts_scraped": len(scraped_posts),
        "saved_file": saved_file
    }

    return result

def save_reddit_scraped_content(scraped_posts: List[Dict[str, Any]], profile_name: str, verbose: bool = False) -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    content_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "scraped_reddit_posts": scraped_posts,
        "metadata": {
            "total_posts": len(scraped_posts),
            "scrape_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "platform": "reddit"
        }
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filename = f"scraped_content_reddit_{timestamp}.json"
    filepath = os.path.join(suggestions_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)

        log(f"Saved {len(scraped_posts)} scraped Reddit posts to {filepath}", verbose, log_caller_file="scraping_utils.py")
        return filepath

    except Exception as e:
        log(f"Error saving scraped Reddit content: {e}", verbose, is_error=True, log_caller_file="scraping_utils.py")
        return ""

def get_latest_scraped_reddit_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    reddit_files = [f for f in os.listdir(suggestions_dir) if f.startswith('scraped_content_reddit_') and f.endswith('.json')]
    if not reddit_files:
        return ""

    reddit_files.sort(reverse=True)
    return os.path.join(suggestions_dir, reddit_files[0])

def get_latest_filtered_reddit_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    filtered_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_reddit_') and f.endswith('.json')]
    if not filtered_files:
        return ""

    filtered_files.sort(reverse=True)
    return os.path.join(suggestions_dir, filtered_files[0])

def get_latest_approved_reddit_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    approved_files = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_reddit_') and f.endswith('.json') and not f.endswith('_with_media.json')]
    if not approved_files:
        return ""

    approved_files.sort(reverse=True)
    return os.path.join(suggestions_dir, approved_files[0])
