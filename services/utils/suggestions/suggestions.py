# socials utils <profile> suggestions x [scrape, filter, web, download, trends, generate, generate_new, review, schedule, post]
# socials utils <profile> suggestions linkedin [scrape, filter, web, download, trends, generate, generate_new ,schedule, review, post]
# socials utils <profile> suggestions reddit [scrape, filter, web, download, trends]

import os
import sys
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.console import Console


sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.support.storage.storage_factory import get_storage

from services.utils.suggestions.support.x.web_app import run_web_app
from services.utils.suggestions.support.x.trends_analyzer import analyze_x_trends
from services.utils.suggestions.support.x.media_downloader import run_media_download
from services.utils.suggestions.support.x.scraping_utils import run_suggestions_workflow
from services.utils.suggestions.support.x.content_generator import run_content_generation
from services.utils.suggestions.support.x.scheduling_utils import run_content_scheduling, run_content_posting
from services.utils.suggestions.support.x.content_filter import filter_and_sort_content, get_latest_scraped_file
from services.utils.suggestions.support.x.content_generator import generate_new_tweets_from_filtered as generate_new_x_tweets

from services.utils.suggestions.support.linkedin.trends_analyzer import analyze_linkedin_trends
from services.utils.suggestions.support.linkedin.media_downloader import run_linkedin_media_download
from services.utils.suggestions.support.linkedin.scraping_utils import run_linkedin_suggestions_workflow
from services.utils.suggestions.support.linkedin.content_generator import run_linkedin_content_generation
from services.utils.suggestions.support.linkedin.content_generator import generate_new_linkedin_tweets_from_filtered
from services.utils.suggestions.support.linkedin.scheduling_utils import run_linkedin_content_scheduling, run_linkedin_content_posting
from services.utils.suggestions.support.linkedin.content_filter import filter_and_sort_linkedin_content, get_latest_scraped_linkedin_file

