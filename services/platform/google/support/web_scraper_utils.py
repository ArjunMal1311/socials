import os
import json
import requests

from datetime import datetime
from bs4 import BeautifulSoup
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from typing import List, Dict, Any, Optional

from profiles import PROFILES

from services.support.path_config import ensure_dir_exists, get_google_profile_dir
from services.platform.google.support.google_api_utils import initialize_google_search_api, get_google_search_results

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None, api_info: Optional[Dict[str, Any]] = None):
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
    
    if verbose or is_error:
        console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def fetch_web_page_content(url: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[str]:
    try:
        _log(f"Fetching content from URL: {url}", verbose, status=status)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()
        
        text = soup.get_text()
        cleaned_text = os.linesep.join([s for s in text.splitlines() if s])
        _log(f"Successfully fetched content from {url}", verbose, status=status)
        return cleaned_text
    except requests.exceptions.RequestException as e:
        _log(f"Error fetching content from {url}: {e}", verbose, is_error=True, status=status)
        return None
    except Exception as e:
        _log(f"An unexpected error occurred while fetching content from {url}: {e}", verbose, is_error=True, status=status)
        return None


def run_web_scraper(profile_name: str, user_keyword: str, status: Optional[Status] = None, verbose: bool = False) -> List[Dict[str, Any]]:
    load_dotenv()
    
    profile_config = PROFILES.get(profile_name, {})
    web_scraper_config = profile_config.get("web_scraper_config", {})

    if not web_scraper_config:
        _log(f"No web scraper configuration found for profile '{profile_name}'.", verbose, is_error=True, status=status)
        return []

    data_sources_reference = web_scraper_config.get("data_sources_reference", [])
    num_search_results_per_source = web_scraper_config.get("num_search_results_per_source", 5)

    if not data_sources_reference:
        _log(f"Missing data_sources_reference in profile '{profile_name}'.", verbose, is_error=True, status=status)
        return []

    google_service = initialize_google_search_api(profile_name, verbose=verbose)
    if not google_service:
        return []
        
    all_scraped_data = []

    for source in data_sources_reference:
        source_name = source.get("Source Name", "Unknown Source")
        source_website = source.get("website", None)
        
        query = f"{user_keyword} {source_name}"
        
        if status:
            status.update(f"[white]Searching Google for '{query}' (Source: {source_name})...[/white]")
        _log(f"Searching Google for query: '{query}' (Source: {source_name})...", verbose, status=status)

        raw_results = get_google_search_results(profile_name, google_service, query, num_results=num_search_results_per_source, status=status, verbose=verbose)
        
        for result in raw_results:
            link = result.get("link")
            if link:
                content = fetch_web_page_content(link, verbose, status)
                if content:
                    all_scraped_data.append({"query": query, "source_name": source_name, "source_website": source_website, "data_point": user_keyword, "url": link, "content": content})

    web_output_dir = get_google_profile_dir(profile_name)
    ensure_dir_exists(web_output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(web_output_dir, f"web_scraped_data_{timestamp}.json")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_scraped_data, f, indent=2, ensure_ascii=False)
        _log(f"Web scraped data saved to {output_file}", verbose, status=status)
    except Exception as e:
        _log(f"Error saving web scraped data to {output_file}: {e}", verbose, is_error=True, status=status)

    return all_scraped_data
