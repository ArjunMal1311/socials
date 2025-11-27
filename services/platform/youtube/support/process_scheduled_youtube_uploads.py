import os
import time

from rich.status import Status
from rich.console import Console
from googleapiclient.errors import HttpError
from services.support.logger_util import _log as log
from services.support.path_config import get_youtube_schedule_videos_dir
from services.platform.youtube.support.load_youtube_schedules import load_youtube_schedules
from services.platform.youtube.support.schedule_youtube_api import get_authenticated_service, initialize_upload

console = Console()

def process_scheduled_youtube_uploads(profile_name="Default", verbose: bool = False):
    log(f"Processing scheduled YouTube uploads for profile: {profile_name}", verbose, log_caller_file="process_scheduled_youtube_uploads.py")

    scheduled_uploads = load_youtube_schedules(profile_name, verbose=verbose)

    if not scheduled_uploads:
        log("No YouTube uploads scheduled yet.", verbose, log_caller_file="process_scheduled_youtube_uploads.py")
        return

    youtube_service = None
    try:
        with Status("[white]Authenticating with YouTube API...[/white]", spinner="dots", console=console) as status:
            youtube_service = get_authenticated_service(profile_name, verbose=verbose)
            log("YouTube API authenticated.", verbose, status=status, log_caller_file="process_scheduled_youtube_uploads.py")
            time.sleep(0.5)

        schedule_folder = get_youtube_schedule_videos_dir(profile_name)
        with Status("[white]Scheduling YouTube uploads...[/white]", spinner="dots", console=console) as status:
            for upload_item in scheduled_uploads:
                log(f"Attempting to upload video: {upload_item['title']}", verbose, status=status, log_caller_file="process_scheduled_youtube_uploads.py")

                class Options:
                    def __init__(self, data):
                        for key, value in data.items():
                            setattr(self, key, value)
                file_value = upload_item.get("file")
                if file_value and not os.path.isabs(file_value):
                    file_value = os.path.join(schedule_folder, file_value)
                options = Options({**upload_item, "file": file_value})

                try:
                    initialize_upload(youtube_service, options, status, verbose=verbose)
                    log(f"Successfully scheduled YouTube upload for {upload_item['title']}", verbose, status=status, log_caller_file="process_scheduled_youtube_uploads.py")
                except HttpError as e:
                    error_message = f"An HTTP error {e.resp.status} occurred: {e.content}"
                    log(error_message, verbose, is_error=True, status=status, log_caller_file="process_scheduled_youtube_uploads.py")
                except Exception as e:
                    log(f"An error occurred during YouTube upload: {e}", verbose, is_error=True, status=status, log_caller_file="process_scheduled_youtube_uploads.py")
                time.sleep(5)
        log("All scheduled YouTube uploads processed!", verbose, log_caller_file="process_scheduled_youtube_uploads.py")

    except Exception as e:
        log(f"An error occurred during YouTube processing: {e}", verbose, is_error=True, log_caller_file="process_scheduled_youtube_uploads.py")
    finally:
        pass
