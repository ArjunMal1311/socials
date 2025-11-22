import os
import json
import google.generativeai as genai

from profiles import PROFILES

from typing import Optional
from datetime import datetime
from rich.status import Status
from rich.console import Console
from services.support.api_key_pool import APIKeyPool
from services.platform.x.support.file_manager import get_latest_dated_json_file as get_latest_x_data
from services.support.path_config import get_reddit_profile_dir, get_community_dir, get_ideas_aggregated_dir
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_error:
        level = "ERROR"
        style = "bold red"
    else:
        level = "INFO"
        style = "white"
    
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    if verbose or is_error:
        console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def calculate_reddit_tokens(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[int]:
    _log("Calculating tokens for Reddit data...", verbose, status=status)

    profile_dir = get_reddit_profile_dir(profile_name)
    latest_file = get_latest_reddit_data(directory=profile_dir, prefix="reddit_scraped_data_")

    if not latest_file or not os.path.exists(latest_file):
        _log(f"No latest Reddit data file found for profile {profile_name}. Cannot calculate tokens.", verbose, is_error=True, status=status)
        return None

    with open(latest_file, 'r', encoding='utf-8') as f:
        reddit_data = json.load(f)
    
    json_data = json.dumps(reddit_data, indent=2, ensure_ascii=False)

    api_key_pool = APIKeyPool()
    current_api_key = api_key_pool.get_key()
    if not current_api_key:
        _log("No API key available in the pool for token counting.", verbose, is_error=True, status=status)
        return None
    genai.configure(api_key=current_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    token_count = model.count_tokens(json_data).total_tokens
    return token_count

def calculate_x_tokens(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[int]:
    _log("Calculating tokens for X data...", verbose, status=status)

    profile_config = PROFILES.get(profile_name, {})
    x_config = profile_config.get("data", {}).get("x", {})
    communities = x_config.get("communities", [])

    if not communities:
        _log(f"No communities specified for X platform in profile '{profile_name}'. Cannot calculate tokens.", verbose, is_error=True, status=status)
        return None

    total_tokens = 0
    api_key_pool = APIKeyPool()
    current_api_key = api_key_pool.get_key()
    if not current_api_key:
        _log("No API key available in the pool for token counting.", verbose, is_error=True, status=status)
        return None
    genai.configure(api_key=current_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    for community_name in communities:
        community_prefix = community_name
        profile_dir = get_community_dir(profile_name)
        latest_file = get_latest_x_data(directory=profile_dir, prefix=community_prefix + "_")

        if not latest_file or not os.path.exists(latest_file):
            _log(f"No latest X data file found for profile {profile_name} with prefix '{community_prefix}'. Skipping token calculation for this community.", verbose, is_error=True, status=status)
            continue

        _log(f"Loading data from {latest_file} for token calculation (community: {community_name}).", verbose, status=status)
        with open(latest_file, 'r', encoding='utf-8') as f:
            x_data = json.load(f)
        
        json_data = json.dumps(x_data, indent=2, ensure_ascii=False)

        community_token_count = model.count_tokens(json_data).total_tokens
        _log(f"Tokens for community '{community_name}': {community_token_count}", verbose, status=status)
        total_tokens += community_token_count

    return total_tokens

def calculate_aggregated_tokens(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[int]:
    _log("Calculating tokens for aggregated data...", verbose, status=status)

    aggregated_dir = get_ideas_aggregated_dir(profile_name)
    aggregated_file = os.path.join(aggregated_dir, "aggregate.json")

    if not os.path.exists(aggregated_file):
        _log(f"No aggregated data file found for profile {profile_name}. Cannot calculate tokens.", verbose, is_error=True, status=status)
        return None

    with open(aggregated_file, 'r', encoding='utf-8') as f:
        aggregated_data = json.load(f)
    
    json_data = json.dumps(aggregated_data, indent=2, ensure_ascii=False)

    api_key_pool = APIKeyPool()
    current_api_key = api_key_pool.get_key()
    if not current_api_key:
        _log("No API key available in the pool for token counting.", verbose, is_error=True, status=status)
        return None
    genai.configure(api_key=current_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    token_count = model.count_tokens(json_data).total_tokens
    return token_count

