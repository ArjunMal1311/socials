import os
import argparse

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.youtube.support.generate_sample_youtube_posts import generate_sample_youtube_posts
from services.platform.youtube.support.generate_youtube_titles import generate_titles_for_youtube_schedule
from services.platform.youtube.support.process_scheduled_youtube_uploads import process_scheduled_youtube_uploads

console = Console()

def main():
    parser = argparse.ArgumentParser(description="YouTube Scheduler CLI Tool")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output for debugging and monitoring. Shows comprehensive information about the execution process.")
    parser.add_argument("--process-youtube-uploads", action="store_true", help="Process and schedule YouTube uploads.")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample YouTube posts.")
    parser.add_argument("--video-title-prefix", type=str, default="My Awesome Video", help="Default title prefix for sample videos.")
    parser.add_argument("--video-description", type=str, default="This is a video about awesome things.", help="Default description for sample videos.")
    parser.add_argument("--video-tags", type=str, default="awesome,video,youtube", help="Default comma-separated tags for sample videos.")
    parser.add_argument("--video-privacy-status", type=str, default="private", choices=["public", "private", "unlisted"], help="Default privacy status for sample videos.")
    parser.add_argument("--start-video-number", type=int, default=1, help="Starting video number for sample posts.")
    parser.add_argument("--num-days", type=int, default=1, help="Number of days to schedule sample posts for.")
    parser.add_argument("--start-date", type=str, help="Start date for scheduling in YYYY-MM-DD format.")
    parser.add_argument("--gap-type", type=str, choices=["random", "fixed"], default="random", help="Type of gap for sample post generation.")
    parser.add_argument("--min-gap-hours", type=int, default=0, help="Minimum gap hours for random gap.")
    parser.add_argument("--min-gap-minutes", type=int, default=1, help="Minimum gap minutes for random gap.")
    parser.add_argument("--max-gap-hours", type=int, default=0, help="Maximum gap hours for random gap.")
    parser.add_argument("--max-gap-minutes", type=int, default=50, help="Maximum gap minutes for random gap.")
    parser.add_argument("--fixed-gap-hours", type=int, default=2, help="Fixed gap hours.")
    parser.add_argument("--fixed-gap-minutes", type=int, default=0, help="Fixed gap minutes.")
    parser.add_argument("--generate-titles", action="store_true", help="Generate Gemini titles for scheduled videos.")
    parser.add_argument("--gemini-api-key", type=str, help="Gemini API key for title generation.")
    parser.add_argument("--gemini-title-prompt", type=str, default="Generate a concise, engaging, and single YouTube video title based on the video content. Return only the title.", help="Prompt for Gemini title generation.")
    parser.add_argument("--gemini-tags-prompt", type=str, help="Prompt for Gemini tags generation.")
    parser.add_argument("--gemini-description-prompt", type=str, help="Prompt for Gemini description generation.")
    parser.add_argument("--no-headless", action="store_true", help="Disable headless browser mode for debugging and observation. The browser UI will be visible.")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", args.verbose, is_error=True, log_caller_file="scheduler.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", args.verbose, is_error=True, log_caller_file="scheduler.py")
        return

    if args.process_youtube_uploads:
        process_scheduled_youtube_uploads(args.profile, verbose=args.verbose)
        log("YouTube processing complete.", args.verbose, log_caller_file="scheduler.py")
    elif args.generate_sample:
        if args.gap_type == "random":
            gap_minutes_min = args.min_gap_hours * 60 + args.min_gap_minutes
            gap_minutes_max = args.max_gap_hours * 60 + args.max_gap_minutes
            if gap_minutes_min > gap_minutes_max:
                log("Minimum gap cannot be greater than maximum gap. Adjusting maximum to minimum.", args.verbose, log_caller_file="scheduler.py")
                gap_minutes_max = gap_minutes_min
            generate_sample_youtube_posts(scheduled_title_prefix=args.video_title_prefix, description=args.video_description, tags=args.video_tags, privacyStatus=args.video_privacy_status, start_video_number=args.start_video_number, num_days=args.num_days, profile_name=args.profile, start_date=args.start_date, gap_minutes_min=gap_minutes_min, gap_minutes_max=gap_minutes_max, verbose=args.verbose)
        else:
            generate_sample_youtube_posts(scheduled_title_prefix=args.video_title_prefix, description=args.video_description, tags=args.video_tags, privacyStatus=args.video_privacy_status, start_video_number=args.start_video_number, num_days=args.num_days, profile_name=args.profile, start_date=args.start_date, fixed_gap_hours=args.fixed_gap_hours, fixed_gap_minutes=args.fixed_gap_minutes, verbose=args.verbose)
        log("Sample YouTube posts generated and saved to youtube_schedule.json", args.verbose, log_caller_file="scheduler.py")
    elif args.generate_titles:
        gemini_api_key = args.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            log("Please provide a Gemini API key using --gemini-api-key argument or set GEMINI_API_KEY environment variable.", args.verbose, is_error=True, log_caller_file="scheduler.py")
        else:
            title_prompt = args.gemini_title_prompt or PROFILES[args.profile].get("youtube_title_prompt", "Generate a concise and engaging YouTube video title based on the video content. Return only the title.")
            tags_prompt = args.gemini_tags_prompt or PROFILES[args.profile].get("youtube_tags_prompt")
            description_prompt = args.gemini_description_prompt or PROFILES[args.profile].get("youtube_description_prompt")
            generate_titles_for_youtube_schedule(args.profile, gemini_api_key, title_prompt, tags_prompt, description_prompt, verbose=args.verbose)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
