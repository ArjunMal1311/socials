import os
import re
import json

from rich.status import Status
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.gemini_util import generate_gemini
from services.support.path_config import get_youtube_schedule_videos_dir
from services.platform.youtube.support.save_youtube_schedules import save_youtube_schedules

console = Console()

def generate_titles_for_youtube_schedule(profile_name, api_key, title_prompt, tags_prompt=None, description_prompt=None, verbose: bool = False):
    log(f"[Gemini Analysis] Starting title generation for profile: {profile_name}", verbose, log_caller_file="generate_youtube_titles.py")
    
    schedule_file_path = os.path.join(get_youtube_schedule_videos_dir(profile_name), 'youtube_schedule.json')
    if not os.path.exists(schedule_file_path):
        log(f"Schedule file not found at {schedule_file_path}.", verbose, log_caller_file="generate_youtube_titles.py")
        return

    with open(schedule_file_path, "r") as f:
        schedules = json.load(f)
    
    schedule_folder = get_youtube_schedule_videos_dir(profile_name)
    
    with Status("[white]Generating titles...[/white]", spinner="dots", console=console) as status:
        for i, video_item in enumerate(schedules):
            media_file = video_item.get("file")
            status.update(f"[white][Gemini Analysis] Processing item {i+1}/{len(schedules)}: Media file = {media_file}[/white]")
            if not media_file:
                status.update(f"[white][Gemini Analysis] Skipping item {i+1}: No media file specified.[/white]")
                continue
            
            media_path = os.path.join(schedule_folder, media_file)
            if not os.path.exists(media_path):
                status.update(f"[white][Gemini Analysis] Skipping item {i+1}: Local media file not found: {media_path}[/white]")
                continue
            
            try:
                status.update(f"[white][Gemini Analysis] Calling Gemini for title generation on {media_file}...[/white]")
                raw_title = generate_gemini(media_path, api_key, title_prompt, status=status, verbose=verbose)
                clean_title = raw_title.split('\n')[0].strip()
                if '**' in clean_title:
                    clean_title = clean_title.replace('**', '')
                if '*' in clean_title:
                    clean_title = clean_title.replace('*', '')
                if '"' in clean_title:
                    clean_title = clean_title.replace('"', '')
                video_item["title"] = clean_title
                status.update(f"[white][Gemini Analysis] Successfully generated title for {media_file}: '{clean_title}'[/white]")

                effective_tags_prompt = tags_prompt or "Generate 4 concise, SEO-friendly YouTube tags for this video's content as a single comma-separated line without hashtags or extra text. Return only the tags."
                status.update(f"[white][Gemini Analysis] Calling Gemini for tags generation on {media_file}...[/white]")
                raw_tags = generate_gemini(media_path, api_key, effective_tags_prompt, status=status, verbose=verbose)
                text = raw_tags.strip()
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                candidate = lines[0] if lines else text
                if ":" in candidate:
                    candidate = candidate.split(":")[-1]
                if "," in candidate:
                    parts = [p.strip() for p in candidate.split(",")]
                else:
                    cleaned_lines = []
                    for l in lines:
                        l = re.sub(r'^[\-\*\d\.)\s#]+', '', l).strip()
                        if l:
                            cleaned_lines.append(l)
                    parts = cleaned_lines
                parts = [p.replace('#', '').replace('"', '').strip(" -•*'`").strip() for p in parts]
                parts = [p for p in parts if p]
                seen = set()
                unique_parts = []
                for p in parts:
                    if p.lower() not in seen:
                        seen.add(p.lower())
                        unique_parts.append(p)
                clean_tags = ",".join(unique_parts)
                video_item["tags"] = clean_tags
                status.update(f"[white][Gemini Analysis] Tags generated for {media_file}[/white]")

                if description_prompt:
                    status.update(f"[white][Gemini Analysis] Calling Gemini for description generation on {media_file}...[/white]")
                    raw_desc = generate_gemini(media_path, api_key, description_prompt, status=status, verbose=verbose)
                    desc_text = raw_desc.strip()
                    desc_lines = [re.sub(r'^[\-\*\d\.)\s#]+', '', l).strip() for l in desc_text.splitlines() if l.strip()]
                    clean_desc = re.sub(r'\s+', ' ', ' '.join(desc_lines)).strip()
                    clean_desc = clean_desc.replace('"', '')
                    video_item["description"] = clean_desc
                    status.update(f"[white][Gemini Analysis] Description generated for {media_file}[/white]")
            except Exception as e:
                status.update(f"[white]Failed to generate title/tags for {media_file}: {e}[/white]")
        
        save_youtube_schedules(schedules, profile_name)
        status.update("[white][Gemini Analysis] All titles and tags processed and youtube_schedule.json updated.[/white]")
    log("[Gemini Analysis] All titles and tags processed and youtube_schedule.json updated.", verbose, log_caller_file="generate_youtube_titles.py") 