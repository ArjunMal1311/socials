import os
import json

from datetime import datetime
from typing import Dict, Any, List, Optional

from services.support.storage.base_storage import BaseStorage

from profiles import PROFILES
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path, get_suggestions_dir
from services.support.gemini_util import generate_gemini, create_inline_media_data

from services.utils.suggestions.support.reddit.media_downloader import download_reddit_post_media
from services.utils.suggestions.support.reddit.scraping_utils import get_latest_filtered_reddit_file

api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())
rate_limiter = RateLimiter()

def generate_reddit_caption(post_data: Dict[str, Any], media_paths: List[str], api_key_pool: APIKeyPool, verbose: bool = False) -> str:
    profile_name = post_data.get('profile_name', 'unknown')
    post_id = post_data.get('data', {}).get('id', 'unknown')

    profile_config = PROFILES.get(profile_name, {})
    prompts = profile_config.get('prompts', {})
    caption_prompt = prompts.get('reddit_caption_generation',
        'Generate a viral social media caption inspired by this Reddit post. Make it engaging and shareable.')

    profile_props = profile_config.get('properties', {})
    model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

    title = post_data.get('data', {}).get('title', '')
    content = post_data.get('data', {}).get('content', '')
    subreddit = post_data.get('data', {}).get('subreddit', '')
    score = post_data.get('engagement', {}).get('score', 0)
    comments = post_data.get('engagement', {}).get('num_comments', 0)

    prompt_parts = []
    prompt_parts.append(caption_prompt)
    prompt_parts.append(f"\n\nReddit Post Title: {title}")
    prompt_parts.append(f"\nSubreddit: r/{subreddit}")
    prompt_parts.append(f"\nContent: {content[:500]}{'...' if len(content) > 500 else ''}")
    prompt_parts.append(f"\nEngagement: {score} upvotes, {comments} comments")
    prompt_parts.append(f"\n\nGenerate a new, engaging caption inspired by this Reddit discussion. Make it viral and appealing to the target audience.")
    prompt_parts.append(f"\n\nURL: {post_data.get('data', {}).get('url', '')}")

    if media_paths:
        for media_path in media_paths:
            media_data = create_inline_media_data(media_path, verbose)
            if media_data:
                prompt_parts.append(media_data)
                prompt_parts.append("\n")
                log(f"Inlined media {os.path.basename(media_path)} for Reddit post {post_id}", verbose, log_caller_file="content_generator.py")

    prompt_parts.append("\n\nImportant: Generate exactly ONE caption. Do not provide multiple options or explanations. Just write a single, engaging caption.")

    log(f"[HITTING API] Calling Gemini API for Reddit post {post_id}", verbose, log_caller_file="content_generator.py")

    result, _ = generate_gemini(
        prompt_parts=prompt_parts,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        model_name=model_name,
        verbose=verbose
    )

    if result:
        log(f"Generated caption for Reddit post {post_id}: {result[:50]}...", verbose, log_caller_file="content_generator.py")
        return result
    else:
        return "Error generating caption: Failed to generate content"

