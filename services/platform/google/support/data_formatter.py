from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any, Optional

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Any] = None, api_info: Optional[Dict[str, Any]] = None):
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

def format_google_search_result(result: Dict[str, Any], query: str, time_filter: str) -> Dict[str, Any]:
    return {
        "source": "google_search",
        "query": query,
        "time_filter": time_filter,
        "title": result.get('title', 'N/A'),
        "link": result.get('link', 'N/A'),
        "snippet": result.get('snippet', 'N/A'),
        "display_link": result.get('displayLink', 'N/A')
    }

def format_google_search_results_list(results: List[Dict[str, Any]], query: str, time_filter: str) -> List[Dict[str, Any]]:
    return [format_google_search_result(result, query, time_filter) for result in results]
