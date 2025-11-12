import argparse

from datetime import datetime
from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console
from typing import Dict, Any, Optional

from services.platform.google.support.web_scraper_utils import run_web_scraper
from services.platform.google.support.web_content_analyzer import analyze_web_content_with_gemini

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


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Web Scraper and Content Analyzer CLI Tool")

    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use from profiles.py")
    
    # Scrape web
    parser.add_argument("--scrape-web", action="store_true", help="Activate web scraping mode.")
    parser.add_argument("--keyword", type=str, default=None, help="Specify a keyword for web scraping")

    # Anlayze the content
    parser.add_argument("--analyze-web-content", action="store_true", help="Analyze scraped web data with Gemini.")

    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")   
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    
    args = parser.parse_args()

    if args.scrape_web:
        if not args.keyword:
            _log("Error: --keyword argument is required for web scraping.", args.verbose, is_error=True)
            parser.print_help()
            return
        with Status(f"[white]Running Web Scraper for profile '{args.profile}' with keyword '{args.keyword}' ...[/white]", spinner="dots", console=console) as status:
            scraped_data = run_web_scraper(args.profile, user_keyword=args.keyword, status=status, verbose=args.verbose)
            if scraped_data:
                _log(f"Successfully scraped {len(scraped_data)} web results.", args.verbose, status=status)
            else:
                _log("No web data scraped.", args.verbose, is_error=True, status=status)
    elif args.analyze_web_content:
        profile_name = args.profile
        with Status(f"[white]Analyzing web content for profile '{profile_name}' ...[/white]", spinner="dots", console=console) as status:
            analysis_results = analyze_web_content_with_gemini(profile_name, api_key=args.api_key, status=status, verbose=args.verbose)
            status.stop()

            if analysis_results:
                console.print("""[bold green]--- Web Content Analysis Results ---[/bold green]""")
                for result in analysis_results:
                    console.print(f"URL: {result.get('url', 'N/A')}")
                    if "error" in result:
                        console.print(f"Error: [red]{result['error']}[/red]")
                    else:
                        for analysis_item in result.get('analysis', []):
                            console.print(f"  Data Point: {analysis_item.get('data_point_name', 'N/A')}")
                            console.print(f"  Info Extracted: {analysis_item.get('info_extracted', 'N/A')}")
                            console.print(f"  Confidence: {analysis_item.get('confidence_level', 'N/A')}")
                            console.print("-" * 20)
                console.print("[bold green]------------------------------------[/bold green]")
            else:
                _log("Failed to analyze web content.", args.verbose, is_error=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
