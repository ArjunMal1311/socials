import os
import json

from profiles import PROFILES

from rich.status import Status
from rich.console import Console
from typing import Dict, Any, List, Optional
from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_ideas_aggregated_dir

console = Console()

def generate_content_titles(profile_name: str, status: Optional[Status] = None, verbose: bool = False) -> Optional[str]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    title_generation_prompt = profile_config.get("prompts", {}).get("content_ideas")
    if not title_generation_prompt:
        log(f"'content_ideas' prompt not found in profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    aggregated_dir = get_ideas_aggregated_dir(profile_name)
    aggregate_file_path = os.path.join(aggregated_dir, "aggregate.json")

    if not os.path.exists(aggregate_file_path):
        log(f"No aggregated data file found at {aggregate_file_path}. Please run --aggregate first.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    try:
        with open(aggregate_file_path, 'r', encoding='utf-8') as f:
            aggregated_data = json.load(f)
        all_items = aggregated_data.get("items", [])
    except Exception as e:
        log(f"Error loading aggregated data from {aggregate_file_path}: {e}", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    if not all_items:
        log("No items found in aggregated data. Cannot generate content titles.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    api_key_pool = APIKeyPool()
    api_call_tracker = APICallTracker()
    rate_limiter = RateLimiter(rpm_limit=60, verbose=verbose)

    full_prompt = f"{title_generation_prompt}\n\nHere is the aggregated data:\n"
    
    json_data = json.dumps(all_items, indent=2, ensure_ascii=False)
    full_prompt += json_data
    log(f"Full aggregated data included. Length: {len(json_data)}", verbose, status=status, log_caller_file="idea_utils.py")

    log("Generating content titles with Gemini...", verbose, status=status, log_caller_file="idea_utils.py")
    gemini_output = generate_gemini(
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
        log("Successfully generated content titles.", verbose, status=status, log_caller_file="idea_utils.py")
        return gemini_output
    else:
        log("Failed to generate content titles with Gemini.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

def generate_video_scripts(profile_name: str, selected_ideas: List[Dict[str, Any]], api_key: Optional[str] = None, status: Optional[Status] = None, verbose: bool = False) -> Optional[List[Dict[str, Any]]]:
    profile_config = PROFILES.get(profile_name)
    if not profile_config:
        log(f"Profile '{profile_name}' not found.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        return None

    script_generation_prompt_template = profile_config.get("prompts", {}).get("content_ideas")
    if not script_generation_prompt_template:
        log(f"'content_ideas' prompt not found in profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
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

        log(f"Generating script for title: '{video_title}' with Gemini...", verbose, status=status, log_caller_file="idea_utils.py")
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
            log(f"Successfully generated script for '{video_title}'.", verbose, status=status, log_caller_file="idea_utils.py")
            try:
                cleaned_script_string = gemini_output.replace("```json", "").replace("```", "").strip()
                script_data = json.loads(cleaned_script_string)
                generated_scripts.append({"idea": idea, "script": script_data})
            except json.JSONDecodeError:
                log(f"Failed to parse Gemini output for script of '{video_title}'. Output: {gemini_output}", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
        else:
            log(f"Failed to generate script for '{video_title}' with Gemini.", verbose, is_error=True, status=status, log_caller_file="idea_utils.py")
    return generated_scripts
