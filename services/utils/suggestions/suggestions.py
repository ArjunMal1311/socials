import os
import sys
import json
import random
import argparse

from profiles import PROFILES

from dotenv import load_dotenv
from rich.console import Console
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.api_key_pool import APIKeyPool
from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories, get_suggestions_dir, get_schedule_file_path

from services.platform.x.support.process_scheduled_tweets import process_scheduled_tweets

from services.utils.suggestions.support.content_generator import process_single_post
from services.utils.suggestions.support.content_filter import filter_and_sort_content, get_latest_scraped_file
from services.utils.suggestions.support.scraping_utils import run_suggestions_workflow, get_latest_approved_file, get_latest_suggestions_file

console = Console()

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Content Inspiration Scraper")
    parser.add_argument("profile", type=str, help="Profile name to use")
    parser.add_argument("command", choices=['scrape', 'filter', 'web', 'generate', 'schedule', 'post'], help="Command to run")

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
        console.print(f"[blue]Web server: http://localhost:5000/{profile_name}[/blue]")
        try:
            from services.utils.suggestions.support.web.app import run_server
            run_server(port=5000)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log(f"Error starting web server: {e}", False, is_error=True, log_caller_file="suggestions.py")

    elif args.command == 'generate':
        log(f"Starting content generation for profile: {profile_name}", False, log_caller_file="suggestions.py")

        approved_file = get_latest_approved_file(profile_name)
        if not approved_file:
            log("No approved content found. Run 'web' command and approve content first.", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        try:
            with open(approved_file, 'r') as f:
                approved_data = json.load(f)

            approved_posts = approved_data.get('approved_posts', [])
            if not approved_posts:
                log("No approved posts found in the file.", False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            profile_props = PROFILES[profile_name].get('properties', {})
            verbose = profile_props.get('verbose', False)

            console.print(f"[blue]Generating captions for {len(approved_posts)} posts...[/blue]")

            api_key_pool = APIKeyPool(verbose=verbose)
            if api_key_pool.size() == 0:
                log("No API keys available. Set GEMINI_API environment variable.", False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            media_dir = os.path.join(get_suggestions_dir(profile_name), "media")
            os.makedirs(media_dir, exist_ok=True)

            generated_posts = []
            with ThreadPoolExecutor(max_workers=api_key_pool.size()) as executor:
                futures = []
                for post in approved_posts:
                    post['profile_name'] = profile_name
                    future = executor.submit(process_single_post, post, api_key_pool, media_dir, verbose)
                    futures.append(future)

                for future in as_completed(futures):
                    result = future.result()
                    generated_posts.append(result)

            profile_config = PROFILES[profile_name]
            prompts = profile_config.get('prompts', {})
            caption_prompt = prompts.get('caption_generation', '')
            model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

            suggestions_content = {
                "timestamp": datetime.now().isoformat(),
                "profile_name": profile_name,
                "generated_posts": generated_posts,
                "metadata": {
                    "total_generated": len(generated_posts),
                    "caption_generation_prompt": caption_prompt,
                    "model_used": model_name,
                    "processing_date": datetime.now().strftime("%Y%m%d"),
                    "api_keys_used": api_key_pool.size()
                }
            }

            output_file = os.path.join(get_suggestions_dir(profile_name), f"suggestions_content_{datetime.now().strftime('%Y%m%d')}.json")
            with open(output_file, 'w') as f:
                json.dump(suggestions_content, f, indent=2)

            console.print(f"[green]Generated {len(generated_posts)} captions[/green]")

        except Exception as e:
            log(f"Error during content generation: {str(e)}", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

    elif args.command == 'schedule':
        log(f"Starting content scheduling for profile: {profile_name}", False, log_caller_file="suggestions.py")

        suggestions_file = get_latest_suggestions_file(profile_name)
        if not suggestions_file:
            log("No suggestions content found. Run 'generate' command first.", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        try:
            with open(suggestions_file, 'r') as f:
                suggestions_data = json.load(f)

            generated_posts = suggestions_data.get('generated_posts', [])
            if not generated_posts:
                log("No generated posts found in the file.", False, is_error=True, log_caller_file="suggestions.py")
                sys.exit(1)

            profile_props = PROFILES[profile_name].get('properties', {})
            verbose = profile_props.get('verbose', False)

            gap_type = profile_props.get('gap_type', 'random')
            min_gap_hours = profile_props.get('min_gap_hours', 0)
            min_gap_minutes = profile_props.get('min_gap_minutes', 1)
            max_gap_hours = profile_props.get('max_gap_hours', 0)
            max_gap_minutes = profile_props.get('max_gap_minutes', 50)
            fixed_gap_hours = profile_props.get('fixed_gap_hours', 2)
            fixed_gap_minutes = profile_props.get('fixed_gap_minutes', 0)

            gap_minutes_min = min_gap_hours * 60 + min_gap_minutes
            gap_minutes_max = max_gap_hours * 60 + max_gap_minutes
            fixed_gap_minutes = fixed_gap_hours * 60 + fixed_gap_minutes

            schedule_file = get_schedule_file_path(profile_name)
            os.makedirs(os.path.dirname(schedule_file), exist_ok=True)

            existing_schedule = []
            if os.path.exists(schedule_file):
                try:
                    with open(schedule_file, 'r') as f:
                        existing_schedule = json.load(f)
                except:
                    existing_schedule = []

            current_time = datetime.now()
            scheduled_posts = []

            for post in generated_posts:
                if not post.get('generated_caption', '').strip():
                    continue

                if gap_type == 'random':
                    gap_minutes = random.randint(gap_minutes_min, gap_minutes_max)
                else:
                    gap_minutes = fixed_gap_minutes

                scheduled_time = current_time + timedelta(minutes=gap_minutes)
                current_time = scheduled_time

                media_paths = post.get('downloaded_media_paths', [])
                media_paths = [path for path in media_paths if path is not None] if post.get('downloaded_media_paths') else []

                if media_paths:
                    project_root = os.getcwd()
                    media_paths = [os.path.relpath(path, project_root) if os.path.isabs(path) else path for path in media_paths]

                schedule_entry = {
                    "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "scheduled_tweet": post['generated_caption'],
                    "scheduled_image": media_paths,
                    "community_posted": False,
                    "community_posted_at": None,
                    "community-tweet": ""
                }

                scheduled_posts.append(schedule_entry)
                post['finalized'] = True

            if scheduled_posts:
                existing_schedule.extend(scheduled_posts)

                with open(schedule_file, 'w') as f:
                    json.dump(existing_schedule, f, indent=2)

                with open(suggestions_file, 'w') as f:
                    json.dump(suggestions_data, f, indent=2)

                console.print(f"[green]Scheduled {len(scheduled_posts)} posts to {schedule_file}[/green]")
                console.print(f"[yellow]Run 'socials x {profile_name} post process' to start posting[/yellow]")
            else:
                console.print("[yellow]No new posts to schedule[/yellow]")

        except Exception as e:
            log(f"Error during content scheduling: {str(e)}", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

    elif args.command == 'post':
        log(f"Starting content posting for profile: {profile_name}", False, log_caller_file="suggestions.py")

        schedule_file = get_schedule_file_path(profile_name)
        if not os.path.exists(schedule_file):
            log("No scheduled content found. Run 'schedule' command first.", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

        try:
            console.print(f"[blue]Posting scheduled suggestions for {profile_name}...[/blue]")
            console.print("This will post tweets from your schedule. Press Ctrl+C to stop.")

            profile_props = PROFILES[profile_name].get('properties', {})
            verbose = profile_props.get('verbose', False)
            headless = profile_props.get('headless', False)

            process_scheduled_tweets(profile_name, verbose=verbose, headless=headless)

            console.print(f"[green]Posting session completed for {profile_name}[/green]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Posting stopped by user[/yellow]")
        except Exception as e:
            log(f"Error during content posting: {str(e)}", False, is_error=True, log_caller_file="suggestions.py")
            sys.exit(1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()