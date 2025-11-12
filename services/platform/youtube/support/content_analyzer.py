import os
import re

from profiles import PROFILES

from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any, Optional, Tuple
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.gemini_util import generate_gemini

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
        console.print(f"[content_analyzer.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[content_analyzer.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def analyze_video_content_with_gemini(video_path: str, profile_name: str, status=None, api_key: Optional[str] = None, verbose: bool = False) -> Tuple[Optional[str], Optional[str]]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)
    
    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        _log("No Gemini API key available.", verbose, is_error=True)
        return None, None

    try:
        rate_limiter.wait_if_needed(gemini_api_key)
        
        if not os.path.exists(video_path):
            _log(f"Video file not found: {video_path}", verbose, is_error=True)
            return None, None

        profile_config = PROFILES.get(profile_name, {})
        summary_prompt_text = profile_config.get("youtube_summary_prompt", "Summarize this video content concisely.")
        transcript_prompt_text = profile_config.get("youtube_transcript_prompt", "Provide a full transcription of the spoken content in this video.")

        if status:
            status.update(f"[white]Analyzing video content for summary (using API key ending in {gemini_api_key[-4:]})...[/white]")
        summary = generate_gemini(video_path, api_pool, api_call_tracker, rate_limiter, summary_prompt_text, model_name='gemini-2.5-flash', status=status, verbose=verbose)

        if status:
            status.update(f"[white]Analyzing video content for transcript (using API key ending in {gemini_api_key[-4:]})...[/white]")
        transcript = generate_gemini(video_path, api_pool, api_call_tracker, rate_limiter, transcript_prompt_text, model_name='gemini-2.5-flash', status=status, verbose=verbose)

        if summary and transcript:
            _log(f"Successfully analyzed video content for {os.path.basename(video_path)}.", verbose)
            return summary, transcript
        else:
            _log(f"Failed to get both summary and transcript for {os.path.basename(video_path)}.", verbose, is_error=True)
            return summary, transcript

    except Exception as e:
        _log(f"Error analyzing video content with Gemini: {e}", verbose, is_error=True)
        return None, None 

def suggest_best_content_with_gemini(videos_data: List[Dict[str, Any]], profile_name: str, api_key: Optional[str] = None, status=None, verbose: bool = False) -> Optional[str]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)
    
    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        _log("No Gemini API key available for content suggestion.", verbose, is_error=True)
        return None

    try:
        rate_limiter.wait_if_needed(gemini_api_key)

        profile_config = PROFILES.get(profile_name, {})
        youtube_scraper_config = profile_config.get("youtube_scraper", {})
        content_suggestion_prompt = youtube_scraper_config.get("youtube_user_prompt", "Based on the following video data (titles, summaries, views, etc.), suggest 5 to 10 best content ideas for a YouTube channel similar to the scraped content. Focus on trending topics, gaps, or unique angles that could attract viewers. Provide just the content ideas, one per line.")

        video_info_for_prompt = []
        for video in videos_data:
            title = video.get('title', 'N/A')
            views = video.get('views', 'N/A')
            summary = video.get('summarized_content', 'N/A')
            subtitles = video.get('subtitles', 'N/A')
            
            video_info_for_prompt.append(f"Title: {title}\nViews: {views}\nSummary: {summary}\nSubtitles: {subtitles}\n---")
        
        full_prompt = f"{content_suggestion_prompt}\n\nScraped Video Data:\n\n{'\n'.join(video_info_for_prompt)}"

        if status:
            status.update(f"[white]Generating content suggestions (using API key ending in {gemini_api_key[-4:]})...[/white]")
        
        suggestions = generate_gemini(None, api_pool, api_call_tracker, rate_limiter, full_prompt, model_name='gemini-2.5-flash', status=status, verbose=verbose)
        
        if suggestions:
            _log("Successfully generated content suggestions.", verbose)
            return suggestions
        else:
            _log("Failed to generate content suggestions.", verbose, is_error=True)
            return None

    except Exception as e:
        _log(f"Error suggesting content with Gemini: {e}", verbose, is_error=True)
        return None 