import os
import sys
import json
import argparse

from datetime import datetime
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from services.platform.youtube.support.scraper_utils import run_youtube_scraper
from services.platform.youtube.support.caption_downloader import download_captions_for_videos
from services.platform.youtube.support.video_downloader import download_videos_for_youtube_scraper
from services.platform.youtube.support.get_latest_dated_json_file import get_latest_dated_json_file
from services.platform.youtube.support.file_manager import clear_youtube_files, clean_and_sort_videos
from services.platform.youtube.support.content_analyzer import analyze_video_content_with_gemini, suggest_best_content_with_gemini

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
    
    console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="YouTube Scraper CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use. Scraped data will be saved to youtube/{profile}.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--search-query", type=str, help="Optional: Search query for YouTube videos. If not provided, trending videos will be scraped.")
    parser.add_argument("--max-videos", type=int, default=50, help="Maximum number of videos to scrape (default: 50).")
    parser.add_argument("--scrape", action="store_true", help="Activate YouTube scraping mode.")
    parser.add_argument("--download-captions", action="store_true", help="Download captions for scraped videos.")
    parser.add_argument("--download-videos", action="store_true", help="Download videos for scraped videos using yt-dlp.")
    parser.add_argument("--content-suggestion", action="store_true", help="Analyze downloaded videos with Gemini to get summarized content and subtitles.")
    parser.add_argument("--weekly", action="store_true", help="Filter search results for videos published this week.")
    parser.add_argument("--today", action="store_true", help="Filter search results for videos published today.")
    parser.add_argument("--max-duration-minutes", type=int, default=None, help="Optional: Maximum video duration in minutes for cleaning (e.g., --max-duration-minutes 30). Videos longer than this will be removed.")
    parser.add_argument("--clear", action="store_true", help="Clear all generated files for the profile (videos, captions, json files).")
    parser.add_argument("--clean", action="store_true", help="Remove videos with no views and sort by view count in descending order.")
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    parser.add_argument("--suggest-content", action="store_true", help="Analyze cleaned videos with Gemini to suggest the best content ideas for your channel based on scraped data.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    if args.scrape:
        profile_name = args.profile
        search_query = args.search_query
        max_videos = args.max_videos
        weekly_filter = args.weekly
        today_filter = args.today

        if weekly_filter and today_filter:
            _log("Cannot use --weekly and --today simultaneously. Please choose one.", args.verbose, is_error=True)
            sys.exit(1)

        with Status(f"[white]Running YouTube Scraper for profile '{profile_name}' Searching for '{search_query}' (max {max_videos} videos)...[/white]" if search_query else f"[white]Running YouTube Scraper for profile '{profile_name}' Scraping trending videos (max {max_videos} videos)...[/white]", spinner="dots", console=console) as status:
            results = run_youtube_scraper(profile_name, search_query, max_videos, weekly_filter=weekly_filter, today_filter=today_filter, status=status, verbose=args.verbose, headless=not args.no_headless)
            status.stop()
            _log(f"YouTube Scraper finished. Scraped {len(results)} videos.", args.verbose)
            if results:
                sample = results[0]
                _log("Sample:", args.verbose)
                _log(f"  Title: {sample.get('title', '')[:70]}...", args.verbose)
                _log(f"  URL: {sample.get('url', '')}", args.verbose)
                _log(f"  Views: {sample.get('views', '')}", args.verbose)
                _log(f"  Channel: {sample.get('channel_name', '')}", args.verbose)

    elif args.download_captions:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if args.weekly:
            json_filename_prefix = "videos_weekly"
        elif args.today:
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            _log(f"No scraped videos found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True)
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            _log(f"Error loading scraped videos from {videos_json_path}: {e}", args.verbose, is_error=True)
            sys.exit(1)

        with Status(f"[white]Downloading captions for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            results = download_captions_for_videos(profile_name, scraped_videos, verbose=args.verbose, headless=not args.no_headless)
            status.stop()
            _log(f"Caption download complete. Success: {len(results['success'])}, Failed: {len(results['failed'])}", args.verbose)

    elif args.download_videos:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if args.weekly:
            json_filename_prefix = "videos_weekly"
        elif args.today:
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            _log(f"No scraped videos found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True)
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            _log(f"Error loading scraped videos from {videos_json_path}: {e}", args.verbose, is_error=True)
            sys.exit(1)

        with Status(f"[white]Downloading videos for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            results = download_videos_for_youtube_scraper(profile_name, scraped_videos, verbose=args.verbose)
            status.stop()
            _log(f"Video download complete. Success: {len(results['success'])}, Failed: {len(results['failed'])}", args.verbose)

    elif args.content_suggestion:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if args.weekly:
            json_filename_prefix = "videos_weekly"
        elif args.today:
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)
        videos_download_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'youtube', profile_name, 'videos'))

        if not videos_json_path:
            _log(f"No scraped videos found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True)
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            _log(f"Error loading scraped videos from {videos_json_path}: {e}", args.verbose, is_error=True)
            sys.exit(1)

        updated_videos = []
        processed_count = 0
        
        with Status(f"[white]Analyzing content for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {}
                for video_data in scraped_videos:
                    video_id = video_data.get('video_id')
                    video_title = video_data.get('title', 'Unknown Title')
                    video_file_path = None
                    if video_id:
                        for fname in os.listdir(videos_download_dir):
                            if fname.startswith(video_id) and any(fname.endswith(ext) for ext in ['.mp4', '.webm', '.mkv', '.avi']):
                                video_file_path = os.path.join(videos_download_dir, fname)
                                break
                    
                    if not video_file_path or not os.path.exists(video_file_path):
                        _log(f"Video file not found for '{video_title}' ({video_id}). Skipping content analysis. Expected in: {videos_download_dir}", args.verbose)
                        video_data['summarized_content'] = "N/A"
                        video_data['subtitles'] = "N/A"
                        updated_videos.append(video_data)
                        continue

                    futures[executor.submit(analyze_video_content_with_gemini, video_file_path, profile_name, status, args.api_key, verbose=args.verbose)] = video_data
                
                for future in futures:
                    video_data = futures[future]
                    video_title = video_data.get('title', 'Unknown Title')
                    video_id = video_data.get('video_id')
                    
                    try:
                        summary, transcript = future.result() 
                        video_data['summarized_content'] = summary or "Analysis failed."
                        video_data['subtitles'] = transcript or "Transcription failed."
                        _log(f"Successfully analyzed content for: {video_title}", args.verbose)
                    except Exception as e:
                        _log(f"Error analyzing content for {video_title}: {e}", args.verbose, is_error=True)
                        video_data['summarized_content'] = f"Error: {e}"
                        video_data['subtitles'] = f"Error: {e}"
                    
                    updated_videos.append(video_data)
                    processed_count += 1
                    status.update(f"[white]Processed {processed_count}/{len(scraped_videos)} videos...[/white]")

            try:
                with open(videos_json_path, 'w', encoding='utf-8') as f:
                    json.dump(updated_videos, f, indent=2, ensure_ascii=False)
                _log(f"Updated video data with content suggestions saved to {videos_json_path}", args.verbose)
            except Exception as e:
                _log(f"Error saving updated video data: {e}", args.verbose, is_error=True)

        status.stop()
        _log("Content suggestion process complete.", args.verbose)

    elif args.clean:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if args.weekly:
            json_filename_prefix = "videos_weekly"
        elif args.today:
            json_filename_prefix = "videos_daily"

        with Status(f"[white]Cleaning and sorting videos for profile '{profile_name}' ({json_filename_prefix})...[/white]", spinner="dots", console=console) as status:
            clean_and_sort_videos(profile_name, json_filename_prefix, weekly_filter=args.weekly, today_filter=args.today, max_duration_minutes=args.max_duration_minutes, status=status, verbose=args.verbose)
            status.stop()
            _log(f"Video cleaning and sorting complete for profile '{profile_name}'.", args.verbose)

    elif args.clear:
        profile_name = args.profile
        with Status(f"[white]Clearing all YouTube-related files for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            clear_youtube_files(profile_name, status=status, verbose=args.verbose)
            status.stop()
            _log(f"All YouTube files for profile '{profile_name}' cleared.", args.verbose)

    elif args.suggest_content:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if args.weekly:
            json_filename_prefix = "videos_weekly"
        elif args.today:
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            _log(f"No video data found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape and --content-suggestion first.", args.verbose, is_error=True)
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            _log(f"Error loading video data from {videos_json_path}: {e}", args.verbose, is_error=True)
            sys.exit(1)
        
        if not scraped_videos:
            _log("No videos found in the selected JSON file. Cannot suggest content.", args.verbose)
            sys.exit(0)

        with Status(f"[white]Generating content suggestions for profile '{profile_name}' from {len(scraped_videos)} videos...[/white]", spinner="dots", console=console) as status:
            suggestions = suggest_best_content_with_gemini(scraped_videos, profile_name, api_key=args.api_key, status=status, verbose=args.verbose)
            status.stop()
            
            if suggestions:
                console.print("\n[bold green]--- Content Suggestions ---[/bold green]")
                console.print(suggestions)
                console.print("[bold green]---------------------------[/bold green]")
            else:
                _log("Failed to generate content suggestions.", args.verbose, is_error=True)

    else:
        parser.print_help()

if __name__ == "__main__":
    main() 