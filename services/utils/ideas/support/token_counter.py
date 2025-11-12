import json
import os
import google.generativeai as genai
from typing import Optional

from rich.status import Status

from services.support.api_key_pool import APIKeyPool
from services.utils.ideas.support.clean import _log as clean_log
from services.support.path_config import get_reddit_profile_dir
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data

def calculate_reddit_tokens(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[int]:
    clean_log("Calculating tokens for Reddit data...", verbose, status=status)

    profile_dir = get_reddit_profile_dir(profile_name)
    latest_file = get_latest_reddit_data(directory=profile_dir, prefix="reddit_scraped_data_")

    if not latest_file or not os.path.exists(latest_file):
        clean_log(f"No latest Reddit data file found for profile {profile_name}. Cannot calculate tokens.", verbose, is_error=True, status=status)
        return None

    with open(latest_file, 'r', encoding='utf-8') as f:
        reddit_data = json.load(f)
    
    json_data = json.dumps(reddit_data, indent=2, ensure_ascii=False)

    api_key_pool = APIKeyPool()
    current_api_key = api_key_pool.get_key()
    if not current_api_key:
        clean_log("No API key available in the pool for token counting.", verbose, is_error=True, status=status)
        return None
    genai.configure(api_key=current_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    token_count = model.count_tokens(json_data).total_tokens
    return token_count

