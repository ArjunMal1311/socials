import os
import time

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Optional, Dict, Any
from googleapiclient.errors import HttpError
from services.platform.youtube.support.load_youtube_schedules import load_youtube_schedules
from services.platform.youtube.support.schedule_youtube_api import get_authenticated_service, initialize_upload

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

def process_scheduled_youtube_uploads(profile_name="Default", verbose: bool = False):
    _log(f"Processing scheduled YouTube uploads for profile: {profile_name}", verbose)

    scheduled_uploads = load_youtube_schedules(profile_name, verbose=verbose)

    if not scheduled_uploads:
        _log("No YouTube uploads scheduled yet.", verbose)
        return

    youtube_service = None
    try:
        with Status("[white]Authenticating with YouTube API...[/white]", spinner="dots", console=console) as status:
            youtube_service = get_authenticated_service(profile_name, verbose=verbose)
            _log("YouTube API authenticated.", verbose, status=status)
            time.sleep(0.5)

        schedule_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'schedule-videos', profile_name))
        with Status("[white]Scheduling YouTube uploads...[/white]", spinner="dots", console=console) as status:
            for upload_item in scheduled_uploads:
                _log(f"Attempting to upload video: {upload_item['title']}", verbose, status=status)

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
                    _log(f"Successfully scheduled YouTube upload for {upload_item['title']}", verbose, status=status)
                except HttpError as e:
                    error_message = f"❌ An HTTP error {e.resp.status} occurred: {e.content}"
                    _log(error_message, verbose, is_error=True, status=status)
                except Exception as e:
                    _log(f"An error occurred during YouTube upload: {e}", verbose, is_error=True, status=status)
                time.sleep(5)
        _log("All scheduled YouTube uploads processed!", verbose)

    except Exception as e:
        _log(f"An error occurred during YouTube processing: {e}", verbose, is_error=True)
    finally:
        pass
