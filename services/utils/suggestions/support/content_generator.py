import os
import base64
import mimetypes
import google.generativeai as genai

from typing import Dict, Any, List
from datetime import datetime

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path

api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())

def generate_caption_with_key(post_data: Dict[str, Any], media_paths: List[str], api_key: str, verbose: bool = False) -> str:
    profile_name = post_data.get('profile_name', 'unknown')
    tweet_id = post_data.get('tweet_id', 'unknown')

    profile_config = PROFILES.get(profile_name, {})
    prompts = profile_config.get('prompts', {})
    caption_prompt = prompts.get('caption_generation', 'Generate a viral social media caption inspired by this content.')

    profile_props = profile_config.get('properties', {})
    model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

    api_key_suffix = api_key[-4:] if api_key else None

    try:
        can_call, reason = api_call_tracker.can_make_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix)
        if not can_call:
            log(f"[RATE LIMIT] Cannot call Gemini API: {reason}", verbose, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="content_generator.py")
            return f"Error generating caption: {reason}"

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        prompt_parts = []
        prompt_parts.append(caption_prompt)
        prompt_parts.append(f"\n\nOriginal post: {post_data.get('tweet_text', '')}")
        prompt_parts.append(f"\n\nTweet URL: {post_data.get('tweet_url', '')}")
        prompt_parts.append(f"\n\nGenerate a new, engaging caption inspired by this content. Make it viral and appealing to the target audience.")

        if media_paths:
            for media_path in media_paths:
                try:
                    mime_type = mimetypes.guess_type(media_path)[0] or "application/octet-stream"
                    if not mime_type.startswith('image/'):
                        continue

                    with open(media_path, 'rb') as f:
                        data_b64 = base64.b64encode(f.read()).decode('utf-8')

                    prompt_parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": data_b64
                        }
                    })
                    prompt_parts.append("\n")
                    log(f"Inlined media {os.path.basename(media_path)} for tweet {tweet_id}", verbose, log_caller_file="content_generator.py")
                except Exception as e:
                    log(f"Could not process media {media_path}: {e}", verbose, is_error=True, log_caller_file="content_generator.py")

        prompt_parts.append("Important: Generate exactly ONE caption. Do not provide multiple options or explanations. Just write a single, engaging caption.")

        log(f"[HITTING API] Calling Gemini API for tweet {tweet_id} using API key ending in {api_key[-4:]}", verbose, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="content_generator.py")
        response = model.generate_content(prompt_parts)
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=True, response=response.text[:100])

        generated_caption = response.text.strip()
        log(f"Generated caption for tweet {tweet_id}: {generated_caption[:50]}...", verbose, log_caller_file="content_generator.py")
        return generated_caption

    except Exception as e:
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=False, response=str(e))
        log(f"Error generating caption: {str(e)} for tweet {tweet_id}", verbose, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="content_generator.py")
        return f"Error generating caption: {str(e)}"

def process_single_post(post_data: Dict[str, Any], api_key_pool: APIKeyPool, media_dir: str, verbose: bool = False) -> Dict[str, Any]:
    from services.utils.suggestions.support.media_downloader import download_post_media

    tweet_id = post_data.get('tweet_id', 'unknown')

    try:
        downloaded_media_paths = download_post_media(post_data, media_dir, verbose)

        api_key = api_key_pool.get_key()
        if not api_key:
            error_msg = "No available API keys"
            log(f"{error_msg} for tweet {tweet_id}", verbose, is_error=True, log_caller_file="content_generator.py")
            return {
                "tweet_url": post_data.get('tweet_url'),
                "tweet_id": tweet_id,
                "error": error_msg,
                "generated_caption": "",
                "media_urls": post_data.get('media_urls', []),
                "downloaded_media_paths": downloaded_media_paths,
                "date": post_data.get('date'),
                "likes": post_data.get('likes', 0),
                "retweets": post_data.get('retweets', 0),
                "replies": post_data.get('replies', 0),
                "views": post_data.get('views', 0),
                "bookmarks": post_data.get('bookmarks', 0),
                "total_engagement": post_data.get('total_engagement', 0),
                "age_days": post_data.get('age_days', 0),
                "scraped_date": post_data.get('scraped_date'),
                "tweet_date": post_data.get('tweet_date'),
                "profile_image_url": post_data.get('profile_image_url'),
                "engagement_score": post_data.get('total_engagement', 0),
                "finalized": False,
                "generation_timestamp": datetime.now().isoformat()
            }

        generated_caption = generate_caption_with_key(post_data, downloaded_media_paths, api_key, verbose)

        return {
            "tweet_url": post_data.get('tweet_url'),
            "tweet_id": tweet_id,
            "original_caption": post_data.get('tweet_text', ''),
            "generated_caption": generated_caption if not generated_caption.startswith("Error") else "",
            "media_urls": post_data.get('media_urls', []),
            "downloaded_media_paths": downloaded_media_paths,
            "date": post_data.get('date'),
            "likes": post_data.get('likes', 0),
            "retweets": post_data.get('retweets', 0),
            "replies": post_data.get('replies', 0),
            "views": post_data.get('views', 0),
            "bookmarks": post_data.get('bookmarks', 0),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "scraped_date": post_data.get('scraped_date'),
            "tweet_date": post_data.get('tweet_date'),
            "profile_image_url": post_data.get('profile_image_url'),
            "engagement_score": post_data.get('total_engagement', 0),
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        log(f"Error processing post {tweet_id}: {str(e)}", verbose, is_error=True, log_caller_file="content_generator.py")
        return {
            "tweet_url": post_data.get('tweet_url'),
            "tweet_id": tweet_id,
            "error": str(e),
            "generated_caption": "",
            "media_urls": post_data.get('media_urls', []),
            "downloaded_media_paths": [],
            "date": post_data.get('date'),
            "likes": post_data.get('likes', 0),
            "retweets": post_data.get('retweets', 0),
            "replies": post_data.get('replies', 0),
            "views": post_data.get('views', 0),
            "bookmarks": post_data.get('bookmarks', 0),
            "total_engagement": post_data.get('total_engagement', 0),
            "age_days": post_data.get('age_days', 0),
            "scraped_date": post_data.get('scraped_date'),
            "tweet_date": post_data.get('tweet_date'),
            "profile_image_url": post_data.get('profile_image_url'),
            "engagement_score": post_data.get('total_engagement', 0),
            "finalized": False,
            "generation_timestamp": datetime.now().isoformat()
        }