def process_single_reddit_post(post_data: Dict[str, Any], api_key_pool: APIKeyPool, media_dir: str, verbose: bool = False) -> Dict[str, Any]:
    reddit_url = post_data.get('data', {}).get('url', '')
    if reddit_url:
        import hashlib
        post_id = hashlib.md5(reddit_url.encode()).hexdigest()[:16]
    else:
        post_id = f"reddit_{hash(str(post_data))}"

    try:
        downloaded_media_paths = download_reddit_post_media(post_data, media_dir, verbose)
        generated_caption = generate_reddit_caption(post_data, downloaded_media_paths, api_key_pool, verbose)

        return {
            "reddit_url": post_data.get('data', {}).get('url', ''),
            "content_id": post_id,
            "original_title": post_data.get('data', {}).get('title', ''),
            "original_content": post_data.get('data', {}).get('content', ''),
            "subreddit": post_data.get('data', {}).get('subreddit', ''),
            "generated_caption": generated_caption if not generated_caption.startswith("Error") else "",
            "media_urls": [],
            "downloaded_media_paths": downloaded_media_paths,
            "score": post_data.get('engagement', {}).get('score', 0),
            "comments": post_data.get('engagement', {}).get('num_comments', 0),
            "upvote_ratio": post_data.get('engagement', {}).get('upvote_ratio', 0.0),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "scraped_date": post_data.get('scraped_at'),
            "created_utc": post_data.get('data', {}).get('created_utc'),
            "engagement_score": post_data.get('total_engagement', 0),
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        log(f"Error processing Reddit post {post_id}: {str(e)}", verbose, is_error=True, log_caller_file="content_generator.py")
        return {
            "reddit_url": post_data.get('data', {}).get('url', ''),
            "content_id": post_id,
            "original_title": post_data.get('data', {}).get('title', ''),
            "original_content": post_data.get('data', {}).get('content', ''),
            "error": str(e),
            "generated_caption": "",
            "media_urls": [],
            "downloaded_media_paths": [],
            "score": post_data.get('engagement', {}).get('score', 0),
            "comments": post_data.get('engagement', {}).get('num_comments', 0),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }

def run_reddit_content_generation(profile_name: str, storage: Optional[BaseStorage] = None, verbose: bool = False) -> Dict[str, Any]:
    filtered_file = get_latest_filtered_reddit_file(profile_name)
    if not filtered_file:
        return {"error": "No filtered Reddit content found. Run 'filter' command first."}

    try:
        log(f"Starting Reddit content generation for profile {profile_name} with storage: {storage is not None}", verbose, log_caller_file="content_generator.py")

        with open(filtered_file, 'r') as f:
            filtered_data = json.load(f)

        filtered_posts = filtered_data.get('filtered_reddit_posts', [])
        if not filtered_posts:
            return {"error": "No filtered Reddit posts found in the file."}

        posts_to_process = filtered_posts[:10]

        profile_props = PROFILES[profile_name].get('properties', {})
        verbose = profile_props.get('verbose', False)

        api_key_pool = APIKeyPool(verbose=verbose)
        if api_key_pool.size() == 0:
            return {"error": "No API keys available. Set GEMINI_API environment variable."}

        media_dir = os.path.join(get_suggestions_dir(profile_name), "reddit_media")
        os.makedirs(media_dir, exist_ok=True)

        generated_posts = []
        with ThreadPoolExecutor(max_workers=min(api_key_pool.size(), 3)) as executor:
            futures = []
            batch_id = f"reddit_generation_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            for post in posts_to_process:
                post['profile_name'] = profile_name
                post['batch_id'] = batch_id
                future = executor.submit(process_single_reddit_post, post, api_key_pool, media_dir, verbose)
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                generated_posts.append(result)

        if storage:
            push_result = storage.push_content(generated_posts, batch_id, verbose)
            if push_result:
                log(f"Successfully pushed {len(generated_posts)} generated Reddit captions to database.", verbose, log_caller_file="content_generator.py")
                return {"success": True, "total_generated": len(generated_posts)}
            else:
                log(f"Failed to push generated Reddit captions to database.", verbose, is_error=True, log_caller_file="content_generator.py")
                return {"error": "Failed to push generated Reddit captions to database."}
        else:
            profile_config = PROFILES[profile_name]
            prompts = profile_config.get('prompts', {})
            caption_prompt = prompts.get('reddit_caption_generation', '')

            reddit_content = {
                "timestamp": datetime.now().isoformat(),
                "profile_name": profile_name,
                "platform": "reddit",
                "generated_reddit_posts": generated_posts,
                "metadata": {
                    "total_generated": len(generated_posts),
                    "reddit_caption_generation_prompt": caption_prompt,
                    "model_used": profile_props.get('model_name', 'gemini-2.5-flash-lite'),
                    "processing_date": datetime.now().strftime("%Y%m%d"),
                    "api_keys_used": api_key_pool.size(),
                    "posts_processed": len(posts_to_process)
                }
            }

            output_file = os.path.join(get_suggestions_dir(profile_name), f"suggestions_content_reddit_{datetime.now().strftime('%Y%m%d')}.json")
            with open(output_file, 'w') as f:
                json.dump(reddit_content, f, indent=2)

            return {
                "success": True,
                "total_generated": len(generated_posts),
                "output_file": output_file
            }

    except Exception as e:
        return {"error": f"Error during Reddit content generation: {str(e)}"}
