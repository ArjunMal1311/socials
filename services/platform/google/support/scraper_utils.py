import os
import json

from datetime import datetime
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from typing import List, Dict, Any, Optional

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import ensure_dir_exists, get_google_profile_dir
from services.platform.google.support.data_formatter import format_google_search_results_list
from services.platform.google.support.google_api_utils import initialize_google_search_api, get_google_search_results

console = Console()

def run_google_scraper(profile_name: str, status: Optional[Status] = None, verbose: bool = False) -> List[Dict[str, Any]]:
    load_dotenv()
    
    profile_config = PROFILES.get(profile_name, {})
    google_search_config = profile_config.get("google_search", {})

    if not google_search_config:
        log(f"No Google Search configuration found for profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []

    search_queries = google_search_config.get("search_queries", [])
    time_filter = google_search_config.get("time_filter", "qdr:w")
    num_results = google_search_config.get("num_results", 10)

    if not search_queries:
        log(f"No search queries specified for Google Search in profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []

    google_service = initialize_google_search_api(profile_name, verbose=verbose)
    if not google_service:
        return []
        
    all_formatted_results = []

    for query in search_queries:
        if status:
            status.update(f"[white]Searching Google for '{query}' (filter: {time_filter})...[/white]")
        log(f"Searching Google for query: '{query}' (filter: {time_filter})...", verbose, status=status, log_caller_file="scraper_utils.py")
        raw_results = get_google_search_results(profile_name, google_service, query, time_filter, num_results, status=status, verbose=verbose)
        formatted_results = format_google_search_results_list(raw_results, query, time_filter)
        all_formatted_results.extend(formatted_results)

    google_output_dir = get_google_profile_dir(profile_name)
    ensure_dir_exists(google_output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(google_output_dir, f"google_scraped_data_{timestamp}.json")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_formatted_results, f, indent=2, ensure_ascii=False)
        log(f"Google scraped data saved to {output_file}", verbose, status=status, log_caller_file="scraper_utils.py")
    except Exception as e:
        log(f"Error saving Google scraped data to {output_file}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")

    return all_formatted_results
