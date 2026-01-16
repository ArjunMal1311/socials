# socials utils <profile> suggestions scrape
# socials utils <profile> suggestions filter  
# socials utils <profile> suggestions web
# socials utils <profile> suggestions download
# socials utils <profile> suggestions generate
# socials utils <profile> suggestions schedule
# socials utils <profile> suggestions review
# socials utils <profile> suggestions post

import os
import sys
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.console import Console

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories

from services.utils.suggestions.support.x.web_app import run_web_app
from services.utils.suggestions.support.x.media_downloader import run_media_download
from services.utils.suggestions.support.x.scraping_utils import run_suggestions_workflow
from services.utils.suggestions.support.x.content_generator import run_content_generation
from services.utils.suggestions.support.x.scheduling_utils import run_content_scheduling, run_content_posting
from services.utils.suggestions.support.x.content_filter import filter_and_sort_content, get_latest_scraped_file

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Content Inspiration Scraper")
    parser.add_argument("profile", type=str, help="Profile name to use")
    parser.add_argument("command", choices=['scrape', 'filter', 'web', 'generate', 'schedule', 'post', 'download', 'review'], help="Command to run")

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

        console.print(f"[green]Scraped {result['total_tweets_scraped']} tweets[/green]")

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

        console.print(f"[green]Filtered {result['original_count']} to {result['filtered_count']} top posts[/green]")

    elif args.command == 'web':
        console.print(f"[blue]Content Workflow Web App: http://localhost:5000[/blue]")
        console.print(f"[blue]Profile workflow: http://localhost:5000/{profile_name}[/blue]")
        try:
            run_web_app(port=5000)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log(f"Error starting web server: {e}", False, is_error=True, log_caller_file="suggestions.py")

    elif args.command == 'generate':
        log(f"Starting content generation for profile: {profile_name}", False, log_caller_file="suggestions.py")

        result = run_content_generation(profile_name)

        if "error" in result:
            log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        console.print(f"[green]Generated {result['total_generated']} captions[/green]")

    elif args.command == 'schedule':
        log(f"Starting content scheduling for profile: {profile_name}", False, log_caller_file="suggestions.py")

        result = run_content_scheduling(profile_name)

        if "error" in result:
            log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        if result.get('scheduled_count', 0) > 0:
            console.print(f"[green]Scheduled {result['scheduled_count']} posts to {result['schedule_file']}[/green]")
            console.print(f"[yellow]Run 'socials x {profile_name} post process' to start posting[/yellow]")
        else:
            console.print("[yellow]No new posts to schedule[/yellow]")

    elif args.command == 'post':
        log(f"Starting content posting for profile: {profile_name}", False, log_caller_file="suggestions.py")

        console.print(f"[blue]Posting scheduled suggestions for {profile_name}...[/blue]")
        console.print("This will post tweets from your schedule. Press Ctrl+C to stop.")

        result = run_content_posting(profile_name)

        if "error" in result:
            log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        console.print(f"[green]{result['message']}[/green]")

    elif args.command == 'download':
        log(f"Starting media download for profile: {profile_name}", False, log_caller_file="suggestions.py")

        result = run_media_download(profile_name)

        if "error" in result:
            log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        console.print(f"[green]Downloaded media for {result['downloaded_count']} items from approved posts. Saved to {result['updated_file']}[/green]")

    elif args.command == 'review':
        console.print(f"[yellow]Review functionality is now integrated into the main web app.[/yellow]")
        console.print(f"[blue]Content Workflow Web App: http://localhost:5000[/blue]")
        console.print(f"[blue]Go to: http://localhost:5000/{profile_name}/review[/blue]")
        console.print(f"[yellow]Then run: socials utils {profile_name} suggestions web[/yellow]")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()