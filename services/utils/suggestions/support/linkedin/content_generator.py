import os
import json
import time

from datetime import datetime
from typing import Dict, Any, List, Optional
from services.support.storage.base_storage import BaseStorage
from concurrent.futures import ThreadPoolExecutor, as_completed

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path, get_suggestions_dir
from services.support.gemini_util import generate_gemini, create_inline_media_data

from services.utils.suggestions.support.linkedin.media_downloader import download_linkedin_post_media
from services.utils.suggestions.support.linkedin.scraping_utils import get_latest_filtered_linkedin_file

api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())
rate_limiter = RateLimiter()

def generate_linkedin_caption(post_data: Dict[str, Any], media_paths: List[str], api_key_pool: APIKeyPool, verbose: bool = False) -> str:
    profile_name = post_data.get('profile_name', 'unknown')
    post_id = post_data.get('data', {}).get('post_id', 'unknown')

    profile_config = PROFILES.get(profile_name, {})
    prompts = profile_config.get('prompts', {})
    caption_prompt = prompts.get('linkedin_caption_generation', 'Generate a professional LinkedIn post inspired by this content. Focus on business insights, industry trends, and professional networking.')

    profile_props = profile_config.get('properties', {})
    model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

    prompt_parts = []
    prompt_parts.append(caption_prompt)
    prompt_parts.append(f"\n\nOriginal post: {post_data.get('data', {}).get('text', '')}")
    prompt_parts.append(f"\n\nPost URL: {post_data.get('data', {}).get('profile_url', '')}")
    prompt_parts.append(f"\n\nGenerate a professional LinkedIn post inspired by this content. Include relevant hashtags and maintain a business-appropriate tone.")
    prompt_parts.append("Important: Generate exactly ONE post. Do not provide multiple options or explanations. Just write a single, professional post.")

    if media_paths:
        for media_path in media_paths:
            media_data = create_inline_media_data(media_path, verbose)
            if media_data:
                prompt_parts.append(media_data)
                prompt_parts.append("\n")
                log(f"Inlined media {os.path.basename(media_path)} for post {post_id}", verbose, log_caller_file="content_generator.py")

    log(f"[HITTING API] Calling Gemini API for post {post_id}", verbose, log_caller_file="content_generator.py")

    result, _ = generate_gemini(
        prompt_parts=prompt_parts,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        model_name=model_name,
        verbose=verbose
    )

    if result:
        log(f"Generated post for {post_id}: {result[:50]}...", verbose, log_caller_file="content_generator.py")
        return result
    else:
        return "Error generating post: Failed to generate content"

