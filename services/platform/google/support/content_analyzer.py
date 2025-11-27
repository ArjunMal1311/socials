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
from services.support.path_config import get_google_analysis_dir, ensure_dir_exists
from services.platform.google.support.file_manager import get_latest_dated_json_file

console = Console()

def analyze_google_content_with_gemini(profile_name: str, api_key: Optional[str] = None, status=None, verbose: bool = False) -> Optional[str]:
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
    google_search_config = profile_config.get("google_search", {})
    google_user_prompt = google_search_config.get("google_user_prompt", "Analyze these Google Search results and suggest 5-10 content ideas for my [Your Channel Niche] channel focusing on relevant topics.")

    latest_scraped_data_path = get_latest_dated_json_file(profile_name, "google_scraped_data", verbose=verbose)

    if not latest_scraped_data_path:
        log(f"No latest scraped Google Search data found for profile '{profile_name}'. Please run Google Search scraper first.", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None

    try:
        with open(latest_scraped_data_path, 'r', encoding='utf-8') as f:
            scraped_google_data = json.load(f)
    except Exception as e:
        log(f"Error loading scraped Google Search data from {latest_scraped_data_path}: {e}", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None

    if not scraped_google_data:
        log("No Google Search data found in the latest scraped file. Cannot generate content suggestions.", verbose, status=status, log_caller_file="content_analyzer.py")
        return None

    google_data_for_prompt = []
    for result in scraped_google_data:
        result_info = f"Title: {result.get('title', 'N/A')}\nLink: {result.get('link', 'N/A')}\nSnippet: {result.get('snippet', 'N/A')}"
        google_data_for_prompt.append(result_info)
    
    full_prompt = f"{google_user_prompt}\n\nScraped Google Search Data:\n\n{'-'*50}\n{'''\n'''.join(google_data_for_prompt)}\n{'-'*50}"

    if status:
        status.update(f"[white]Analyzing Google Search content for suggestions (using API key ending in {gemini_api_key[-4:]})...[/white]")

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
        log("Successfully generated content suggestions from Google Search data.", verbose, status=status, log_caller_file="content_analyzer.py")
        analysis_output_dir = get_google_analysis_dir(profile_name)
        ensure_dir_exists(analysis_output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(analysis_output_dir, f"google_content_suggestions_{timestamp}.txt")
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(suggestions)
            log(f"Google content suggestions saved to {output_file}", verbose, status=status, log_caller_file="content_analyzer.py")
        except Exception as e:
            log(f"Error saving Google content suggestions to {output_file}: {e}", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return suggestions
    else:
        log("Failed to generate content suggestions from Google Search data.", verbose, is_error=True, status=status, log_caller_file="content_analyzer.py")
        return None
