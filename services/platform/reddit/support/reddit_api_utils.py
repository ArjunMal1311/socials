import os
import time
import praw

from dotenv import load_dotenv
from rich.console import Console
from typing import List, Dict, Any
from datetime import datetime, timedelta

from services.support.logger_util import _log as log
from services.support.rate_limiter import RateLimiter
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_reddit_log_file_path

console = Console()

_api_call_tracker_instances: Dict[str, APICallTracker] = {}
_rate_limiter_instances: Dict[str, RateLimiter] = {}

def _get_api_trackers(profile_name: str):
    if profile_name not in _api_call_tracker_instances:
        _api_call_tracker_instances[profile_name] = APICallTracker(log_file=get_reddit_log_file_path(profile_name))
    if profile_name not in _rate_limiter_instances:
        _rate_limiter_instances[profile_name] = RateLimiter(rpm_limit=60)
    return _api_call_tracker_instances[profile_name], _rate_limiter_instances[profile_name]

def _handle_rate_limit(profile_name: str, method_name: str, status=None, verbose: bool = False):
    api_call_tracker, rate_limiter = _get_api_trackers(profile_name)
    api_key_suffix = os.getenv("REDDIT_CLIENT_ID")[-4:] if os.getenv("REDDIT_CLIENT_ID") else "N/A"
    while True:
        can_call, reason = api_call_tracker.can_make_call("reddit", method_name, api_key_suffix=api_key_suffix)
        if can_call:
            break
        api_info = api_call_tracker.get_quot_info("reddit", method_name, api_key_suffix=api_key_suffix)
        log(f"Rate limit hit for Reddit API ({method_name}): {reason}. Waiting...", verbose, is_error=True, status=status, api_info=api_info)
        sleep_time = rate_limiter.wait_if_needed(api_key_suffix)
        if sleep_time > 0:
            time.sleep(sleep_time)

def initialize_praw(profile_name: str, verbose: bool = False):
    load_dotenv()
    try:
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "python:socials-scout:v1.0 (by /u/YOUR_REDDIT_USERNAME)")
        username = os.getenv("REDDIT_USERNAME")
        password = os.getenv("REDDIT_PASSWORD")

        if not all([client_id, client_secret]):
            log("Reddit API credentials (client_id, client_secret) are required and not found in .env. PRAW cannot be initialized.", verbose, is_error=True)
            return None

        if not all([username, password]):
            log("Reddit user credentials (username, password) not found in .env. PRAW will be initialized for read-only operations.", verbose, is_error=False)
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
        else:
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                username=username,
                password=password
            )
        log("PRAW initialized successfully.", verbose)
        return reddit
    except Exception as e:
        log(f"Error initializing PRAW: {e}", verbose, is_error=True)
        return None

def get_subreddit_posts(profile_name: str, reddit_instance: praw.Reddit, subreddit_name: str, time_filter: str = "all", limit: int = 100, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    api_key_suffix = os.getenv("REDDIT_CLIENT_ID")[-4:] if os.getenv("REDDIT_CLIENT_ID") else "N/A"
    
    posts_data = []
    api_call_tracker, rate_limiter = _get_api_trackers(profile_name)
    try:
        subreddit = reddit_instance.subreddit(subreddit_name)
        method_name = f"subreddit_{time_filter}"
        
        log(f"Fetching {time_filter} posts from r/{subreddit_name}...", verbose, status=status)
        _handle_rate_limit(profile_name, method_name, status, verbose)

        posts = []
        if time_filter == "hot":
            posts = subreddit.hot(limit=limit)
        elif time_filter == "new":
            posts = subreddit.new(limit=limit)
        elif time_filter == "top":
            posts = subreddit.top(time_filter="all", limit=limit)
        elif time_filter == "rising":
            posts = subreddit.rising(limit=limit)
        elif time_filter == "week":
            posts = subreddit.top(time_filter="week", limit=limit)
        elif time_filter == "day":
            posts = subreddit.top(time_filter="day", limit=limit)
        elif time_filter == "yesterday":
            method_name = "subreddit_top_day"
            _handle_rate_limit(profile_name, method_name, status, verbose)

            today = datetime.now()
            yesterday = today - timedelta(days=1)
            yesterday_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0)
            yesterday_end = datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59)

            log(f"Fetching 'day' posts for custom 'yesterday' filter from r/{subreddit_name}...", verbose, status=status)
            all_day_posts = subreddit.top(time_filter="day", limit=limit)
            filtered_posts = []
            for post in all_day_posts:
                post_utc_dt = datetime.fromtimestamp(post.created_utc)
                if yesterday_start <= post_utc_dt <= yesterday_end:
                    filtered_posts.append(post)
            posts = filtered_posts
            log(f"Filtered {len(posts)} posts for 'yesterday' from r/{subreddit_name}.", verbose, status=status)
        else:
            log(f"Unsupported time filter: {time_filter}", verbose, is_error=True, status=status)
            return []

        for post in posts:
            posts_data.append({
                "id": post.id,
                "title": post.title,
                "url": post.url,
                "author": str(post.author) if post.author else "[deleted]",
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "selftext": post.selftext,
                "is_video": post.is_video,
                "link_flair_text": post.link_flair_text if post.link_flair_text else "",
                "total_awards_received": post.total_awards_received,
                "subreddit": post.subreddit.display_name
            })
        api_call_tracker.record_call("reddit", method_name, api_key_suffix=api_key_suffix, success=True)
        log(f"Fetched {len(posts_data)} {time_filter} posts from r/{subreddit_name}.", verbose, status=status)
    except Exception as e:
        api_call_tracker.record_call("reddit", method_name, api_key_suffix=api_key_suffix, success=False, response=str(e))
        log(f"Error fetching posts from r/{subreddit_name} with filter {time_filter}: {e}", verbose, is_error=True, status=status)
    return posts_data

def get_post_comments(profile_name: str, reddit_instance: praw.Reddit, post_id: str, limit: int = 25, status=None, verbose: bool = False) -> List[Dict[str, Any]]:
    api_key_suffix = os.getenv("REDDIT_CLIENT_ID")[-4:] if os.getenv("REDDIT_CLIENT_ID") else "N/A"
    if not reddit_instance:
        log("Reddit API not initialized.", verbose, is_error=True, status=status)
        return []
    
    comments_data = []
    api_call_tracker, rate_limiter = _get_api_trackers(profile_name)
    try:
        post = reddit_instance.submission(id=post_id)
        method_name = "post_comments"

        log(f"Fetching comments for post {post_id}...", verbose, status=status)
        _handle_rate_limit(profile_name, method_name, status, verbose)

        post.comments.replace_more(limit=0) 
        for comment in post.comments.list()[:limit]:
            comments_data.append({
                "id": comment.id,
                "body": comment.body,
                "author": str(comment.author) if comment.author else "[deleted]",
                "score": comment.score,
                "created_utc": comment.created_utc,
                "is_submitter": comment.is_submitter,
                "replies_count": len(comment.replies) if hasattr(comment, 'replies') else 0,
                "is_stickied": comment.stickied
            })
        api_call_tracker.record_call("reddit", method_name, api_key_suffix=api_key_suffix, success=True)
        log(f"Fetched {len(comments_data)} comments for post {post_id}.", verbose, status=status)
    except Exception as e:
        api_call_tracker.record_call("reddit", method_name, api_key_suffix=api_key_suffix, success=False, response=str(e))
        log(f"Error fetching comments for post {post_id}: {e}", verbose, is_error=True, status=status)
    return comments_data
