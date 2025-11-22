import os
import json

from profiles import PROFILES

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Dict, Any, List, Optional
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.utils.ideas.support.clean import clean_reddit_data, clean_x_data
from services.support.path_config import get_reddit_profile_dir, get_community_dir
from services.platform.x.support.file_manager import get_latest_dated_json_file as get_latest_x_data
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data

console = Console()


def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None, api_info: Optional[Dict[str, Any]] = None, token_count: Optional[int] = None):
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
    
    if token_count is not None:
        formatted_message += f" | Tokens: {token_count}"

    if verbose or is_error:
        console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def get_latest_data(platform: str, profile_name: str, verbose: bool = False) -> Optional[List[Dict[str, Any]]]:
    if platform == "reddit":
        profile_dir = get_reddit_profile_dir(profile_name)
        latest_file = get_latest_reddit_data(directory=profile_dir, prefix="reddit_scraped_data_")
    elif platform == "x":
        profile_dir = get_community_dir(profile_name)
        latest_file = get_latest_x_data(directory=profile_dir, prefix="Build in Public_")
    else:
        _log(f"Unknown platform: {platform}", verbose, is_error=True)
        return None

    if latest_file and os.path.exists(latest_file):
        _log(f"Loading latest data for {platform} from {latest_file}", verbose)
        with open(latest_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        _log(f"No latest data found for {platform} in profile {profile_name}", verbose)
        return None

def get_and_clean_aggregated_data(profile_name: str, platforms: List[str], status: Optional[Status] = None, verbose: bool = False, clean: bool = False) -> Optional[Dict[str, Any]]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        _log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status)
        return None

    aggregated_data = {}
    for platform in platforms:
        data = get_latest_data(platform, profile_name, verbose)
        if data:
            if clean and platform == "reddit":
                _log(f"Cleaning data for {platform}...", verbose, status=status)
                data = clean_reddit_data(profile_name, verbose, status, data=data)
            elif clean and platform == "x":
                _log(f"Cleaning data for {platform}...", verbose, status=status)
                data = clean_x_data(profile_name, verbose, status)
            aggregated_data[platform] = data
    
    if not aggregated_data:
        _log("No data available from selected platforms.", verbose, is_error=True, status=status)
        return None
    return aggregated_data

def generate_content_titles(profile_name: str, platforms: List[str], api_key: Optional[str] = None, status: Optional[Status] = None, verbose: bool = False) -> Optional[str]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        _log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status)
        return None

    title_generation_prompt = profile_config.get("title_generation_prompt")
    if not title_generation_prompt:
        _log(f"'title_generation_prompt' not found in profile '{profile_name}'.", verbose, is_error=True, status=status)
        return None

    api_key_pool = APIKeyPool()
    api_call_tracker = APICallTracker()
    rate_limiter = RateLimiter(rpm_limit=60, verbose=verbose)

    aggregated_data = get_and_clean_aggregated_data(profile_name, platforms, status, verbose, clean=False)
    if not aggregated_data:
        return None

    full_prompt = f"{title_generation_prompt}\n\nHere is the aggregated data:\n"
    for platform, data in aggregated_data.items():
        full_prompt += f"\n--- {platform.upper()} Data ---\n"
        if isinstance(data, list) and len(data) > 0:
            json_data = json.dumps(data, indent=2, ensure_ascii=False)
            full_prompt += json_data
            _log(f"Full {platform} data included. Length: {len(json_data)}", verbose, status=status)
        else:
            full_prompt += "No relevant data available."
        full_prompt += "\n"

    _log("Generating content titles with Gemini...", verbose, status=status)
    gemini_output, token_count = generate_gemini(
        media_path=None,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        prompt_text=full_prompt,
        model_name="gemini-2.5-flash",
        status=status,
        verbose=verbose
    )

    if gemini_output:
        _log("Successfully generated content titles.", verbose, status=status, token_count=token_count)
        return gemini_output
    else:
        _log("Failed to generate content titles with Gemini.", verbose, is_error=True, status=status)
        return None

def generate_video_scripts(profile_name: str, selected_ideas: List[Dict[str, Any]], api_key: Optional[str] = None, status: Optional[Status] = None, verbose: bool = False) -> Optional[List[Dict[str, Any]]]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        _log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status)
        return None

    script_generation_prompt_template = profile_config.get("script_generation_prompt")
    if not script_generation_prompt_template:
        _log(f"'script_generation_prompt' not found in profile '{profile_name}'.", verbose, is_error=True, status=status)
        return None

    api_key_pool = APIKeyPool()
    api_call_tracker = APICallTracker()
    rate_limiter = RateLimiter(rpm_limit=60, verbose=verbose)

    generated_scripts = []
    for idea in selected_ideas:
        topic = idea.get("topic", "")
        video_title = idea.get("video_title", "")
        why_trending = idea.get("why_trending", "")
        discussion_data = json.dumps(idea, indent=2, ensure_ascii=False)

        full_prompt = script_generation_prompt_template.format(
            topic=topic,
            video_title=video_title,
            why_trending=why_trending,
            discussion_data=discussion_data
        )

        _log(f"Generating script for title: '{video_title}' with Gemini...", verbose, status=status)
        gemini_output, token_count = generate_gemini(
            media_path=None,
            api_key_pool=api_key_pool,
            api_call_tracker=api_call_tracker,
            rate_limiter=rate_limiter,
            prompt_text=full_prompt,
            model_name="gemini-2.5-flash",
            status=status,
            verbose=verbose
        )

        if gemini_output:
            _log(f"Successfully generated script for '{video_title}'.", verbose, status=status, token_count=token_count)
            try:
                cleaned_script_string = gemini_output.replace("```json", "").replace("```", "").strip()
                script_data = json.loads(cleaned_script_string)
                generated_scripts.append({"idea": idea, "script": script_data})
            except json.JSONDecodeError:
                _log(f"Failed to parse Gemini output for script of '{video_title}'. Output: {gemini_output}", verbose, is_error=True, status=status)
        else:
            _log(f"Failed to generate script for '{video_title}' with Gemini.", verbose, is_error=True, status=status)
    return generated_scripts
