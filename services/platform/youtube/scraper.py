import os
import sys
import json
import argparse

from pathlib import Path
from datetime import datetime
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.support.path_config import get_youtube_profile_dir
from services.platform.youtube.support.scraper_utils import run_youtube_scraper
from services.platform.youtube.support.caption_downloader import download_captions_for_videos
from services.platform.youtube.support.video_downloader import download_videos_for_youtube_scraper
from services.platform.youtube.support.get_latest_dated_json_file import get_latest_dated_json_file
from services.platform.youtube.support.file_manager import clear_youtube_files, clean_and_sort_videos
from services.platform.youtube.support.content_analyzer import analyze_video_content_with_gemini, suggest_best_content_with_gemini

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="YouTube Scraper CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use. Scraped data will be saved to youtube/{profile}.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--scrape", action="store_true", help="Activate YouTube scraping mode.")
    parser.add_argument("--download-captions", action="store_true", help="Download captions for scraped videos.")
    parser.add_argument("--caption-method", type=str, choices=["api", "selenium", "transcript_api"], default="transcript_api", help="Method to download captions: 'api', 'selenium', or 'transcript_api' (default: transcript_api).")
    parser.add_argument("--download-videos", action="store_true", help="Download videos for scraped videos using yt-dlp.")
    parser.add_argument("--clear", action="store_true", help="Clear all generated files for the profile (videos, captions, json files).")
    parser.add_argument("--clean", action="store_true", help="Remove videos with no views and sort by view count in descending order.")
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    parser.add_argument("--suggest-content", action="store_true", help="Analyze cleaned videos with Gemini to suggest the best content ideas for your channel based on scraped data.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    profile_name = args.profile
    profile_config = PROFILES.get(profile_name, {})
    youtube_scraper_config = profile_config.get("youtube_scraper", {})

    if args.scrape:
        search_query = youtube_scraper_config.get("search_query")
        max_videos = youtube_scraper_config.get("max_videos", 50)
        time_filter = youtube_scraper_config.get("time_filter", "")
        max_duration_minutes = youtube_scraper_config.get("max_duration_minutes")

        weekly_filter = (time_filter == "weekly")
        today_filter = (time_filter == "daily")

        if weekly_filter and today_filter:
            log("Cannot use --weekly and --today simultaneously. Please choose one.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Running YouTube Scraper for profile '{profile_name}' Searching for '{search_query}' (max {max_videos} videos)...[/white]" if search_query else f"[white]Running YouTube Scraper for profile '{profile_name}' Scraping trending videos (max {max_videos} videos)...[/white]", spinner="dots", console=console) as status:
            results = run_youtube_scraper(profile_name, search_query, max_videos, weekly_filter=weekly_filter, today_filter=today_filter, status=status, verbose=args.verbose, headless=not args.no_headless)
            status.stop()
            log(f"YouTube Scraper finished. Scraped {len(results)} videos.", args.verbose, log_caller_file="scraper.py")
            if results:
                sample = results[0]
                log("Sample:", args.verbose, log_caller_file="scraper.py")
                log(f"  Title: {sample.get('title', '')[:70]}...", args.verbose, log_caller_file="scraper.py")
                log(f"  URL: {sample.get('url', '')}", args.verbose, log_caller_file="scraper.py")
                log(f"  Views: {sample.get('views', '')}", args.verbose, log_caller_file="scraper.py")
                log(f"  Channel: {sample.get('channel_name', '')}", args.verbose, log_caller_file="scraper.py")

            scraped_videos = results

            if args.download_captions and scraped_videos:
                with Status(f"[white]Downloading captions for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as captions_status:
                    scraped_videos = download_captions_for_videos(profile_name, scraped_videos, verbose=args.verbose, headless=not args.no_headless, caption_method=args.caption_method)
                    captions_status.stop()
                    log(f"Caption download complete. Videos with captions: {sum(1 for v in scraped_videos if v.get('caption_filepath'))}", args.verbose, log_caller_file="scraper.py")
                
            if args.download_videos and scraped_videos:
                with Status(f"[white]Downloading videos for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as videos_status:
                    scraped_videos = download_videos_for_youtube_scraper(profile_name, scraped_videos, verbose=args.verbose)
                    videos_status.stop()
                    log(f"Video download complete. Videos with files: {sum(1 for v in scraped_videos if v.get('video_filepath'))}", args.verbose, log_caller_file="scraper.py")

            if (args.download_captions or args.download_videos) and scraped_videos:
                updated_videos_for_analysis = []
                processed_count = 0
                
                with Status(f"[white]Analyzing content for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as analysis_status:
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {}
                        for video_data in scraped_videos:
                            video_id = video_data.get('video_id')
                            video_title = video_data.get('title', 'Unknown Title')
                            video_file_path = video_data.get('video_filepath') 
                            caption_file_content = None

                            if video_file_path and os.path.exists(video_file_path):
                                futures[executor.submit(analyze_video_content_with_gemini, video_file_path, profile_name, analysis_status, args.api_key, verbose=args.verbose)] = video_data
                            elif video_data.get('caption_filepath') and os.path.exists(video_data['caption_filepath']):
                                try:
                                    with open(video_data['caption_filepath'], 'r', encoding='utf-8') as f:
                                        caption_file_content = f.read()
                                    video_data['summarized_content'] = "N/A"
                                    video_data['subtitles'] = caption_file_content
                                    updated_videos_for_analysis.append(video_data)
                                    processed_count += 1
                                    analysis_status.update(f"[white]Processed {processed_count}/{len(scraped_videos)} videos (from captions only)...[/white]")
                                    log(f"Loaded captions for {video_title} from {video_data['caption_filepath']}", args.verbose, log_caller_file="scraper.py")
                                except Exception as e:
                                    log(f"Error reading caption file {video_data['caption_filepath']}: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")
                                    video_data['summarized_content'] = "Error: N/A"
                                    video_data['subtitles'] = "Error: N/A"
                                    updated_videos_for_analysis.append(video_data)
                                    processed_count += 1
                                    analysis_status.update(f"[white]Processed {processed_count}/{len(scraped_videos)} videos (caption read failed)...[/white]")
                            else:
                                log(f"No video file or caption file found for '{video_title}' ({video_id}). Skipping content analysis.", args.verbose, log_caller_file="scraper.py")
                                video_data['summarized_content'] = "N/A"
                                video_data['subtitles'] = "N/A"
                                updated_videos_for_analysis.append(video_data)
                                processed_count += 1
                                analysis_status.update(f"[white]Processed {processed_count}/{len(scraped_videos)} videos (no media found)...[/white]")

                        for future in futures:
                            video_data_from_future = futures[future]
                            video_title = video_data_from_future.get('title', 'Unknown Title')

                            try:
                                summary, transcript = future.result()
                                video_data_from_future['summarized_content'] = summary or "Analysis failed."
                                video_data_from_future['subtitles'] = transcript or "Transcription failed."
                                log(f"Successfully analyzed content for: {video_title}", args.verbose, log_caller_file="scraper.py")
                            except Exception as e:
                                log(f"Error analyzing content for {video_title}: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")
                                video_data_from_future['summarized_content'] = f"Error: {e}"
                                video_data_from_future['subtitles'] = f"Error: {e}"

                            updated_videos_for_analysis.append(video_data_from_future)
                            processed_count += 1
                            analysis_status.update(f"[white]Processed {processed_count}/{len(scraped_videos)} videos...[/white]")

                scraped_videos = updated_videos_for_analysis
                analysis_status.stop()
                log("Content analysis for scraped videos complete.", args.verbose, log_caller_file="scraper.py")

            try:
                output_dir = get_youtube_profile_dir(profile_name)
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(output_dir, f"videos_{timestamp}.json")

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(scraped_videos, f, indent=2, ensure_ascii=False)
                log(f"Enriched video data saved to {output_file}", args.verbose, log_caller_file="scraper.py")
            except Exception as e:
                log(f"Error saving enriched video data: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")

    elif args.download_captions:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if youtube_scraper_config.get("time_filter") == "weekly":
            json_filename_prefix = "videos_weekly"
        elif youtube_scraper_config.get("time_filter") == "daily":
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            log(f"No scraped videos found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            log(f"Error loading scraped videos from {videos_json_path}: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Downloading captions for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            updated_videos = download_captions_for_videos(profile_name, scraped_videos, verbose=args.verbose, headless=not args.no_headless, caption_method=args.caption_method)
            status.stop()
            log(f"Caption download complete. Success: {sum(1 for v in updated_videos if v.get('caption_filepath'))} videos updated.", args.verbose, log_caller_file="scraper.py")

        try:
            with open(videos_json_path, 'w', encoding='utf-8') as f:
                json.dump(updated_videos, f, indent=2, ensure_ascii=False)
            log(f"Updated video data with caption file paths saved to {videos_json_path}", args.verbose, log_caller_file="scraper.py")
        except Exception as e:
            log(f"Error saving updated video data with caption file paths: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")

    elif args.download_videos:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if youtube_scraper_config.get("time_filter") == "weekly":
            json_filename_prefix = "videos_weekly"
        elif youtube_scraper_config.get("time_filter") == "daily":
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            log(f"No scraped videos found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            log(f"Error loading scraped videos from {videos_json_path}: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Downloading videos for {len(scraped_videos)} videos for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            updated_videos = download_videos_for_youtube_scraper(profile_name, scraped_videos, verbose=args.verbose)
            status.stop()
            log(f"Video download complete. Videos with files: {sum(1 for v in updated_videos if v.get('video_filepath'))} videos updated.", args.verbose, log_caller_file="scraper.py")
        
        try:
            with open(videos_json_path, 'w', encoding='utf-8') as f:
                json.dump(updated_videos, f, indent=2, ensure_ascii=False)
            log(f"Updated video data with video file paths saved to {videos_json_path}", args.verbose, log_caller_file="scraper.py")
        except Exception as e:
            log(f"Error saving updated video data with video file paths: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")

    elif args.clean:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if youtube_scraper_config.get("time_filter") == "weekly":
            json_filename_prefix = "videos_weekly"
        elif youtube_scraper_config.get("time_filter") == "daily":
            json_filename_prefix = "videos_daily"

        with Status(f"[white]Cleaning and sorting videos for profile '{profile_name}' ({json_filename_prefix})...[/white]", spinner="dots", console=console) as status:
            clean_and_sort_videos(profile_name, json_filename_prefix, weekly_filter=youtube_scraper_config.get("time_filter") == "weekly", today_filter=youtube_scraper_config.get("time_filter") == "daily", max_duration_minutes=youtube_scraper_config.get("max_duration_minutes"), status=status, verbose=args.verbose)
            status.stop()
            log(f"Video cleaning and sorting complete for profile '{profile_name}'.", args.verbose, log_caller_file="scraper.py")

    elif args.clear:
        profile_name = args.profile
        with Status(f"[white]Clearing all YouTube-related files for profile '{profile_name}'[/white]", spinner="dots", console=console) as status:
            clear_youtube_files(profile_name, status=status, verbose=args.verbose)
            status.stop()
            log(f"All YouTube files for profile '{profile_name}' cleared.", args.verbose, log_caller_file="scraper.py")

    elif args.suggest_content:
        profile_name = args.profile
        json_filename_prefix = "videos"
        if youtube_scraper_config.get("time_filter") == "weekly":
            json_filename_prefix = "videos_weekly"
        elif youtube_scraper_config.get("time_filter") == "daily":
            json_filename_prefix = "videos_daily"

        videos_json_path = get_latest_dated_json_file(profile_name, json_filename_prefix, verbose=args.verbose)

        if not videos_json_path:
            log(f"No video data found for profile '{profile_name}' with prefix '{json_filename_prefix}'. Please run --scrape first.", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        
        try:
            with open(videos_json_path, 'r', encoding='utf-8') as f:
                scraped_videos = json.load(f)
        except Exception as e:
            log(f"Error loading video data from {videos_json_path}: {e}", args.verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)
        
        if not scraped_videos:
            log("No videos found in the selected JSON file. Cannot suggest content.", args.verbose, log_caller_file="scraper.py")
            sys.exit(0)

        with Status(f"[white]Generating content suggestions for profile '{profile_name}' from {len(scraped_videos)} videos...[/white]", spinner="dots", console=console) as status:
            suggestions = suggest_best_content_with_gemini(scraped_videos, profile_name, api_key=args.api_key, status=status, verbose=args.verbose)
            status.stop()
            
            if suggestions:
                console.print("\n[bold green]--- Content Suggestions ---[/bold green]")
                console.print(suggestions)
                console.print("[bold green]---------------------------[/bold green]")
            else:
                log("Failed to generate content suggestions.", args.verbose, is_error=True, log_caller_file="scraper.py")

    else:
        parser.print_help()

if __name__ == "__main__":
    main() 