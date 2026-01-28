import os
import sys
import json

from datetime import datetime
from typing import List, Dict, Any

from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir

from services.platform.linkedin.support.scraper_utils import scrape_linkedin_profiles, scrape_linkedin_feed_posts

console = Console()

def save_linkedin_scraped_content(scraped_posts: List[Dict[str, Any]], profile_name: str, verbose: bool = False) -> str:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    content_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "scraped_posts": scraped_posts,
        "metadata": {
            "total_posts": len(scraped_posts),
            "scrape_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filename = f"scraped_content_linkedin_{timestamp}.json"
    filepath = os.path.join(suggestions_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)

        log(f"Saved {len(scraped_posts)} scraped posts to {filepath}", verbose, log_caller_file="scraping_utils.py")
        return filepath

    except Exception as e:
        log(f"Error saving scraped content: {e}", verbose, is_error=True, log_caller_file="scraping_utils.py")
        return ""

def run_linkedin_suggestions_workflow(profile_name: str, max_posts_per_profile: int = 10, verbose: bool = False, headless: bool = True) -> Dict[str, Any]:
    if profile_name not in PROFILES:
        return {"error": f"Profile '{profile_name}' not found"}

    log(f"Starting LinkedIn content scraping for profile: {profile_name}", verbose, log_caller_file="scraping_utils.py")

    profile_config = PROFILES[profile_name]
    linkedin_target_profiles = profile_config.get('target_profiles', [])

    # Just scrape home page for now when no target profiles are configured
    # This scrapes the LinkedIn feed/home page instead of specific target profiles
    if not linkedin_target_profiles:
        log(f"No linkedin_target_profiles found for {profile_name}. Scraping LinkedIn home page feed instead.", verbose, log_caller_file="scraping_utils.py")
        scraped_posts = scrape_linkedin_feed_posts(
            profile_name=profile_name,
            max_posts=max_posts_per_profile,
            headless=headless,
            verbose=verbose
        )
    else:
        scraped_posts = scrape_linkedin_profiles(
            linkedin_target_profiles=linkedin_target_profiles,
            profile_name=profile_name,
            max_posts_per_profile=max_posts_per_profile,
            headless=headless,
            verbose=verbose
        )

    if not scraped_posts:
        return {"error": "No posts were scraped from LinkedIn"}

    log(f"Total posts scraped: {len(scraped_posts)}", verbose, log_caller_file="scraping_utils.py")

    saved_file = save_linkedin_scraped_content(scraped_posts, profile_name, verbose)

    result = {
        "success": True,
        "total_posts_scraped": len(scraped_posts),
        "saved_file": saved_file
    }

    return result

def get_latest_approved_linkedin_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    approved_files_with_media = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_') and f.endswith('_with_media.json')]
    if approved_files_with_media:
        approved_files_with_media.sort(reverse=True)
        return os.path.join(suggestions_dir, approved_files_with_media[0])

    approved_files = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_') and f.endswith('.json')]
    if not approved_files:
        return ""

    approved_files.sort(reverse=True)
    return os.path.join(suggestions_dir, approved_files[0])

def get_latest_linkedin_suggestions_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    suggestions_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_') and f.endswith('.json')]
    if not suggestions_files:
        return ""

    suggestions_files.sort(reverse=True)
    return os.path.join(suggestions_dir, suggestions_files[0])

def get_latest_filtered_linkedin_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    filtered_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_linkedin_') and f.endswith('.json')]
    if not filtered_files:
        return ""

    filtered_files.sort(reverse=True)
    return os.path.join(suggestions_dir, filtered_files[0])
