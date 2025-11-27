import os

from profiles import PROFILES

from rich.console import Console
from typing import List, Dict, Any, Optional, Tuple
from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker

console = Console()

def analyze_video_content_with_gemini(video_path: str, profile_name: str, status=None, api_key: Optional[str] = None, verbose: bool = False) -> Tuple[Optional[str], Optional[str]]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)
    
    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        log("No Gemini API key available.", verbose, is_error=True, log_caller_file="content_analyzer.py")
        return None, None

    try:
        rate_limiter.wait_if_needed(gemini_api_key)
        
        if not os.path.exists(video_path):
            log(f"Video file not found: {video_path}", verbose, is_error=True, log_caller_file="content_analyzer.py")
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
            log(f"Successfully analyzed video content for {os.path.basename(video_path)}.", verbose, log_caller_file="content_analyzer.py")
            return summary, transcript
        else:
            log(f"Failed to get both summary and transcript for {os.path.basename(video_path)}.", verbose, is_error=True, log_caller_file="content_analyzer.py")
            return summary, transcript

    except Exception as e:
        log(f"Error analyzing video content with Gemini: {e}", verbose, is_error=True, log_caller_file="content_analyzer.py")
        return None, None 

def suggest_best_content_with_gemini(videos_data: List[Dict[str, Any]], profile_name: str, api_key: Optional[str] = None, status=None, verbose: bool = False) -> Optional[str]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)
    
    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        log("No Gemini API key available for content suggestion.", verbose, is_error=True, log_caller_file="content_analyzer.py")
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
            log("Successfully generated content suggestions.", verbose, log_caller_file="content_analyzer.py")
            return suggestions
        else:
            log("Failed to generate content suggestions.", verbose, is_error=True, log_caller_file="content_analyzer.py")
            return None

    except Exception as e:
        log(f"Error suggesting content with Gemini: {e}", verbose, is_error=True, log_caller_file="content_analyzer.py")
        return None 