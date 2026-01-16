import os
import sys
import json

from typing import Dict, Any
from datetime import datetime

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.path_config import get_suggestions_dir

def parse_tweet_date(tweet_data):
    if isinstance(tweet_data.get('tweet_date'), str):
        try:
            return datetime.fromisoformat(tweet_data['tweet_date'].replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(tweet_data['tweet_date'], '%Y-%m-%d %H:%M:%S')
            except:
                return datetime.now()
    return datetime.now()

def filter_and_sort_content(scraped_file_path: str, profile_name: str) -> Dict[str, Any]:
    profile_props = PROFILES[profile_name].get('properties', {})
    content_filter = profile_props.get('content_filter', {})

    min_age_days = content_filter.get('min_age_days', 7)
    max_age_days = content_filter.get('max_age_days', 30)
    max_posts_per_profile = content_filter.get('max_posts_per_profile', 5)
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

    tweets_by_profile = {}
    for tweet in scraped_tweets:
        username = tweet.get('username') or tweet.get('user', {}).get('screen_name')

        if not username and tweet.get('tweet_url'):
            try:
                url_parts = tweet['tweet_url'].split('/')
                if len(url_parts) >= 4 and url_parts[2] == 'x.com':
                    username = url_parts[3]
            except:
                pass

        if not username:
            username = 'unknown'

        if username not in tweets_by_profile:
            tweets_by_profile[username] = []
        tweets_by_profile[username].append(tweet)

    all_top_tweets = []
    profile_stats = {}

    for username, profile_tweets in tweets_by_profile.items():
        age_filtered_tweets = []

        for tweet in profile_tweets:
            tweet_date = parse_tweet_date(tweet)
            age_days = (now - tweet_date).days

            if not (min_age_days <= age_days <= max_age_days):
                continue

            likes = tweet.get('likes', 0)
            retweets = tweet.get('retweets', 0)
            replies = tweet.get('replies', 0)
            total_engagement = likes + retweets + replies

            tweet_copy = tweet.copy()
            tweet_copy['total_engagement'] = total_engagement
            tweet_copy['age_days'] = age_days
            age_filtered_tweets.append(tweet_copy)

        if age_filtered_tweets:
            age_filtered_tweets.sort(key=lambda x: x['total_engagement'], reverse=True)
            top_tweets_from_profile = age_filtered_tweets[:max_posts_per_profile]
            all_top_tweets.extend(top_tweets_from_profile)

            profile_stats[username] = {
                "total_tweets": len(profile_tweets),
                "age_filtered_tweets": len(age_filtered_tweets),
                "selected_top": len(top_tweets_from_profile),
                "avg_engagement": sum(t['total_engagement'] for t in top_tweets_from_profile) / len(top_tweets_from_profile) if top_tweets_from_profile else 0
            }

    all_top_tweets.sort(key=lambda x: x['total_engagement'], reverse=True)
    final_top_tweets = all_top_tweets[:max_posts]

    filtered_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "original_scraped_count": len(scraped_tweets),
        "profiles_count": len(tweets_by_profile),
        "filtered_count": len(final_top_tweets),
        "filter_criteria": {
            "min_age_days": min_age_days,
            "max_age_days": max_age_days,
            "max_posts_per_profile": max_posts_per_profile,
            "max_posts": max_posts
        },
        "profile_stats": profile_stats,
        "filtered_tweets": final_top_tweets
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filtered_filename = f"filtered_content_x_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filtered_filepath = os.path.join(suggestions_dir, filtered_filename)

    try:
        with open(filtered_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": f"Failed to save filtered data: {e}"}

    return {
        "success": True,
        "original_count": len(scraped_tweets),
        "profiles_count": len(tweets_by_profile),
        "filtered_count": len(final_top_tweets),
        "saved_file": filtered_filepath,
        "profile_stats": profile_stats,
        "top_tweets": final_top_tweets[:5]
    }

def get_latest_scraped_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    scraped_files = [f for f in os.listdir(suggestions_dir) if f.startswith('scraped_content_x_') and f.endswith('.json')]
    if not scraped_files:
        return ""

    scraped_files.sort(reverse=True)
    return os.path.join(suggestions_dir, scraped_files[0])
