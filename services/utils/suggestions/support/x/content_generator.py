import os
import json
import time

from datetime import datetime
from typing import Dict, Any, List

from profiles import PROFILES
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path, get_suggestions_dir
from services.support.gemini_util import generate_gemini_with_inline_media, create_inline_media_data

from services.utils.suggestions.support.x.media_downloader import download_post_media
from services.utils.suggestions.support.x.scraping_utils import get_latest_approved_file

api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())
rate_limiter = RateLimiter()

def generate_caption_with_key(post_data: Dict[str, Any], media_paths: List[str], api_key_pool: APIKeyPool, verbose: bool = False) -> str:
    profile_name = post_data.get('profile_name', 'unknown')
    tweet_id = post_data.get('tweet_id', 'unknown')

    profile_config = PROFILES.get(profile_name, {})
    prompts = profile_config.get('prompts', {})
    caption_prompt = prompts.get('caption_generation', 'Generate a viral social media caption inspired by this content.')

    profile_props = profile_config.get('properties', {})
    model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')

    prompt_parts = []
    prompt_parts.append(caption_prompt)
    prompt_parts.append(f"\n\nOriginal post: {post_data.get('tweet_text', '')}")
    prompt_parts.append(f"\n\nTweet URL: {post_data.get('tweet_url', '')}")
    prompt_parts.append(f"\n\nGenerate a new, engaging caption inspired by this content. Make it viral and appealing to the target audience.")

    if media_paths:
        for media_path in media_paths:
            media_data = create_inline_media_data(media_path, verbose)
            if media_data:
                prompt_parts.append(media_data)
                prompt_parts.append("\n")
                log(f"Inlined media {os.path.basename(media_path)} for tweet {tweet_id}", verbose, log_caller_file="content_generator.py")

    prompt_parts.append("Important: Generate exactly ONE caption. Do not provide multiple options or explanations. Just write a single, engaging caption.")

    log(f"[HITTING API] Calling Gemini API for tweet {tweet_id}", verbose, log_caller_file="content_generator.py")

    result, _ = generate_gemini_with_inline_media(
        prompt_parts=prompt_parts,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        model_name=model_name,
        verbose=verbose
    )

    if result:
        log(f"Generated caption for tweet {tweet_id}: {result[:50]}...", verbose, log_caller_file="content_generator.py")
        return result
    else:
        return "Error generating caption: Failed to generate content"

def process_single_post(post_data: Dict[str, Any], api_key_pool: APIKeyPool, media_dir: str, verbose: bool = False) -> Dict[str, Any]:
    tweet_id = post_data.get('tweet_id', 'unknown')

    try:
        downloaded_media_paths = download_post_media(post_data, media_dir, verbose)
        generated_caption = generate_caption_with_key(post_data, downloaded_media_paths, api_key_pool, verbose)

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

def run_content_generation(profile_name: str) -> Dict[str, Any]:
    approved_file = get_latest_approved_file(profile_name)
    if not approved_file:
        return {"error": "No approved content found. Run 'web' command and approve content first."}

    try:
        with open(approved_file, 'r') as f:
            approved_data = json.load(f)

        approved_posts = approved_data.get('approved_posts', [])
        if not approved_posts:
            return {"error": "No approved posts found in the file."}

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
            for post in approved_posts:
                post['profile_name'] = profile_name
                future = executor.submit(process_single_post, post, api_key_pool, media_dir, verbose)
                futures.append(future)

            for future in as_completed(futures):
                result = future.result()
                generated_posts.append(result)

        profile_config = PROFILES[profile_name]
        prompts = profile_config.get('prompts', {})
        caption_prompt = prompts.get('caption_generation', '')
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

        output_file = os.path.join(get_suggestions_dir(profile_name), f"suggestions_content_x_{datetime.now().strftime('%Y%m%d')}.json")
        with open(output_file, 'w') as f:
            json.dump(suggestions_content, f, indent=2)

        return {
            "success": True,
            "total_generated": len(generated_posts),
            "output_file": output_file
        }

    except Exception as e:
        return {"error": f"Error during content generation: {str(e)}"}

def generate_new_tweets_from_filtered(profile_name: str) -> Dict[str, Any]:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return {"error": "No filtered content found. Run 'filter' command first."}

    x_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_x_') and f.endswith('.json')]

    if not x_files:
        return {"error": "No filtered content found. Run 'filter' command first."}

    x_files.sort(reverse=True)
    filtered_file = os.path.join(suggestions_dir, x_files[0])
    if not filtered_file:
        return {"error": "No filtered content found. Run 'filter' command first."}

    try:
        with open(filtered_file, 'r') as f:
            filtered_data = json.load(f)

        filtered_tweets = filtered_data.get('filtered_tweets', [])
        if not filtered_tweets:
            return {"error": "No filtered tweets found."}

        profile_config = PROFILES.get(profile_name, {})
        prompts = profile_config.get('prompts', {})
        new_tweets_prompt = prompts.get('new_tweets_generation', 'Generate 5 new original tweets inspired by the themes and trends in these tweets. Make them engaging and viral. Return only the tweets, one per line.')

        profile_props = profile_config.get('properties', {})
        model_name = profile_props.get('model_name', 'gemini-2.5-flash-lite')
        num_tweets = profile_props.get('num_new_tweets', 5)

        api_key_pool = APIKeyPool(verbose=False)
        if api_key_pool.size() == 0:
            return {"error": "No API keys available. Set GEMINI_API environment variable."}

        tweet_texts = []
        for tweet in filtered_tweets[:10]:
            text = tweet.get('tweet_text', '')
            if text:
                tweet_texts.append(text[:200])

        prompt_parts = []
        prompt_parts.append(f"Here are {len(tweet_texts)} example tweets:")
        for i, text in enumerate(tweet_texts, 1):
            prompt_parts.append(f"{i}. {text}")
        prompt_parts.append(f"\n\n{new_tweets_prompt}")
        prompt_parts.append(f"\n\nReturn exactly {num_tweets} new tweets, one per line. Do not include analysis or explanations - only the tweet text.")

        result, _ = generate_gemini_with_inline_media(
            prompt_parts=prompt_parts,
            api_key_pool=api_key_pool,
            api_call_tracker=api_call_tracker,
            rate_limiter=rate_limiter,
            model_name=model_name,
            verbose=False
        )

        new_tweets = []
        if result:
            lines = result.strip().split('\n')
            tweet_count = 0
            for line in lines:
                line = line.strip()
                if line and len(line) > 10 and tweet_count < num_tweets:
                    new_tweets.append({
                        "id": f"new_x_{int(time.time())}_{tweet_count}",
                        "text": line,
                        "approved": False
                    })
                    tweet_count += 1

        if not new_tweets:
            return {"error": "Failed to generate new tweets"}

        new_tweets_content = {
            "timestamp": datetime.now().isoformat(),
            "profile_name": profile_name,
            "platform": "x",
            "new_tweets": new_tweets,
            "metadata": {
                "total_filtered_tweets_analyzed": len(filtered_tweets),
                "total_new_tweets_generated": len(new_tweets),
                "generation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        }

        output_file = os.path.join(get_suggestions_dir(profile_name), f"new_tweets_content_x_{datetime.now().strftime('%Y%m%d')}.json")
        with open(output_file, 'w') as f:
            json.dump(new_tweets_content, f, indent=2)

        return {
            "success": True,
            "total_generated": len(new_tweets),
            "output_file": output_file
        }

    except Exception as e:
        return {"error": f"Error during new tweets generation: {str(e)}"}