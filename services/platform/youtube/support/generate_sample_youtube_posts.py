import random

from rich.console import Console
from datetime import datetime, timedelta
from services.support.logger_util import _log as log
from services.platform.youtube.support.save_youtube_schedules import save_youtube_schedules

console = Console()

def generate_sample_youtube_posts(scheduled_title_prefix="My Awesome Video", description="This is a video about awesome things.", tags="awesome,video,youtube", privacyStatus="private", start_video_number=1, num_days=1, profile_name="Default", start_date=None, fixed_gap_hours=0, fixed_gap_minutes=0, gap_minutes_min=1, gap_minutes_max=50, verbose: bool = False):
    log(f"Generating sample YouTube posts for profile: {profile_name}", verbose, log_caller_file="generate_sample_youtube_posts.py")
    
    scheduled_uploads = []
    current_time = datetime.now()
    if start_date:
        current_time = datetime.strptime(start_date, "%Y-%m-%d")

    for day in range(num_days):
        day_end_time = current_time + timedelta(days=1)
        while current_time < day_end_time:
            video_file_name = f"{start_video_number}.mp4"
            title = f"{scheduled_title_prefix} {start_video_number}"

            upload_item = {
                "file": video_file_name,
                "title": title,
                "description": description,
                "tags": tags,
                "privacyStatus": privacyStatus,
                "publishAt": current_time.isoformat() + "Z"
            }
            scheduled_uploads.append(upload_item)

            if fixed_gap_hours or fixed_gap_minutes:
                gap = timedelta(hours=fixed_gap_hours, minutes=fixed_gap_minutes)
            else:
                random_minutes = random.randint(gap_minutes_min, gap_minutes_max)
                gap = timedelta(minutes=random_minutes)
            
            current_time += gap
            start_video_number += 1

    save_youtube_schedules(scheduled_uploads, profile_name)
    log(f"Generated {len(scheduled_uploads)} sample YouTube posts.", verbose, log_caller_file="generate_sample_youtube_posts.py") 