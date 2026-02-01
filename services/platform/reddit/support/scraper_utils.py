import os
import json

from datetime import datetime
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.path_config import ensure_dir_exists, get_reddit_profile_dir

from services.platform.reddit.support.data_formatter import format_reddit_post
from services.platform.reddit.support.reddit_api_utils import initialize_praw, get_subreddit_posts, get_post_comments

console = Console()


def run_reddit_scraper(profile_name: str, status: Optional[Status] = None, verbose: bool = False) -> List[Dict[str, Any]]:
    load_dotenv()
    
    profile_config = PROFILES.get(profile_name, {})
    profile_props = profile_config.get('properties', {})
    platform_props = profile_props.get('platform', {})
    reddit_config = platform_props.get("reddit", {})

    if not reddit_config:
        log(f"No Reddit configuration found for profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []

    subreddits = reddit_config.get("subreddits", [])
    time_filters = reddit_config.get("time_filter", ["hot"])
    min_comments = reddit_config.get("min_comments", 0)
    include_comments = reddit_config.get("include_comments", False)
    max_posts = reddit_config.get("max_posts", 25)

    if not subreddits:
        log(f"No subreddits specified for profile '{profile_name}'.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []

    reddit_instance = initialize_praw(profile_name, verbose=verbose)
    if not reddit_instance:
        return []
        
    all_formatted_posts = []

    for subreddit_name in subreddits:
        for time_filter in time_filters:
            if status:
                status.update(f"[white]Scraping r/{subreddit_name} ({time_filter} posts)...[/white]")
            log(f"Scraping r/{subreddit_name} ({time_filter} posts)...", verbose, status=status, log_caller_file="scraper_utils.py")
            raw_posts = get_subreddit_posts(profile_name, reddit_instance, subreddit_name, time_filter, limit=max_posts, status=status, verbose=verbose)
            
            filtered_posts = [post for post in raw_posts if post.get("num_comments", 0) >= min_comments]
            log(f"Found {len(filtered_posts)} posts from r/{subreddit_name} ({time_filter}) with >= {min_comments} comments.", verbose, status=status, log_caller_file="scraper_utils.py")

            posts_with_comments = []
            if include_comments:
                for post in filtered_posts:
                    post_comments = get_post_comments(profile_name, reddit_instance, post["id"], status=status, verbose=verbose)
                    posts_with_comments.append(format_reddit_post(post, time_filter, include_comments, post_comments))
            else:
                for post in filtered_posts:
                    posts_with_comments.append(format_reddit_post(post, time_filter, include_comments))
            
            all_formatted_posts.extend(posts_with_comments)

    reddit_output_dir = get_reddit_profile_dir(profile_name)
    ensure_dir_exists(reddit_output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(reddit_output_dir, f"reddit_scraped_data_{timestamp}.json")

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_formatted_posts, f, indent=2, ensure_ascii=False)
        log(f"Reddit scraped data saved to {output_file}", verbose, status=status, log_caller_file="scraper_utils.py")
    except Exception as e:
        log(f"Error saving Reddit scraped data to {output_file}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")

    return all_formatted_posts
