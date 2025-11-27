import os
import time

from dotenv import load_dotenv
from rich.console import Console
from googleapiclient.discovery import build
from typing import List, Dict, Any, Optional, Tuple
from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_google_log_file_path

console = Console()

_api_call_tracker_instances: Dict[str, APICallTracker] = {}
_rate_limiter_instances: Dict[str, RateLimiter] = {}

def _get_api_trackers(profile_name: str) -> Tuple[APICallTracker, RateLimiter]:
    if profile_name not in _api_call_tracker_instances:
        log_file = get_google_log_file_path(profile_name)
        _api_call_tracker_instances[profile_name] = APICallTracker(log_file=log_file)
    if profile_name not in _rate_limiter_instances:
        _rate_limiter_instances[profile_name] = RateLimiter(rpm_limit=100)
    return _api_call_tracker_instances[profile_name], _rate_limiter_instances[profile_name]

def _handle_rate_limit(profile_name: str, method_name: str, status=None, verbose: bool = False):
    api_call_tracker, rate_limiter = _get_api_trackers(profile_name)
    api_key_suffix = os.getenv("GOOGLE_API_KEY")[-4:] if os.getenv("GOOGLE_API_KEY") else "N/A"
    while True:
        can_call, reason = api_call_tracker.can_make_call("google_search", method_name, api_key_suffix=api_key_suffix)
        if can_call:
            break
        api_info = api_call_tracker.get_quot_info("google_search", method_name, api_key_suffix=api_key_suffix)
        log(f"Rate limit hit for Google Search API ({method_name}): {reason}. Waiting...", verbose, is_error=True, status=status, api_info=api_info, log_caller_file="google_api_utils.py")
        sleep_time = rate_limiter.wait_if_needed(api_key_suffix)
        if sleep_time > 0:
            time.sleep(sleep_time)

def initialize_google_search_api(profile_name: str, verbose: bool = False) -> Optional[Any]:
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_SEARCH_API_KEY")
    google_cx_id = os.getenv("GOOGLE_CSE_ID")

    if not all([google_api_key, google_cx_id]):
        log("Google Custom Search API key (GOOGLE_SEARCH_API_KEY) or Search Engine ID (GOOGLE_CSE_ID) not found in .env. API cannot be initialized.", verbose, is_error=True, log_caller_file="google_api_utils.py")
        return None
    
    try:
        service = build("customsearch", "v1", developerKey=google_api_key)
        log("Google Custom Search API initialized successfully.", verbose, log_caller_file="google_api_utils.py")
        return service
    except Exception as e:
        log(f"Error initializing Google Custom Search API: {e}", verbose, is_error=True, log_caller_file="google_api_utils.py")
        return None

def get_google_search_results(profile_name: str, service: Any, query: str, time_filter: str = "qdr:w", num_results: int = 10, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    google_cx_id = os.getenv("GOOGLE_CSE_ID")
    api_key_suffix = os.getenv("GOOGLE_SEARCH_API_KEY")[-4:] if os.getenv("GOOGLE_SEARCH_API_KEY") else "N/A"
    
    if not service or not google_cx_id:
        log("Google Custom Search API not initialized or Search Engine ID is missing.", verbose, is_error=True, status=status, log_caller_file="google_api_utils.py")
        return []
    
    results_data = []
    api_call_tracker, rate_limiter = _get_api_trackers(profile_name)
    method_name = "search_query"
    try:
        log(f"Searching Google for query: '{query}' with time filter '{time_filter}'...", verbose, status=status, log_caller_file="google_api_utils.py")
        _handle_rate_limit(profile_name, method_name, status, verbose)

        res = service.cse().list(q=query, cx=google_cx_id, num=num_results, lr="lang_en", sort="date", dateRestrict=time_filter).execute()
        items = res.get('items', [])

        for item in items:
            results_data.append({
                "title": item.get('title'),
                "link": item.get('link'),
                "snippet": item.get('snippet'),
                "display_link": item.get('displayLink'),
                "pagemap": item.get('pagemap')
            })
        api_call_tracker.record_call("google_search", method_name, api_key_suffix=api_key_suffix, success=True)
        log(f"Found {len(results_data)} results for query: '{query}'.", verbose, status=status, log_caller_file="google_api_utils.py")
    except Exception as e:
        api_call_tracker.record_call("google_search", method_name, api_key_suffix=api_key_suffix, success=False, response=str(e))
        log(f"Error fetching Google search results for query '{query}': {e}", verbose, is_error=True, status=status, log_caller_file="google_api_utils.py")
    return results_data
