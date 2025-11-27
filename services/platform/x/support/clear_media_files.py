import os
import json

from rich.status import Status
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_schedule_file_path, ensure_dir_exists

console = Console()

def clear_media(profile_name, verbose: bool = False):
    log(f"Clearing media files for profile: {profile_name}", verbose, log_caller_file="clear_media_files.py")
    schedule_json_path = get_schedule_file_path(profile_name)
    schedule_folder = os.path.dirname(schedule_json_path)
    
    ensure_dir_exists(schedule_folder)
        
    try:
        with open(schedule_json_path, 'w') as f:
            json.dump([], f)
        log(f"Cleared schedule file: {schedule_json_path}", verbose, log_caller_file="clear_media_files.py")
    except Exception as e:
        log(f"Error clearing schedule file {schedule_json_path}: {e}", verbose, is_error=True, log_caller_file="clear_media_files.py")

    deleted_count = 0
    with Status("[white]Deleting media files...[/white]", spinner="dots", console=console) as status:
        for filename in os.listdir(schedule_folder):
            file_path = os.path.join(schedule_folder, filename)
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in [".mp4", ".png", ".jpg", ".jpeg"]:
                    try:
                        os.remove(file_path)
                        log(f"Deleted: {filename}", verbose, status, log_caller_file="clear_media_files.py")
                        deleted_count += 1
                    except Exception as e:
                        log(f"Error deleting {filename}: {e}", verbose, status, is_error=True, log_caller_file="clear_media_files.py")
    log(f"Cleaned up {deleted_count} media files in {schedule_folder}.", verbose, log_caller_file="clear_media_files.py") 