def process_linkedin_post(post_data: Dict[str, Any], api_key_pool: APIKeyPool, media_dir: str, verbose: bool = False) -> Dict[str, Any]:
    post_id = post_data.get('data', {}).get('post_id', 'unknown')

    try:
        downloaded_media_paths = download_linkedin_post_media(post_data, media_dir, verbose)
        generated_caption = generate_linkedin_caption(post_data, downloaded_media_paths, api_key_pool, verbose)

        return {
            "source": "linkedin",
            "content_id": post_id,
            "data": post_data.get('data', {}),
            "engagement": post_data.get('engagement', {}),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "scraped_at": post_data.get('scraped_at'),
            "post_date": post_data.get('data', {}).get('post_date'),
            "profile_url": post_data.get('data', {}).get('profile_url'),
            "original_content": post_data.get('data', {}).get('text') or post_data.get('data', {}).get('post_text', ''),
            "generated_caption": generated_caption if not generated_caption.startswith("Error") else "",
            "media_urls": post_data.get('data', {}).get('media_urls', []),
            "downloaded_media_paths": downloaded_media_paths,
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        log(f"Error processing post {post_id}: {str(e)}", verbose, is_error=True, log_caller_file="content_generator.py")
        return {
            "source": "linkedin",
            "data": post_data.get('data', {}),
            "engagement": post_data.get('engagement', {}),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "scraped_at": post_data.get('scraped_at'),
            "post_date": post_data.get('data', {}).get('post_date'),
            "profile_url": post_data.get('data', {}).get('profile_url'),
            "original_content": post_data.get('data', {}).get('text') or post_data.get('data', {}).get('post_text', ''),
            "error": str(e),
            "generated_caption": "",
            "media_urls": post_data.get('data', {}).get('media_urls', []),
            "downloaded_media_paths": [],
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }

def run_linkedin_content_generation(profile_name: str, storage: Optional[BaseStorage] = None, verbose: bool = False) -> Dict[str, Any]:
    filtered_file = get_latest_filtered_linkedin_file(profile_name)
    if not filtered_file:
        return {"error": "No filtered content found. Run 'filter' command first."}

    try:
        log(f"Starting LinkedIn content generation for profile {profile_name} with storage: {storage is not None}", verbose, log_caller_file="content_generator.py")
        with open(filtered_file, 'r') as f:
            filtered_data = json.load(f)

        filtered_posts = filtered_data.get('filtered_posts', [])
        if not filtered_posts:
            return {"error": "No filtered posts found in the file."}

        approved_posts = filtered_posts

        profile_props = PROFILES[profile_name].get('properties', {})
        verbose = profile_props.get('verbose', False)

        api_key_pool = APIKeyPool(verbose=verbose)
        if api_key_pool.size() == 0:
            return {"error": "No API keys available. Set GEMINI_API environment variable."}

        media_dir = os.path.join(get_suggestions_dir(profile_name), "media")
        os.makedirs(media_dir, exist_ok=True)

        generated_posts = []
        with ThreadPoolExecutor(max_workers=api_key_pool.size()) as executor:
            futures = []
            batch_id = f"linkedin_generation_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            for post in approved_posts:
                post['profile_name'] = profile_name
                post['batch_id'] = batch_id
                future = executor.submit(process_linkedin_post, post, api_key_pool, media_dir, verbose)
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                
                processed_post = {
                    "profile_name": result.get('profile_name', profile_name),
                    "batch_id": batch_id,
                    "content_id": result.get('data', {}).get('post_id'),
                    "source": result.get('source'),
                    "original_content": result.get('original_content'),
                    "generated_caption": result.get('generated_caption'),
                    "total_engagement": result.get('total_engagement', 0),
                    "likes": result.get('engagement', {}).get('likes', 0),
                    "comments": result.get('engagement', {}).get('comments', 0),
                    "reposts": result.get('engagement', {}).get('reposts', 0),
                    "media_urls": result.get('media_urls', []),
                    "downloaded_media_paths": result.get('downloaded_media_paths', []),
                    "age_days": result.get('age_days', 0),
                    "scraped_at": result.get('scraped_at'),
                    "post_date": result.get('post_date'),
                    "profile_url": result.get('profile_url'),
                    "finalized": result.get('finalized', False),
                    "generation_timestamp": result.get('generation_timestamp'),
                    "status": 'pending'
                }
                generated_posts.append(processed_post)

        if storage:
            if storage.push_content(generated_posts, batch_id, verbose):
                log(f"Successfully pushed {len(generated_posts)} generated LinkedIn captions to database.", verbose, log_caller_file="content_generator.py")
                return {"success": True, "total_generated": len(generated_posts)}
            else:
                return {"error": "Failed to push generated LinkedIn captions to database."}
        else:
            profile_config = PROFILES[profile_name]
            prompts = profile_config.get('prompts', {})
            caption_prompt = prompts.get('linkedin_caption_generation', '')
            model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

            suggestions_content = {
                "timestamp": datetime.now().isoformat(),
                "profile_name": profile_name,
                "generated_posts": generated_posts,
                "metadata": {
                    "total_generated": len(generated_posts),
                    "caption_generation_prompt": caption_prompt,
                    "model_used": model_name,
                    "processing_date": datetime.now().strftime("%Y%m%d"),
                    "api_keys_used": api_key_pool.size()
                }
            }

            output_file = os.path.join(get_suggestions_dir(profile_name), f"suggestions_content_linkedin_{datetime.now().strftime('%Y%m%d')}.json")
            with open(output_file, 'w') as f:
                json.dump(suggestions_content, f, indent=2)

            return {
                "success": True,
                "total_generated": len(generated_posts),
                "output_file": output_file
            }


    except Exception as e:
        return {"error": f"Error during content generation: {str(e)}"}

def generate_new_linkedin_tweets_from_filtered(profile_name: str, storage: Optional[BaseStorage] = None, verbose: bool = False) -> Dict[str, Any]:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return {"error": "No filtered content found. Run 'filter' command first."}

    linkedin_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_linkedin_') and f.endswith('.json')]

    if not linkedin_files:
        return {"error": "No filtered content found. Run 'filter' command first."}

    linkedin_files.sort(reverse=True)
    filtered_file = os.path.join(suggestions_dir, linkedin_files[0])
    if not filtered_file:
        return {"error": "No filtered content found. Run 'filter' command first."}

    try:
        with open(filtered_file, 'r') as f:
            filtered_data = json.load(f)

        filtered_posts = filtered_data.get('filtered_posts', [])
        if not filtered_posts:
            return {"error": "No filtered posts found."}

        profile_config = PROFILES.get(profile_name, {})
        prompts = profile_config.get('prompts', {})
        new_posts_prompt = prompts.get('new_linkedin_posts_generation', 'Generate 3 new original professional posts inspired by the themes and trends in these LinkedIn posts. Focus on business insights and professional networking. Return only the posts, one per line.')

        profile_props = profile_config.get('properties', {})
        model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')
        num_posts = profile_props.get('new_linkedin_posts', 3)

        api_key_pool = APIKeyPool(verbose=False)
        if api_key_pool.size() == 0:
            return {"error": "No API keys available. Set GEMINI_API environment variable."}

        post_texts = []
        for post in filtered_posts[:10]:
            data = post.get('data', {})
            text = data.get('text', '')
            if text:
                post_texts.append(text[:300])

        prompt_parts = []
        prompt_parts.append(f"Here are {len(post_texts)} example LinkedIn posts:")
        for i, text in enumerate(post_texts, 1):
            prompt_parts.append(f"{i}. {text}")
        prompt_parts.append(f"\n\n{new_posts_prompt}")
        prompt_parts.append(f"\n\nReturn exactly {num_posts} new posts, one per line. Do not include analysis or explanations - only the post text.")

        result, _ = generate_gemini(
            prompt_parts=prompt_parts,
            api_key_pool=api_key_pool,
            api_call_tracker=api_call_tracker,
            rate_limiter=rate_limiter,
            model_name=model_name,
            verbose=False
        )

        new_posts_data = []
        if result:
            sections = result.strip().split('\n\n')
            post_count = 0
            batch_id = f"new_linkedin_generation_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            for section in sections:
                section = section.strip()
                if section and len(section) > 20 and post_count < num_posts:
                    new_posts_data.append({
                        "profile_name": profile_name,
                        "batch_id": batch_id,
                        "generated_text_id": f"new_linkedin_{int(time.time())}_{post_count}",
                        "generated_text": section,
                        "filtered_content_analyzed": filtered_file,
                        "approved": False,
                        "status": 'pending',
                        "generation_date": datetime.now().isoformat()
                    })
                    post_count += 1

        if not new_posts_data:
            return {"error": "Failed to generate new posts"}

        if storage:
            if storage.push_content(new_posts_data, batch_id, verbose=profile_props.get('verbose', False)):
                log(f"Successfully pushed {len(new_posts_data)} new LinkedIn posts to database.", verbose=profile_props.get('verbose', False), log_caller_file="content_generator.py")
                return {"success": True, "total_generated": len(new_posts_data)}
            else:
                return {"error": "Failed to push new LinkedIn posts to database."}
        else:
            new_posts_content = {
                "timestamp": datetime.now().isoformat(),
                "profile_name": profile_name,
                "platform": "linkedin",
                "new_posts": new_posts_data,
                "metadata": {
                    "total_filtered_posts_analyzed": len(filtered_posts),
                    "total_new_posts_generated": len(new_posts_data),
                    "generation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }

            output_file = os.path.join(get_suggestions_dir(profile_name), f"new_posts_content_linkedin_{datetime.now().strftime('%Y%m%d')}.json")
            with open(output_file, 'w') as f:
                json.dump(new_posts_content, f, indent=2)

            return {
                "success": True,
                "total_generated": len(new_posts_data),
                "output_file": output_file
            }

    except Exception as e:
        return {"error": f"Error during new posts generation: {str(e)}"}