from services.utils.suggestions.support.reddit.trends_analyzer import analyze_reddit_trends
from services.utils.suggestions.support.reddit.media_downloader import run_reddit_media_download
from services.utils.suggestions.support.reddit.scraping_utils import run_reddit_suggestions_workflow
from services.utils.suggestions.support.reddit.content_generator import run_reddit_content_generation
from services.utils.suggestions.support.reddit.content_filter import filter_and_sort_reddit_content, get_latest_scraped_reddit_file

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Content Inspiration Scraper")
    parser.add_argument("profile", type=str, help="Profile name to use")
    parser.add_argument("platform", choices=['x', 'linkedin', 'reddit'], help="Platform to use")
    parser.add_argument("command", choices=['scrape', 'filter', 'web', 'generate', 'generate_new', 'trends', 'schedule', 'post', 'download', 'review'], help="Command to run")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="suggestions.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="suggestions.py")
        sys.exit(1)

    profile_name = profile
    platform = args.platform

    if platform == 'x':
        profile_props = PROFILES[profile_name].get('properties', {})
        utils_props = profile_props.get('utils', {})
        suggestions_props = utils_props.get('suggestions', {})
        global_props = profile_props.get('global', {})
        push_to_db = global_props.get('push_to_db', False)

        if args.command == 'scrape':
            max_tweets_profile = suggestions_props.get('count_x_profile', 20)
            max_tweets_community = suggestions_props.get('count_x_community', 20)
            verbose = global_props.get('verbose', False)
            headless = global_props.get('headless', True)

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
            if push_to_db:
                storage = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                if not storage:
                    log(f"Failed to get storage for {platform} suggestions_generated", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_content_generation(profile_name, storage=storage, verbose=global_props.get('verbose', False))
            else:
                result = run_content_generation(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Generated {result['total_generated']} captions[/green]")

        elif args.command == 'generate_new':
            if push_to_db:
                storage = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage:
                    log(f"Failed to get storage for {platform} suggestions_new", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = generate_new_x_tweets(profile_name, storage=storage, verbose=global_props.get('verbose', False))
            else:
                result = generate_new_x_tweets(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Generated {result['total_generated']} new tweets[/green]")

        elif args.command == 'schedule':
            if push_to_db:
                storage_generated = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                storage_new = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage_generated or not storage_new:
                    log(f"Failed to get storage for {platform} scheduling", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_content_scheduling(profile_name, storage_generated=storage_generated, storage_new=storage_new)
            else:
                result = run_content_scheduling(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            if result.get('scheduled_count', 0) > 0:
                console.print(f"[green]Scheduled {result['scheduled_count']} posts[/green]")
                if not push_to_db:
                    console.print(f"[green]Scheduled to {result['schedule_file']}[/green]")
                console.print(f"[yellow]Run 'socials x {profile_name} post process' to start posting[/yellow]")
            else:
                console.print("[yellow]No new posts to schedule[/yellow]")

        elif args.command == 'post':
            console.print(f"[blue]Posting scheduled suggestions for {profile_name}...[/blue]")
            console.print("This will post tweets from your schedule. Press Ctrl+C to stop.")

            if push_to_db:
                storage_generated = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                storage_new = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage_generated or not storage_new:
                    log(f"Failed to get storage for {platform} posting", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_content_posting(profile_name, storage_generated=storage_generated, storage_new=storage_new)
            else:
                result = run_content_posting(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]{result['message']}[/green]")

        elif args.command == 'download':
            result = run_media_download(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Downloaded media for {result['downloaded_count']} items from approved posts. Saved to {result['updated_file']}[/green]")

        elif args.command == 'trends':
            result = analyze_x_trends(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Analyzed trends from {result['posts_analyzed']} posts[/green]")
            console.print(f"[green]Found {result['trends_count']} trending topics[/green]")

        elif args.command == 'review':
            console.print(f"[yellow]Review functionality is now integrated into the main web app.[/yellow]")
            console.print(f"[blue]Content Workflow Web App: http://localhost:5000[/blue]")
            console.print(f"[blue]Go to: http://localhost:5000/{profile_name}/review[/blue]")
            console.print(f"[yellow]Then run: socials utils {profile_name} suggestions web[/yellow]")

    elif platform == 'linkedin':
        profile_props = PROFILES[profile_name].get('properties', {})
        utils_props = profile_props.get('utils', {})
        suggestions_props = utils_props.get('suggestions', {})
        global_props = profile_props.get('global', {})
        push_to_db = global_props.get('push_to_db', False)

        if args.command == 'scrape':
            max_posts_profile = suggestions_props.get('count_linkedin', 10)
            verbose = global_props.get('verbose', False)
            headless = global_props.get('headless', True)

            result = run_linkedin_suggestions_workflow(
                profile_name=profile_name,
                max_posts_per_profile=max_posts_profile,
                verbose=verbose,
                headless=headless
            )

            if "error" in result:
                log(result["error"], verbose, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Scraped {result['total_posts_scraped']} posts[/green]")

        elif args.command == 'filter':
            scraped_file = get_latest_scraped_linkedin_file(profile_name)
            if not scraped_file:
                log("No scraped content found. Run 'scrape' command first.", False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            result = filter_and_sort_linkedin_content(scraped_file, profile_name)

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
            if push_to_db:
                storage = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                if not storage:
                    log(f"Failed to get storage for {platform} suggestions_generated", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_linkedin_content_generation(profile_name, storage=storage, verbose=global_props.get('verbose', False))
            else:
                result = run_linkedin_content_generation(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Generated {result['total_generated']} posts[/green]")

        elif args.command == 'generate_new':
            if push_to_db:
                storage = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage:
                    log(f"Failed to get storage for {platform} suggestions_new", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = generate_new_linkedin_tweets_from_filtered(profile_name, storage=storage, verbose=global_props.get('verbose', False))
            else:
                result = generate_new_linkedin_tweets_from_filtered(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Generated {result['total_generated']} new posts[/green]")

        elif args.command == 'schedule':
            if push_to_db:
                storage_generated = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                storage_new = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage_generated or not storage_new:
                    log(f"Failed to get storage for {platform} scheduling", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_linkedin_content_scheduling(profile_name, storage_generated=storage_generated, storage_new=storage_new)
            else:
                result = run_linkedin_content_scheduling(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            if result.get('scheduled_count', 0) > 0:
                console.print(f"[green]Scheduled {result['scheduled_count']} posts[/green]")
                if not push_to_db:
                    console.print(f"[green]Scheduled to {result['schedule_file']}[/green]")
                console.print(f"[yellow]Run 'socials linkedin {profile_name} post' to start posting[/yellow]")
            else:
                console.print("[yellow]No new posts to schedule[/yellow]")

        elif args.command == 'post':
            console.print(f"[blue]Posting scheduled suggestions for {profile_name}...[/blue]")
            console.print("This will post content from your schedule. Press Ctrl+C to stop.")

            if push_to_db:
                storage_generated = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                storage_new = get_storage(platform, profile_name, 'suggestions_new', verbose=global_props.get('verbose', False))
                if not storage_generated or not storage_new:
                    log(f"Failed to get storage for {platform} posting", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_linkedin_content_posting(profile_name, storage_generated=storage_generated, storage_new=storage_new)
            else:
                result = run_linkedin_content_posting(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]{result['message']}[/green]")

        elif args.command == 'download':
            result = run_linkedin_media_download(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Downloaded media for {result['downloaded_count']} items from approved posts. Saved to {result['updated_file']}[/green]")

        elif args.command == 'trends':
            result = analyze_linkedin_trends(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Analyzed trends from {result['posts_analyzed']} posts[/green]")
            console.print(f"[green]Found {result['trends_count']} trending topics[/green]")

        elif args.command == 'review':
            console.print(f"[yellow]Review functionality is now integrated into the main web app.[/yellow]")
            console.print(f"[blue]Content Workflow Web App: http://localhost:5000[/blue]")
            console.print(f"[blue]Go to: http://localhost:5000/{profile_name}/review[/blue]")
            console.print(f"[yellow]Then run: socials utils {profile_name} suggestions web[/yellow]")

    elif platform == 'reddit':
        profile_props = PROFILES[profile_name].get('properties', {})
        utils_props = profile_props.get('utils', {})
        suggestions_props = utils_props.get('suggestions', {})
        global_props = profile_props.get('global', {})
        push_to_db = global_props.get('push_to_db', False)

        if args.command == 'scrape':
            max_posts_reddit = suggestions_props.get('count_reddit', 15)
            verbose = global_props.get('verbose', False)
            headless = global_props.get('headless', True)

            result = run_reddit_suggestions_workflow(profile_name=profile_name, max_posts=max_posts_reddit, verbose=verbose, headless=headless)

            if "error" in result:
                log(result["error"], verbose, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Scraped {result['total_posts_scraped']} Reddit posts[/green]")

        elif args.command == 'filter':
            scraped_file = get_latest_scraped_reddit_file(profile_name)
            if not scraped_file:
                log("No scraped content found. Run 'scrape' command first.", False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            result = filter_and_sort_reddit_content(scraped_file, profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Filtered {result['original_count']} to {result['filtered_count']} top Reddit posts[/green]")

        elif args.command == 'generate':
            if push_to_db:
                storage = get_storage(platform, profile_name, 'suggestions_generated', verbose=global_props.get('verbose', False))
                if not storage:
                    log(f"Failed to get storage for {platform} suggestions_generated", False, is_error=True, log_caller_file="suggestions.py")
                    sys.exit(1)
                result = run_reddit_content_generation(profile_name, storage=storage, verbose=global_props.get('verbose', False))
            else:
                result = run_reddit_content_generation(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Generated {result['total_generated']} Reddit post ideas[/green]")

        elif args.command == 'download':
            result = run_reddit_media_download(profile_name)

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Downloaded media for {result['downloaded_count']} items from approved Reddit posts. Saved to {result['updated_file']}[/green]")

        elif args.command == 'trends':
            result = analyze_reddit_trends(profile_name, verbose=global_props.get('verbose', False))

            if "error" in result:
                log(result["error"], False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            console.print(f"[green]Analyzed trends from {result['posts_analyzed']} posts[/green]")
            console.print(f"[green]Found {result['trends_count']} trending topics[/green]")

        else:
            log(f"Command '{args.command}' not implemented for Reddit platform yet.", False, is_error=True, log_caller_file="suggestions.py")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()