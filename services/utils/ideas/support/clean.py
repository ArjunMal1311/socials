import os
import json

from profiles import PROFILES

from rich.status import Status
from rich.console import Console
from typing import Optional, List, Dict, Any
from services.support.logger_util import _log as log
from services.support.path_config import get_reddit_profile_dir, get_community_dir
from services.platform.x.support.file_manager import get_latest_dated_json_file as get_latest_x_data
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data

console = Console()

def clean_reddit_data(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> None:
    log("Cleaning Reddit data...", verbose, status=status, log_caller_file="clean.py")

    profile_dir = get_reddit_profile_dir(profile_name)
    latest_file = get_latest_reddit_data(directory=profile_dir, prefix="reddit_scraped_data_")

    if not latest_file or not os.path.exists(latest_file):
        log(f"No latest Reddit data file found for profile {profile_name}. Skipping cleaning.", verbose, is_error=True, status=status, log_caller_file="clean.py")
        return

    log(f"Loading data from {latest_file} for cleaning.", verbose, status=status, log_caller_file="clean.py")
    with open(latest_file, 'r', encoding='utf-8') as f:
        reddit_data = json.load(f)

    original_post_count = len(reddit_data)
    total_removed_comments = 0
    cleaned_posts = []

    for post in reddit_data:
        original_comments_count = len(post.get("data", {}).get("comments", []))
        cleaned_comments = [
            comment for comment in post.get("data", {}).get("comments", [])
            if not (comment.get("score", 0) < 5)
        ]
        removed_comments_in_post = original_comments_count - len(cleaned_comments)
        total_removed_comments += removed_comments_in_post
        
        if removed_comments_in_post > 0 and verbose:
            log(f"  Removed {removed_comments_in_post} comments from post '{post.get("data", {}).get("title", "N/A")}'", verbose, status=status, log_caller_file="clean.py")
        
        post["data"]["comments"] = cleaned_comments
        cleaned_posts.append(post)
    
    log(f"Processed {original_post_count} posts. No posts were removed based on score in this function.", verbose, status=status, log_caller_file="clean.py")
    log(f"Cleaned {total_removed_comments} comments from {len(cleaned_posts)} posts.", verbose, status=status, log_caller_file="clean.py")

    if total_removed_comments > 0:
        log(f"Updating latest Reddit data file: {latest_file}", verbose, status=status, log_caller_file="clean.py")
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_posts, f, indent=2, ensure_ascii=False)
        log("Reddit data cleaning complete and file updated.", verbose, status=status, log_caller_file="clean.py")
    else:
        log("No comments or posts to remove. Reddit data file not updated.", verbose, status=status, log_caller_file="clean.py")
    return cleaned_posts

def clean_x_data(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> List[Dict[str, Any]]:
    log("Cleaning X data...", verbose, status=status, log_caller_file="clean.py")

    profile_config = PROFILES.get(profile_name, {})
    x_config = profile_config.get("data", {}).get("x", {})
    communities = x_config.get("communities", [])
    
    if not communities:
        log(f"No communities specified for X platform in profile '{profile_name}'. Cannot clean X data.", verbose, is_error=True, status=status, log_caller_file="clean.py")
        return []

    all_cleaned_x_data = []

    for community_name in communities:
        community_prefix = community_name
        profile_dir = get_community_dir(profile_name)
        latest_file = get_latest_x_data(directory=profile_dir, prefix=community_prefix + "_")

        if not latest_file or not os.path.exists(latest_file):
            log(f"No latest X data file found for profile {profile_name} with prefix '{community_prefix}'. Skipping cleaning for this community.", verbose, is_error=True, status=status, log_caller_file="clean.py")
            continue

        log(f"Loading data from {latest_file} for cleaning (community: {community_name}).", verbose, status=status, log_caller_file="clean.py")
        with open(latest_file, 'r', encoding='utf-8') as f:
            x_data = json.load(f)

        original_tweet_count = len(x_data)
        log(f"Original tweet count for community '{community_name}': {original_tweet_count}", verbose, status=status, log_caller_file="clean.py")
        
        cleaned_tweets = []
        for tweet in x_data:
            likes = tweet.get("engagement", {}).get("likes", 0)
            log(f"  Processing tweet ID '{tweet.get("data", {}).get("tweet_id", "N/A")}' with {likes} likes.", verbose, status=status, log_caller_file="clean.py")
            if likes >= 20:
                cleaned_tweets.append(tweet)
            else:
                log(f"  Removing tweet ID '{tweet.get("data", {}).get("tweet_id", "N/A")}' due to {likes} likes (less than 20).", verbose, status=status, log_caller_file="clean.py")

        removed_tweet_count = original_tweet_count - len(cleaned_tweets)

        log(f"Processed {original_tweet_count} tweets for community '{community_name}'. Removed {removed_tweet_count} tweets with less than 20 likes.", verbose, status=status, log_caller_file="clean.py")

        if removed_tweet_count > 0:
            log(f"Updating latest X data file: {latest_file} (community: {community_name})", verbose, status=status, log_caller_file="clean.py")
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_tweets, f, indent=2, ensure_ascii=False)
            log(f"X data cleaning complete and file updated for community '{community_name}'.", verbose, status=status, log_caller_file="clean.py")
        else:
            log(f"No tweets to remove for community '{community_name}'. X data file not updated.", verbose, status=status, log_caller_file="clean.py")
        
        all_cleaned_x_data.extend(cleaned_tweets)

    return all_cleaned_x_data
