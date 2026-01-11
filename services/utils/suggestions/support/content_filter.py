import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir

def parse_tweet_date(tweet_data):
    if isinstance(tweet_data.get('tweet_date'), str):
        try:
            return datetime.fromisoformat(tweet_data['tweet_date'].replace('Z', '+00:00'))
        except:
            return datetime.now()
    return datetime.now()

def filter_and_sort_content(scraped_file_path: str, profile_name: str) -> Dict[str, Any]:
    profile_props = PROFILES[profile_name].get('properties', {})
    content_filter = profile_props.get('content_filter', {})

    min_age_days = content_filter.get('min_age_days', 7)
    max_age_days = content_filter.get('max_age_days', 30)
    min_total_engagement = content_filter.get('min_total_engagement', 50)
    max_posts = content_filter.get('max_posts', 25)

    try:
        with open(scraped_file_path, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load scraped data: {e}"}

    scraped_tweets = scraped_data.get('scraped_tweets', [])
    if not scraped_tweets:
        return {"error": "No tweets found in scraped data"}

    now = datetime.now()
    filtered_tweets = []

    for tweet in scraped_tweets:
        tweet_date = parse_tweet_date(tweet)
        age_days = (now - tweet_date).days

        if not (min_age_days <= age_days <= max_age_days):
            continue

        likes = tweet.get('likes', 0)
        retweets = tweet.get('retweets', 0)
        replies = tweet.get('replies', 0)
        total_engagement = likes + retweets + replies

        if total_engagement < min_total_engagement:
            continue

        tweet_copy = tweet.copy()
        tweet_copy['total_engagement'] = total_engagement
        tweet_copy['age_days'] = age_days
        filtered_tweets.append(tweet_copy)

    filtered_tweets.sort(key=lambda x: x['total_engagement'], reverse=True)
    top_tweets = filtered_tweets[:max_posts]

    filtered_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "original_scraped_count": len(scraped_tweets),
        "filtered_count": len(top_tweets),
        "filter_criteria": {
            "min_age_days": min_age_days,
            "max_age_days": max_age_days,
            "min_total_engagement": min_total_engagement,
            "max_posts": max_posts
        },
        "filtered_tweets": top_tweets
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filtered_filename = f"filtered_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filtered_filepath = os.path.join(suggestions_dir, filtered_filename)

    try:
        with open(filtered_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": f"Failed to save filtered data: {e}"}

    return {
        "success": True,
        "original_count": len(scraped_tweets),
        "filtered_count": len(top_tweets),
        "saved_file": filtered_filepath,
        "top_tweets": top_tweets[:5]
    }

def get_latest_scraped_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    scraped_files = [f for f in os.listdir(suggestions_dir) if f.startswith('scraped_content_') and f.endswith('.json')]
    if not scraped_files:
        return ""

    scraped_files.sort(reverse=True)
    return os.path.join(suggestions_dir, scraped_files[0])
