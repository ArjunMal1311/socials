import os
import json
import time

from rich.status import Status
from rich.console import Console
from typing import List, Dict, Any

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.gemini_util import generate_gemini
from services.support.api_call_tracker import APICallTracker
from services.support.storage.base_storage import BaseStorage
from services.support.path_config import get_platform_profile_dir, get_base_dir

from services.platform.instagram.support.video_utils import download_instagram_videos

console = Console()

def load_all_posts(profile_name: str) -> List[Dict[str, Any]]:
    base_dir = get_platform_profile_dir("instagram", profile_name)
    posts_file = os.path.join(base_dir, "profiles", "posts.json")
    
    if os.path.exists(posts_file):
        with open(posts_file, 'r') as f:
            return json.load(f)
    return []

def load_learnings(profile_name: str) -> List[Dict[str, Any]]:
    learning_dir = os.path.join(get_base_dir(), "learning", "instagram", profile_name)
    os.makedirs(learning_dir, exist_ok=True)
    
    learnings_file = os.path.join(learning_dir, "learnings.json")
    
    if os.path.exists(learnings_file):
        try:
            with open(learnings_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_learnings(profile_name: str, learnings: List[Dict[str, Any]]):
    learning_dir = os.path.join(get_base_dir(), "learning", "instagram", profile_name)
    os.makedirs(learning_dir, exist_ok=True)
    
    learnings_file = os.path.join(learning_dir, "learnings.json")
    
    with open(learnings_file, 'w') as f:
        json.dump(learnings, f, indent=4)

def process_instagram_learning(profile_name: str, target_profiles: List[str], learning_prompt: str, model_name: str, storage: BaseStorage, verbose: bool = False):
    api_key_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()

    existing_learnings = load_learnings(profile_name)
    processed_urls = {item['post_url'] for item in existing_learnings}
    new_learnings = []

    posts = load_all_posts(profile_name)
    if not posts:
        log(f"No posts found for profile '{profile_name}'. Skipping.", verbose)
        return

    log(f"Found total {len(posts)} posts to process.", verbose)

    with Status("[bold green]Running Instagram Learning Utility...[/bold green]", spinner="dots", console=console) as status:
        for post in posts:
            post_url = post.get('post_url') or post.get('url')
            if not post_url:
                continue
                
            if post_url in processed_urls:
                log(f"Skipping already processed post: {post_url}", verbose, status=status)
                continue

            status.update(f"[bold yellow]Processing {post_url}...[/bold yellow]")
            
            videos_props = PROFILES[profile_name].get('properties', {}).get('platform', {}).get('instagram', {}).get('videos', {})
            output_format = videos_props.get('output_format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]')
            restrict_filenames = videos_props.get('restrict_filenames', True)

            media_path, cdn_link = download_instagram_videos(
                video_urls=post_url,
                profile_name=profile_name,
                output_format=output_format,
                restrict_filenames=restrict_filenames,
                status=status,
                verbose=verbose,
                extract_cdn_links=True,
                use_reels_dir=True
            )
            
            if not media_path:
                log(f"Failed to download media for {post_url}. Proceeding with text only if caption exists.", verbose, is_warning=True, status=status)
            
            status.update(f"[bold magenta]Generating explanation with {model_name}...[/bold magenta]")
            
            caption = post.get('caption', '')
            full_prompt = learning_prompt
            if caption:
                full_prompt += f"\n\nContext/Caption from post:\n{caption}"
            
            explanation, _ = generate_gemini(
                media_path=media_path,
                api_key_pool=api_key_pool,
                api_call_tracker=api_call_tracker,
                rate_limiter=rate_limiter,
                prompt_text=full_prompt,
                model_name=model_name,
                status=status,
                verbose=verbose
            )
            
            if explanation:
                log(f"Generated explanation for {post_url}", verbose, status=status)
                
                learning_item = {
                    "profile_name": post.get('profile_name', 'unknown'),
                    "post_url": post_url,
                    "post_type": "reel" if "/reel/" in post_url else "post",
                    "caption": caption,
                    "explanation": explanation,
                    "media_path": media_path,
                    "cdn_link": cdn_link,
                    "raw_data": post
                }
                
                existing_learnings.append(learning_item)
                new_learnings.append(learning_item)
                processed_urls.add(post_url)
                
                save_learnings(profile_name, existing_learnings)
            else:
                log(f"Failed to generate explanation for {post_url}", verbose, is_error=True, status=status)

    if new_learnings:
        log(f"Pushing {len(new_learnings)} new learning records to Supabase...", verbose)
        try:
             batch_id = str(int(time.time()))
             storage.push_content(new_learnings, batch_id, verbose)
             log("Successfully pushed to Supabase.", verbose)
        except Exception as e:
            log(f"Failed to push to Supabase: {e}", is_error=True)
