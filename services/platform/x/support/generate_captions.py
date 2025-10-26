import re
import os
import json

from profiles import PROFILES
from datetime import datetime

from rich.status import Status
from rich.console import Console
from services.support.gemini_util import generate_gemini
from services.support.path_config import get_schedule_file_path

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
        console.print(f"[generate_captions.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[generate_captions.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[generate_captions.py] {timestamp}|[{color}]{message}[/{color}]")

def generate_captions_for_schedule(profile_name, api_key, verbose: bool = False):
    _log(f"[Gemini Analysis] Starting caption generation for profile: {profile_name}", verbose)
    
    schedule_file_path = get_schedule_file_path(profile_name)
    if not os.path.exists(schedule_file_path):
        _log(f"Schedule file not found at {schedule_file_path}.", verbose, status=status, is_error=True)
        return

    with open(schedule_file_path, "r") as f:
        schedules = json.load(f)
    
    schedule_folder = os.path.dirname(schedule_file_path)
    
    with Status("[white]Generating captions...[/white]", spinner="dots", console=console) as status:
        for i, tweet in enumerate(schedules):
            media_file = tweet.get("scheduled_image")
            status.update(f"[white][Gemini Analysis] Processing item {i+1}/{len(schedules)}: Media file = {media_file}[/white]")
            if not media_file:
                status.update(f"[white][Gemini Analysis] Skipping item {i+1}: No media file specified.[/white]")
                continue
            
            media_path = os.path.join(schedule_folder, media_file)
            if not os.path.exists(media_path):
                status.update(f"[white][Gemini Analysis] Skipping item {i+1}: Local media file not found: {media_path}[/white]")
                continue

            _log(f"[DEBUG] Processing media file: {media_file}", verbose, status) 
            ext = os.path.splitext(media_file)[1].lower()
            try:
                if ext in [".png", ".jpg", ".jpeg"]:
                    status.update(f"[white][Gemini Analysis] Calling Gemini for image captioning on {media_file}...[/white]")
                    caption = generate_gemini(media_path, api_key, PROFILES[profile_name].get("prompt", "Generate a short, engaging social media caption."), model_name='gemini-2.0-flash-lite')
                elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                    status.update(f"[white][Gemini Analysis] Calling Gemini for video captioning on {media_file}...[/white]")
                    caption = generate_gemini(media_path, api_key, PROFILES[profile_name].get("prompt", "Generate a short, engaging social media caption."), model_name='gemini-2.0-flash-lite')
                else:
                    status.update(f"[white][Gemini Analysis] Skipping item {i+1}: Unsupported media extension '{ext}' for file {media_file}.[/white]")
                    continue

                if profile_name == "akg":
                    username_match = re.search(r'\d+_([a-zA-Z0-9]+)\.', media_file)
                    _log(f"[DEBUG] Regex match object: {username_match}", verbose, status) 
                    if username_match:
                        username = username_match.group(1)
                        _log(f"[DEBUG] Extracted username: {username}", verbose, status) 
                        caption_before = caption
                        caption += f"\n\n@{username}"
                        _log(f"[DEBUG] Caption before: {caption_before}, Caption after: {caption}", verbose, status) 
                        status.update(f"[white][Gemini Analysis] Appended @{username} to caption.[/white]")
                
                tweet["scheduled_tweet"] = caption
                status.update(f"[white][Gemini Analysis] Successfully captioned {media_file} with: '{caption}'[/white]")
            except Exception as e:
                status.update(f"[white]Failed to caption {media_file}: {e}[/white]")
            with open(schedule_file_path, "w") as f:
                json.dump(schedules, f, indent=2)
            status.update("[white][Gemini Analysis] Schedule file updated.[/white]")

        status.update("[white][Gemini Analysis] All captions processed and schedule.json updated.[/white]") 