import os
import sys
import argparse

from dotenv import load_dotenv

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.utils.suggestions.support.scraping_utils import run_suggestions_workflow
from services.utils.suggestions.support.content_filter import filter_and_sort_content, get_latest_scraped_file

from rich.console import Console

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Content Inspiration Scraper")
    parser.add_argument("profile", type=str, help="Profile name to use")
    parser.add_argument("command", choices=['scrape', 'filter', 'web'], help="Command to run")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="suggestions.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="suggestions.py")
        sys.exit(1)

    profile_name = profile

    if args.command == 'scrape':
        profile_props = PROFILES[profile_name].get('properties', {})
        max_tweets_profile = profile_props.get('max_tweets_profile', 20)
        max_tweets_community = profile_props.get('max_tweets_community', 20)
        verbose = profile_props.get('verbose', False)
        headless = profile_props.get('headless', True)

        log(f"Starting content scraping for profile: {profile_name}", verbose, log_caller_file="suggestions.py")

        result = run_suggestions_workflow(
            profile_name=profile_name,
            max_tweets_profile=max_tweets_profile,
            max_tweets_community=max_tweets_community,
            verbose=verbose,
            headless=headless
        )

        if "error" in result:
            log(result["error"], verbose, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        console.print(f"\n[green]Content scraped successfully![/green]")
        console.print(f"Total tweets scraped: {result['total_tweets_scraped']}")
        console.print(f"Saved to: {result['saved_file']}")

        console.print(f"\n[yellow]Run 'socials utils {profile_name} suggestions filter' to filter and sort the content[/yellow]")

    elif args.command == 'filter':
        log(f"Starting content filtering for profile: {profile_name}", False, log_caller_file="suggestions.py")

        scraped_file = get_latest_scraped_file(profile_name)
        if not scraped_file:
            log("No scraped content found. Run 'scrape' command first.", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        result = filter_and_sort_content(scraped_file, profile_name)

        if "error" in result:
            log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        console.print(f"\n[green]Content filtered and sorted![/green]")
        console.print(f"Original tweets: {result['original_count']}")
        console.print(f"Filtered to top: {result['filtered_count']}")
        console.print(f"Saved to: {result['saved_file']}")

        console.print(f"\n[yellow]Review the filtered content in {result['saved_file']} for approval[/yellow]")

    elif args.command == 'web':
        console.print(f"\n[blue]Starting web interface for profile: {profile_name}[/blue]")
        console.print("Open your browser to: http://localhost:5000/" + profile_name)
        console.print("Press Ctrl+C to stop the server")

        try:
            from services.utils.suggestions.support.web.app import run_server
            run_server(port=5000)
        except KeyboardInterrupt:
            console.print("\n[yellow]Web server stopped[/yellow]")
        except Exception as e:
            log(f"Error starting web server: {e}", False, is_error=True, log_caller_file="suggestions.py")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()