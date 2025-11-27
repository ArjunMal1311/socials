from rich.console import Console
from typing import List, Dict, Any

console = Console()

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
