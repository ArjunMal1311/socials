import os
import json

from profiles import PROFILES

from typing import Optional
from datetime import datetime
from rich.console import Console

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_reddit_analysis_dir, ensure_dir_exists

from services.platform.reddit.support.file_manager import get_latest_dated_json_file

console = Console()

def analyze_reddit_content_with_gemini(profile_name: str, api_key: Optional[str] = None, status=None, verbose: bool = False) -> Optional[str]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)
    
    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        log("No Gemini API key available.", verbose, is_error=True, log_caller_file="content_analyzer.py")
        return None

    profile_config = PROFILES.get(profile_name, {})
    profile_props = profile_config.get('properties', {})
    platform_props = profile_props.get('platform', {})
    reddit_config = platform_props.get("reddit", {})
    prompts = profile_config.get("prompts", {})
    reddit_user_prompt = prompts.get("reddit_user_prompt", "Analyze these Reddit trends and suggest 5-10 content ideas for my [Your Channel Niche] channel focusing on engaging topics and unanswered questions from the discussions.")
    latest_scraped_data_path = get_latest_dated_json_file(profile_name, "reddit_scraped_data", verbose=verbose)

    if not latest_scraped_data_path:
        log(f"No latest scraped Reddit data found for profile '{profile_name}'. Please run Reddit scraper first.", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None

    try:
        with open(latest_scraped_data_path, 'r', encoding='utf-8') as f:
            scraped_reddit_data = json.load(f)
    except Exception as e:
        log(f"Error loading scraped Reddit data from {latest_scraped_data_path}: {e}", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None

    if not scraped_reddit_data:
        log("No Reddit data found in the latest scraped file. Cannot generate content suggestions.", verbose, status=status, log_caller_file="content_analyzer.py")
        return None

    reddit_data_for_prompt = []
    for post in scraped_reddit_data:
        post_info = f"Title: {post.get('title', 'N/A')}\nSubreddit: {post.get('subreddit', 'N/A')}\nScore: {post.get('score', 0)}\nComments: {post.get('num_comments', 0)}\nContent: {post.get('content', 'N/A')}"
        if post.get("comments"):
            comments_str = "\n".join([f"  - {c.get('body', '')[:100]}..." for c in post["comments"][:3]])
            post_info += f"\nTop Comments:\n{comments_str}"
        reddit_data_for_prompt.append(post_info)
    
    full_prompt = f"{reddit_user_prompt}\n\nScraped Reddit Data:\n\n{'--'*50}\n{'''\n'''.join(reddit_data_for_prompt)}\n{'--'*50}"

    if status:
        status.update(f"[white]Analyzing Reddit content for suggestions (using API key ending in {gemini_api_key[-4:]})...[/white]")

    suggestions = generate_gemini(
        media_path=None, 
        api_key_pool=api_pool, 
        api_call_tracker=api_call_tracker, 
        rate_limiter=rate_limiter, 
        prompt_text=full_prompt, 
        model_name='gemini-2.5-flash', 
        status=status, 
        verbose=verbose
    )

    if suggestions:
        log("Successfully generated content suggestions from Reddit data.", verbose, status=status, log_caller_file="content_analyzer.py")
        analysis_output_dir = get_reddit_analysis_dir(profile_name)
        ensure_dir_exists(analysis_output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(analysis_output_dir, f"reddit_content_suggestions_{timestamp}.txt")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(suggestions)
            log(f"Reddit content suggestions saved to {output_file}", verbose, status=status, log_caller_file="content_analyzer.py")
        except Exception as e:
            log(f"Error saving Reddit content suggestions to {output_file}: {e}", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return suggestions
    else:
        log("Failed to generate content suggestions from Reddit data.", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None
