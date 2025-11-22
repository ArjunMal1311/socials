import argparse

from datetime import datetime
from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console
from typing import Dict, Any, Optional

from services.platform.reddit.support.scraper_utils import run_reddit_scraper
from services.platform.reddit.support.content_analyzer import analyze_reddit_content_with_gemini

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
    parser = argparse.ArgumentParser(description="Reddit Scraper CLI Tool")
    
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use from profiles.py")

    # scrape
    parser.add_argument("--scrape", action="store_true", help="Activate Reddit scraping mode.")
    parser.add_argument("--analyze-content", action="store_true", help="Analyze scraped Reddit data with Gemini to suggest content.")
    
    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    
    args = parser.parse_args()

    if args.scrape:
        with Status(f"[white]Running Reddit Scraper for profile '{args.profile}' ...[/white]", spinner="dots", console=console) as status:
            scraped_data = run_reddit_scraper(args.profile, status=status, verbose=args.verbose)
            if scraped_data:
                _log(f"Successfully scraped {len(scraped_data)} Reddit posts.", args.verbose, status=status)
                sample_post = scraped_data[0]
                _log("Sample Post:", args.verbose)
                _log(f"Title: {sample_post.get('title', '')}", args.verbose)
                _log(f"Subreddit: {sample_post.get('subreddit', '')}", args.verbose)
                _log(f"Score: {sample_post.get('score', 0)}", args.verbose)
                _log(f"Comments: {sample_post.get('num_comments', 0)}", args.verbose)
            else:
                _log("No Reddit data scraped.", args.verbose, is_error=True, status=status)
                
    elif args.analyze_content:
        profile_name = args.profile
        with Status(f"[white]Analyzing Reddit content for profile '{profile_name}' ...[/white]", spinner="dots", console=console) as status:
            suggestions = analyze_reddit_content_with_gemini(profile_name, api_key=args.api_key, status=status, verbose=args.verbose)
            status.stop()

            if suggestions:
                console.print("\n[bold green]--- Reddit Content Suggestions ---[/bold green]")
                console.print(suggestions)
                console.print("[bold green]----------------------------------[/bold green]")
            else:
                _log("Failed to generate Reddit content suggestions.", args.verbose, is_error=True)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
