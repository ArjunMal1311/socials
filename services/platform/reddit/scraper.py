import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console
from services.support.logger_util import _log as log
from services.platform.reddit.support.scraper_utils import run_reddit_scraper
from services.platform.reddit.support.content_analyzer import analyze_reddit_content_with_gemini

console = Console()


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
                log(f"Successfully scraped {len(scraped_data)} Reddit posts.", args.verbose, status=status, log_caller_file="scraper.py")
                sample_post = scraped_data[0]
                log("Sample Post:", args.verbose, log_caller_file="scraper.py")
                log(f"Title: {sample_post.get('title', '')}", args.verbose, log_caller_file="scraper.py")
                log(f"Subreddit: {sample_post.get('subreddit', '')}", args.verbose, log_caller_file="scraper.py")
                log(f"Score: {sample_post.get('score', 0)}", args.verbose, log_caller_file="scraper.py")
                log(f"Comments: {sample_post.get('num_comments', 0)}", args.verbose, log_caller_file="scraper.py")
            else:
                log("No Reddit data scraped.", args.verbose, is_error=True, status=status, log_caller_file="scraper.py")
                
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
                log("Failed to generate Reddit content suggestions.", args.verbose, is_error=True, log_caller_file="scraper.py")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
