import re
import random

from rich.status import Status
from rich.console import Console
from datetime import datetime, timedelta
from services.platform.x.support.save_tweet_schedules import save_tweet_schedules

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False):
    if is_error:
        if status:
            status.stop()
        log_message = message
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[generate_sample_posts.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[generate_sample_posts.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[generate_sample_posts.py] {timestamp}|[{color}]{message}[/{color}]")

def generate_sample_posts(gap_minutes_min=None, gap_minutes_max=None, fixed_gap_hours=None, fixed_gap_minutes=None, scheduled_tweet_text="This is a sample tweet!", start_image_number=1, profile_name="Default", num_days=1, start_date=None, verbose: bool = False):
    with Status("[white]Generating sample posts...[/white]", spinner="dots", console=console) as status:
        save_tweet_schedules([], profile_name)
        sample_posts = []
        image_index = start_image_number

        for day_offset in range(num_days):
            if start_date:
                base_date = datetime.strptime(start_date, "%Y-%m-%d")
                current_time = (base_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                current_time = (datetime.now() + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
            total_duration_minutes = 24 * 60
            elapsed_minutes = 0

            while elapsed_minutes < total_duration_minutes:
                if gap_minutes_min is not None and gap_minutes_max is not None:
                    gap = random.randint(gap_minutes_min, gap_minutes_max)
                    time_delta = timedelta(minutes=gap)
                elif fixed_gap_hours is not None and fixed_gap_minutes is not None:
                    time_delta = timedelta(hours=fixed_gap_hours, minutes=fixed_gap_minutes)
                else:
                    time_delta = timedelta(minutes=30)

                if (elapsed_minutes + (time_delta.total_seconds() // 60)) > total_duration_minutes:
                    break

                scheduled_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
                sample_posts.append({
                    "scheduled_time": scheduled_time_str,
                    "scheduled_tweet": scheduled_tweet_text,
                    "scheduled_image": f"{image_index}.png"
                })
                current_time += time_delta
                elapsed_minutes += (time_delta.total_seconds() // 60)
                image_index += 1
        save_tweet_schedules(sample_posts, profile_name)
        status.update(f"[white]Generated {len(sample_posts)} sample posts for profile '{profile_name}'.[/white]")
        _log(f"Generated {len(sample_posts)} sample posts for profile '{profile_name}'.", verbose)
