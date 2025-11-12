import os
import json

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Dict, Any, List, Optional

from profiles import PROFILES

from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_reddit_profile_dir
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data
from services.utils.ideas.support.clean import clean_reddit_data

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

def aggregate_and_suggest_ideas(profile_name: str, platforms: List[str], api_key: Optional[str] = None, status: Optional[Status] = None, verbose: bool = False, clean: bool = False) -> Optional[str]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        _log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status)
        return None

    idea_prompt = profile_config.get("idea_prompt")
    if not idea_prompt:
        _log(f"'idea_prompt' not found in profile '{profile_name}'.", verbose, is_error=True, status=status)
        return None

    api_key_pool = APIKeyPool()
    api_call_tracker = APICallTracker()
    rate_limiter = RateLimiter(rpm_limit=60, verbose=verbose)

    aggregated_data = {}
    for platform in platforms:
        data = get_latest_data(platform, profile_name, verbose)
        if data:
            aggregated_data[platform] = data
    
    if not aggregated_data:
        _log("No data available from selected platforms for content suggestion.", verbose, is_error=True, status=status)
        return None

    full_prompt = f"{idea_prompt}\n\nHere is the aggregated data:\n"
    for platform, data in aggregated_data.items():
        full_prompt += f"\n--- {platform.upper()} Data ---\n"
        if isinstance(data, list) and len(data) > 0:
            if platform == "reddit":
                json_data = json.dumps(data, indent=2, ensure_ascii=False)
                full_prompt += json_data
                _log(f"Full Reddit data included. Length: {len(json_data)}", verbose, status=status)
            else:
                full_prompt += json.dumps(data, indent=2, ensure_ascii=False)
        else:
            full_prompt += "No relevant data available."
        full_prompt += "\n"

    _log("Generating content ideas with Gemini...", verbose, status=status)
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
        _log("Successfully generated content ideas.", verbose, status=status, token_count=token_count)
        return gemini_output
    else:
        _log("Failed to generate content ideas with Gemini.", verbose, is_error=True, status=status)
        return None
