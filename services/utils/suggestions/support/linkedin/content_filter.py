import os
import sys
import json

from typing import Dict, Any
from datetime import datetime

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.path_config import get_suggestions_dir

def parse_linkedin_date(post_data):
    if isinstance(post_data.get('post_date'), str):
        try:
            dt = datetime.fromisoformat(post_data['post_date'].replace('Z', '+00:00'))
            return dt.replace(tzinfo=None)
        except Exception as e:
            try:
                return datetime.strptime(post_data['post_date'], '%Y-%m-%d %H:%M:%S')
            except:
                return datetime.now()
    return datetime.now()

def filter_and_sort_linkedin_content(scraped_file_path: str, profile_name: str) -> Dict[str, Any]:
    profile_props = PROFILES[profile_name].get('properties', {})
    content_filter = profile_props.get('content_filter', {})

    min_age_days = content_filter.get('min_age_days', 0)
    max_age_days = content_filter.get('max_age_days', 30)
    max_posts_per_profile = content_filter.get('max_posts_per_profile', 5)
    max_posts = content_filter.get('max_posts', 25)

    try:
        with open(scraped_file_path, 'r', encoding='utf-8') as f:
            scraped_data = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load scraped data: {e}"}

    scraped_posts = scraped_data.get('scraped_posts', [])
    if not scraped_posts:
        return {"error": "No posts found in scraped data"}

    now = datetime.now()

    posts_by_profile = {}
    for post in scraped_posts:
        profile_url = post.get('data', {}).get('profile_url', '')
        username = post.get('data', {}).get('author_name', '')

        if not username and profile_url:
            try:
                username = profile_url.split('/')[-1] or profile_url.split('/')[-2]
            except:
                username = 'unknown'
        elif not username:
            username = 'unknown'

        if username not in posts_by_profile:
            posts_by_profile[username] = []
        posts_by_profile[username].append(post)

    all_top_posts = []
    profile_stats = {}

    for username, profile_posts in posts_by_profile.items():
        age_filtered_posts = []

        for post in profile_posts:
            post_date = parse_linkedin_date(post.get('data', {}))
            age_days = (now - post_date).days

            if not (min_age_days <= age_days <= max_age_days):
                continue

            likes = post.get('engagement', {}).get('likes', 0)
            comments = post.get('engagement', {}).get('comments', 0)
            reposts = post.get('engagement', {}).get('reposts', 0)
            total_engagement = likes + comments + reposts

            post_copy = post.copy()
            post_copy['total_engagement'] = total_engagement
            post_copy['age_days'] = age_days
            age_filtered_posts.append(post_copy)

        if age_filtered_posts:
            age_filtered_posts.sort(key=lambda x: x['total_engagement'], reverse=True)
            top_posts_from_profile = age_filtered_posts[:max_posts_per_profile]
            all_top_posts.extend(top_posts_from_profile)

            profile_stats[username] = {
                "total_posts": len(profile_posts),
                "age_filtered_posts": len(age_filtered_posts),
                "selected_top": len(top_posts_from_profile),
                "avg_engagement": sum(p['total_engagement'] for p in top_posts_from_profile) / len(top_posts_from_profile) if top_posts_from_profile else 0
            }

    all_top_posts.sort(key=lambda x: x['total_engagement'], reverse=True)
    final_top_posts = all_top_posts[:max_posts]

    filtered_data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "original_scraped_count": len(scraped_posts),
        "profiles_count": len(posts_by_profile),
        "filtered_count": len(final_top_posts),
        "filter_criteria": {
            "min_age_days": min_age_days,
            "max_age_days": max_age_days,
            "max_posts_per_profile": max_posts_per_profile,
            "max_posts": max_posts
        },
        "profile_stats": profile_stats,
        "filtered_posts": final_top_posts
    }

    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    filtered_filename = f"filtered_content_linkedin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filtered_filepath = os.path.join(suggestions_dir, filtered_filename)

    try:
        with open(filtered_filepath, 'w', encoding='utf-8') as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {"error": f"Failed to save filtered data: {e}"}

    return {
        "success": True,
        "original_count": len(scraped_posts),
        "profiles_count": len(posts_by_profile),
        "filtered_count": len(final_top_posts),
        "saved_file": filtered_filepath,
        "profile_stats": profile_stats,
        "top_posts": final_top_posts[:5]
    }

def get_latest_scraped_linkedin_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    scraped_files = [f for f in os.listdir(suggestions_dir) if f.startswith('scraped_content_linkedin_') and f.endswith('.json')]
    if not scraped_files:
        return ""

    scraped_files.sort(reverse=True)
    return os.path.join(suggestions_dir, scraped_files[0])

def get_latest_filtered_linkedin_file(profile_name: str) -> str:
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return ""

    filtered_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_linkedin_') and f.endswith('.json')]
    if not filtered_files:
        return ""

    filtered_files.sort(reverse=True)
    return os.path.join(suggestions_dir, filtered_files[0])
