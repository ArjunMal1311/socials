import os
import json

from datetime import datetime
from rich.console import Console
from typing import Dict, Any, Optional, List

from profiles import PROFILES

from rich.status import Status
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.platform.google.support.file_manager import get_latest_dated_json_file
from services.support.path_config import get_google_analysis_dir, ensure_dir_exists, get_google_profile_dir

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

def analyze_web_content_with_gemini(profile_name: str, api_key: Optional[str] = None, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    api_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()
    if api_key:
        api_pool.set_explicit_key(api_key)

    gemini_api_key = api_pool.get_key()
    if not gemini_api_key:
        _log("No Gemini API key available.", verbose, is_error=True)
        return []

    profile_config = PROFILES.get(profile_name, {})
    web_scraper_config = profile_config.get("web_scraper_config", {})

    if not web_scraper_config:
        _log(f"No web scraper configuration found for profile '{profile_name}'.", verbose, is_error=True, status=status)
        return []

    data_sources_reference = web_scraper_config.get("data_sources_reference", [])
    market_research_data_points = web_scraper_config.get("market_research_data_points", [])
    analysis_user_prompt = web_scraper_config.get("analysis_user_prompt", "Analyze these market research data points from various sources and extract information for each data point.")

    latest_scraped_data_path = get_latest_dated_json_file(get_google_profile_dir(profile_name), "web_scraped_data", verbose=verbose)

    if not latest_scraped_data_path:
        _log(f"No latest scraped web data found for profile '{profile_name}'. Please run web scraper first.", verbose, is_error=True, status=status)
        return []

    try:
        with open(latest_scraped_data_path, 'r', encoding='utf-8') as f:
            scraped_web_data = json.load(f)
    except Exception as e:
        _log(f"Error loading scraped web data from {latest_scraped_data_path}: {e}", verbose, is_error=True, status=status)
        return []

    if not scraped_web_data:
        _log("No web data found in the latest scraped file. Cannot perform analysis.", verbose, status=status)
        return []

    all_analysis_results = []

    full_analysis_prompt_template = web_scraper_config.get("full_analysis_prompt_template", "")
    if not full_analysis_prompt_template:
        _log("No full_analysis_prompt_template found in profile configuration.", verbose, is_error=True, status=status)
        return []

    for item in scraped_web_data:
        url = item["url"]
        content = item["content"]
        
        try:
            if not content:
                all_analysis_results.append({"url": url, "error": "Content is empty or could not be read.", "analysis": []})
                continue
            
            formatted_analysis_prompt = full_analysis_prompt_template.format(
                analysis_user_prompt=analysis_user_prompt,
                data_sources_reference=json.dumps(data_sources_reference, indent=2),
                market_research_data_points=json.dumps(market_research_data_points, indent=2)
            )

            full_prompt_for_item = f"""{formatted_analysis_prompt}

                Input Data:
                {{
                \"url\": \"{url}\",
                \"content\": \"{content}\"
                }}
            """
            
            _log(f"[white]Sending prompt for URL: {url}[/white]", verbose, status=status)
            suggestions, _ = generate_gemini(
                media_path=None, 
                api_key_pool=api_pool, 
                api_call_tracker=api_call_tracker, 
                rate_limiter=rate_limiter, 
                prompt_text=full_prompt_for_item, 
                model_name='gemini-2.5-flash', 
                status=status, 
                verbose=verbose
            )
            
            if suggestions:
                _log(f"[white]Raw Gemini response (length {len(suggestions)}):\n{suggestions}[/white]", verbose, status=status)
                cleaned_response_text = suggestions.strip()
                if cleaned_response_text.startswith('```json') and cleaned_response_text.endswith('```'):
                    cleaned_response_text = cleaned_response_text[len('```json'):-len('```')].strip()
                elif cleaned_response_text.startswith('```') and cleaned_response_text.endswith('```'):
                    cleaned_response_text = cleaned_response_text[len('```'):-len('```')].strip()
                
                if not cleaned_response_text:
                    all_analysis_results.append({"url": url, "error": "Gemini returned empty text after stripping markdown.", "raw_response": suggestions.strip()})
                    continue

                _log(f"[white]Cleaned Gemini response text (length {len(cleaned_response_text)}):\n{cleaned_response_text}[/white]", verbose, status=status)

                try:
                    parsed_analysis = json.loads(cleaned_response_text)
                    if isinstance(parsed_analysis, dict):
                        parsed_analysis = [parsed_analysis]
                    all_analysis_results.append({"url": url, "analysis": parsed_analysis})
                except json.JSONDecodeError as e:
                    all_analysis_results.append({"url": url, "error": f"Failed to parse Gemini JSON response: {e}", "raw_response": cleaned_response_text})
            else:
                _log(f"Failed to get suggestions from Gemini for URL: {url}", verbose, is_error=True, status=status)
                all_analysis_results.append({"url": url, "error": "Gemini returned no text.", "analysis": []})

        except Exception as e:
            _log(f"Error processing content for {url}: {e}", verbose, is_error=True, status=status)
            all_analysis_results.append({"url": url, "error": f"Error processing content for {url}: {e}", "analysis": []})

    analysis_output_dir = get_google_analysis_dir(profile_name)
    ensure_dir_exists(analysis_output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(analysis_output_dir, f"web_content_analysis_results_{timestamp}.json")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_analysis_results, f, indent=2, ensure_ascii=False)
        _log(f"Web content analysis results saved to {output_file}", verbose, status=status)
    except Exception as e:
        _log(f"Error saving web content analysis results to {output_file}: {e}", verbose, is_error=True, status=status)

    return all_analysis_results
