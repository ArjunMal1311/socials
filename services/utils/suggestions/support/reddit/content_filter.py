import os
import sys
import json

from typing import Dict, Any
from datetime import datetime

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.path_config import get_suggestions_dir

def parse_reddit_date(post_data):
    if isinstance(post_data.get('data', {}).get('created_utc'), (int, float)):
        try:
            return datetime.fromtimestamp(post_data['data']['created_utc'])
        except:
            return datetime.now()
    return datetime.now()

def filter_and_sort_reddit_content(scraped_file_path: str, profile_name: str) -> Dict[str, Any]:
    profile_props = PROFILES[profile_name].get('properties', {})
    utils_props = profile_props.get('utils', {})
    suggestions_props = utils_props.get('suggestions', {})
    content_filter = suggestions_props.get('content_filter', {})

    min_age_days = content_filter.get('min_age_days', 0)
    max_age_days = content_filter.get('max_age_days', 7)
    min_score = content_filter.get('min_score', 10)
    max_posts_per_subreddit = content_filter.get('max_posts_per_subreddit', 10)
    max_posts = content_filter.get('max_posts', 15)

    try:
        with open(scraped_file_path, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load scraped data: {e}"}

    scraped_posts = scraped_data.get('scraped_reddit_posts', [])
    if not scraped_posts:
        return {"error": "No Reddit posts found in scraped data"}

    now = datetime.now()

    posts_by_subreddit = {}
    for post in scraped_posts:
        subreddit = post.get('data', {}).get('subreddit', '')

        if not subreddit:
            subreddit = 'unknown'

        if subreddit not in posts_by_subreddit:
            posts_by_subreddit[subreddit] = []
        posts_by_subreddit[subreddit].append(post)

    all_top_posts = []
    subreddit_stats = {}

    for subreddit, subreddit_posts in posts_by_subreddit.items():
        age_filtered_posts = []

        for post in subreddit_posts:
            post_date = parse_reddit_date(post)
            age_days = (now - post_date).days

            if not (min_age_days <= age_days <= max_age_days):
                continue

            score = post.get('engagement', {}).get('score', 0)
            if score < min_score:
                continue

            comments = post.get('engagement', {}).get('num_comments', 0)
            total_engagement = score + comments

            post_copy = post.copy()
            post_copy['total_engagement'] = total_engagement
            post_copy['age_days'] = age_days
            age_filtered_posts.append(post_copy)

        if age_filtered_posts:
            age_filtered_posts.sort(key=lambda x: x['total_engagement'], reverse=True)
            top_posts_from_subreddit = age_filtered_posts[:max_posts_per_subreddit]
            all_top_posts.extend(top_posts_from_subreddit)

            subreddit_stats[subreddit] = {
                "total_posts": len(subreddit_posts),
                "age_filtered_posts": len(age_filtered_posts),
                "selected_top": len(top_posts_from_subreddit),
                "avg_score": sum(p.get('engagement', {}).get('score', 0) for p in top_posts_from_subreddit) / len(top_posts_from_subreddit) if top_posts_from_subreddit else 0,
                "avg_comments": sum(p.get('engagement', {}).get('num_comments', 0) for p in top_posts_from_subreddit) / len(top_posts_from_subreddit) if top_posts_from_subreddit else 0
            }

    all_top_posts.sort(key=lambda x: x['total_engagement'], reverse=True)
    final_top_posts = all_top_posts[:max_posts]

    filtered_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "platform": "reddit",
        "original_scraped_count": len(scraped_posts),
        "subreddits_count": len(posts_by_subreddit),
        "filtered_count": len(final_top_posts),
        "filter_criteria": {
            "min_age_days": min_age_days,
            "max_age_days": max_age_days,
            "min_score": min_score,
            "max_posts_per_subreddit": max_posts_per_subreddit,
            "max_posts": max_posts
        },
        "subreddit_stats": subreddit_stats,
        "filtered_reddit_posts": final_top_posts
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filtered_filename = f"filtered_content_reddit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filtered_filepath = os.path.join(suggestions_dir, filtered_filename)

    try:
        with open(filtered_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": f"Failed to save filtered data: {e}"}

    return {
        "success": True,
        "original_count": len(scraped_posts),
        "subreddits_count": len(posts_by_subreddit),
        "filtered_count": len(final_top_posts),
        "saved_file": filtered_filepath,
        "subreddit_stats": subreddit_stats,
        "top_posts": final_top_posts[:5]
    }

def get_latest_scraped_reddit_file(profile_name: str) -> str:
    """
    Get the latest scraped Reddit content file.
    """
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    reddit_files = [f for f in os.listdir(suggestions_dir) if f.startswith('scraped_content_reddit_') and f.endswith('.json')]
    if not reddit_files:
        return ""

    reddit_files.sort(reverse=True)
    return os.path.join(suggestions_dir, reddit_files[0])

def get_latest_filtered_reddit_file(profile_name: str) -> str:
    """
    Get the latest filtered Reddit content file.
    """
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    filtered_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_reddit_') and f.endswith('.json')]
    if not filtered_files:
        return ""

    filtered_files.sort(reverse=True)
    return os.path.join(suggestions_dir, filtered_files[0])
