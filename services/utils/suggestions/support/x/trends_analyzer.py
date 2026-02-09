import os
import json
from typing import Dict, Any
from datetime import datetime

from profiles import PROFILES
from services.support.logger_util import _log as log
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.gemini_util import generate_gemini_with_inline_media
from services.support.storage.platforms.x.trends import XTrendsStorage
from services.support.path_config import get_gemini_log_file_path, get_suggestions_dir

api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())
rate_limiter = RateLimiter()

def aggregate_x_data(profile_name: str, verbose: bool = False) -> Dict[str, Any]:
    scraped_data = []
    try:
        import glob
        from services.support.path_config import get_suggestions_dir
        suggestions_dir = get_suggestions_dir(profile_name)
        if os.path.exists(suggestions_dir):
            filtered_files = glob.glob(os.path.join(suggestions_dir, "filtered_content_x_*.json"))
            for file_path in filtered_files[-3:]:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        posts = data.get('filtered_tweets', [])
                        for post in posts:
                            scraped_data.append({
                                'content': post.get('text', ''),
                                'author_name': post.get('author_name', ''),
                                'likes': int(post.get('likes', 0)),
                                'retweets': int(post.get('retweets', 0)),
                                'replies': int(post.get('replies', 0))
                            })
                except Exception as e:
                    log(f"Error reading filtered file {file_path}: {e}", verbose, log_caller_file="trends_analyzer.py")
        else:
            return {"error": f"Suggestions directory not found: {suggestions_dir}"}
    except Exception as e:
        log(f"Error aggregating file data: {e}", verbose, log_caller_file="trends_analyzer.py")
        return {"error": f"Failed to aggregate data: {e}"}

    return {
        "scraped_posts": scraped_data,
        "total_sources": len(scraped_data)
    }


def analyze_trends_with_gemini(data_summary: str, api_key_pool: APIKeyPool, trends_prompt: str = "", verbose: bool = False) -> str:
    if not trends_prompt:
        trends_prompt = "Analyze the following X/Twitter content data and identify all key trends, topics, hashtags, and keywords that people are discussing. Focus on emerging topics, viral hashtags, real-time conversations, and trending discussions. Provide structured analysis with all significant trends, hashtags, keywords, sentiment insights, and content ideas for social media engagement."

    prompt_parts = []
    prompt_parts.append(trends_prompt)
    prompt_parts.append("")
    prompt_parts.append("Data Summary:")
    prompt_parts.append(data_summary)
    prompt_parts.append("")
    prompt_parts.append("Return ONLY valid JSON with this exact structure:")
    prompt_parts.append('{"trends": ["topic1", "topic2", ...], "hashtags": ["#hashtag1", "#hashtag2", ...], "keywords": ["keyword1", "keyword2", ...], "sentiment": "overall sentiment analysis on X/Twitter", "content_ideas": ["idea1", "idea2", ...]}')
    prompt_parts.append("Do not include any other text, explanations, or formatting.")

    profile_config = PROFILES.get('flytdev', {})
    model_name = profile_config.get('properties', {}).get('model_name', 'gemini-2.5-flash-lite')

    result, _ = generate_gemini_with_inline_media(
        prompt_parts=prompt_parts,
        api_key_pool=api_key_pool,
        api_call_tracker=api_call_tracker,
        rate_limiter=rate_limiter,
        model_name=model_name,
        verbose=verbose
    )

    return result


def analyze_x_trends(profile_name: str, verbose: bool = False) -> Dict[str, Any]:
    log(f"Starting X trends analysis for profile {profile_name}", verbose, log_caller_file="trends_analyzer.py")

    aggregated_data = aggregate_x_data(profile_name, verbose)
    if "error" in aggregated_data:
        return aggregated_data

    data_summary = f"""
        Total data points analyzed: {aggregated_data['total_sources']}
        Recent Posts ({len(aggregated_data['scraped_posts'])}):
    """

    for i, post in enumerate(aggregated_data['scraped_posts']):
        author_name = post.get('author_name', 'Unknown')
        if not author_name or author_name == 'Unknown':
            tweet_url = post.get('tweet_url', '')
            if '/status/' in tweet_url:
                author_name = tweet_url.split('/status/')[0].split('/')[-1]
        data_summary += f"\n{i+1}. [@{author_name}] {post['content'][:100]}... (Likes: {post['likes']}, Retweets: {post['retweets']})"

    api_key_pool = APIKeyPool(verbose=verbose)
    if api_key_pool.size() == 0:
        return {"error": "No API keys available. Set GEMINI_API environment variable."}

    trends_prompt = PROFILES.get(profile_name, {}).get('prompts', {}).get('x_trends', '')

    log("Sending data to Gemini for trend analysis...", verbose, log_caller_file="trends_analyzer.py")
    analysis_result = analyze_trends_with_gemini(data_summary, api_key_pool, trends_prompt, verbose)

    if not analysis_result:
        return {"error": "Failed to generate trends analysis"}

    try:
        clean_result = analysis_result.strip()
        if clean_result.startswith('```json'):
            clean_result = clean_result[7:]
        if clean_result.endswith('```'):
            clean_result = clean_result[:-3]
        clean_result = clean_result.strip()

        trends_data = json.loads(clean_result)
        trends_data['posts_analyzed'] = aggregated_data['total_sources']
        trends_data['analysis_timestamp'] = datetime.now().isoformat()
    except json.JSONDecodeError as e:
        log(f"JSON parsing failed: {e}. Raw response: {analysis_result[:200]}...", verbose, is_error=True, log_caller_file="trends_analyzer.py")
        trends_data = {
            "trends": ["Analysis completed but JSON parsing failed"],
            "hashtags": [],
            "keywords": [],
            "sentiment": analysis_result[:1000],
            "content_ideas": [],
            "posts_analyzed": aggregated_data['total_sources']
        }

    suggestions_dir = get_suggestions_dir(profile_name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    trends_filename = f"trends_content_x_{timestamp}.json"
    trends_filepath = os.path.join(suggestions_dir, trends_filename)

    with open(trends_filepath, 'w', encoding='utf-8') as f:
        json.dump(trends_data, f, indent=2, ensure_ascii=False)

    log(f"Saved trends analysis to {trends_filepath}", verbose, log_caller_file="trends_analyzer.py")

    storage = XTrendsStorage(profile_name)
    trends_content = [{
        "profile_name": profile_name,
        "trends": json.dumps(trends_data.get('trends', [])),
        "hashtags": json.dumps(trends_data.get('hashtags', [])),
        "keywords": trends_data.get('keywords', []),
        "sentiment": trends_data.get('sentiment', ''),
        "content_ideas": json.dumps(trends_data.get('content_ideas', [])),
        "posts_analyzed": aggregated_data['total_sources']
    }]

    if storage.push_content(trends_content, batch_id=f"trends_{timestamp}", verbose=verbose):
        return {
            "success": True,
            "trends_count": len(trends_data.get('trends', [])),
            "posts_analyzed": aggregated_data['total_sources'],
            "analysis_saved": True
        }
    else:
        return {"error": "Failed to save trends analysis to database"}
