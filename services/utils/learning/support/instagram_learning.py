import os
import json
import time
import re
import requests

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

def download_image(url: str, profile_name: str, post_id: str) -> Optional[str]:
    try:
        if not url:
            return None
        
        output_dir = os.path.join(get_base_dir(), "tmp", "platform", "instagram", profile_name, "images")
        os.makedirs(output_dir, exist_ok=True)
        
        # Simple extension check or default to jpg
        ext = "jpg"
        if ".png" in url.lower(): ext = "png"
        elif ".webp" in url.lower(): ext = "webp"
        
        file_path = os.path.join(output_dir, f"{post_id}.{ext}")
        
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return file_path
    except Exception as e:
        log(f"Failed to download image from {url}: {e}", True, is_error=True)
    return None

def process_instagram_learning(profile_name: str, target_profiles: List[str], learning_prompt: str, model_name: str, storage: BaseStorage, verbose: bool = False):
    api_key_pool = APIKeyPool()
    rate_limiter = RateLimiter()
    api_call_tracker = APICallTracker()

    existing_learnings = load_learnings(profile_name)
    local_processed_urls = {item['post_url'] for item in existing_learnings}
    
    log("Fetching processed URLs from database to avoid redundant work...", verbose)
    db_processed_urls = set(storage.get_all_processed_urls(verbose))
    
    processed_urls = local_processed_urls.union(db_processed_urls)
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

            # Try video download first
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
            
            from services.support.gemini_util import create_inline_media_data
            import mimetypes
            
            prompt_parts = []
            final_media_path = None
            
            if media_path:
                mime_type = mimetypes.guess_type(media_path)[0] or ""
                if "video" in mime_type:
                    final_media_path = media_path
                else:
                    inline = create_inline_media_data(media_path, verbose, status)
                    if inline: prompt_parts.append(inline)
            
            if not final_media_path:
                # Handle Carousel or missing media
                image_urls = post.get('image_urls', [])
                if not image_urls and post.get('thumbnail_url'):
                    image_urls = [post['thumbnail_url']]
                
                if image_urls:
                    log(f"Downloading {len(image_urls)} images for carousel/post support...", verbose, status=status)
                    for i, img_url in enumerate(image_urls):
                         # Limit to 10 images to avoid prompt bloat
                         if i >= 10: break
                         p_id = post.get('id', str(int(time.time())))
                         local_img_path = download_image(img_url, profile_name, f"{p_id}_{i}")
                         if local_img_path:
                             inline = create_inline_media_data(local_img_path, verbose, status)
                             if inline: prompt_parts.append(inline)
                             # Keep track for storage
                             if not media_path: media_path = local_img_path
                
            if not final_media_path and not prompt_parts:
                log(f"Failed to download any media for {post_url}. Proceeding with text only if caption exists.", verbose, status=status)
            
            status.update(f"[bold magenta]Generating explanation with {model_name}...[/bold magenta]")
            
            caption = post.get('caption', '')
            full_prompt = learning_prompt
            if caption:
                full_prompt += f"\n\nContext/Caption from post:\n{caption}"
            
            explanation, _ = generate_gemini(
                media_path=final_media_path,
                prompt_parts=prompt_parts if prompt_parts else None,
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
                
                short_explanation = ""
                long_explanation = ""
                try:
                    clean_json = explanation.strip()
                    if clean_json.startswith("```"):
                        clean_json = re.sub(r"```(?:json)?\n?|\n?```", "", clean_json).strip()
                    
                    data = json.loads(clean_json)
                    short_explanation = data.get("short_explanation", "")
                    long_explanation = data.get("long_explanation", "")
                except (json.JSONDecodeError, ValueError) as e:
                    log(f"Failed to parse explanation JSON for {post_url}: {e}", verbose, is_warning=True, status=status)
                    # Fallback: if it's not JSON, put the whole thing in long_explanation
                    long_explanation = explanation

                learning_item = {
                    "profile_name": post.get('profile_name', 'unknown'),
                    "post_url": post_url,
                    "post_type": "reel" if "/reel/" in post_url else "post",
                    "caption": caption,
                    "short_explanation": short_explanation,
                    "long_explanation": long_explanation,
                    "media_path": media_path,
                    "cdn_link": cdn_link,
                    "raw_data": json.dumps(post)
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
