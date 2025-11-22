import os
import json

from profiles import PROFILES

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import Optional, List, Dict, Any
from services.support.path_config import get_reddit_profile_dir, get_community_dir
from services.platform.x.support.file_manager import get_latest_dated_json_file as get_latest_x_data
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data

console = Console()

def _log(message: str, verbose: bool = False, is_error: bool = False, status: Optional[Status] = None) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if is_error:
        level = "ERROR"
        style = "bold red"
    else:
        level = "INFO"
        style = "white"
    
    formatted_message = f"[{timestamp}] [{level}] {message}"
    
    if verbose or is_error:
        console.print(formatted_message, style=style)
    
    if status:
        status.update(formatted_message)

def clean_reddit_data(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> None:
    _log("Cleaning Reddit data...", verbose, status=status)

    profile_dir = get_reddit_profile_dir(profile_name)
    latest_file = get_latest_reddit_data(directory=profile_dir, prefix="reddit_scraped_data_")

    if not latest_file or not os.path.exists(latest_file):
        _log(f"No latest Reddit data file found for profile {profile_name}. Skipping cleaning.", verbose, is_error=True, status=status)
        return

    _log(f"Loading data from {latest_file} for cleaning.", verbose, status=status)
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
            _log(f"  Removed {removed_comments_in_post} comments from post '{post.get("data", {}).get("title", "N/A")}'", verbose, status=status)
        
        post["data"]["comments"] = cleaned_comments
        cleaned_posts.append(post)
    
    _log(f"Processed {original_post_count} posts. No posts were removed based on score in this function.", verbose, status=status)
    _log(f"Cleaned {total_removed_comments} comments from {len(cleaned_posts)} posts.", verbose, status=status)

    if total_removed_comments > 0:
        _log(f"Updating latest Reddit data file: {latest_file}", verbose, status=status)
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_posts, f, indent=2, ensure_ascii=False)
        _log("Reddit data cleaning complete and file updated.", verbose, status=status)
    else:
        _log("No comments or posts to remove. Reddit data file not updated.", verbose, status=status)
    return cleaned_posts

def clean_x_data(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> List[Dict[str, Any]]:
    _log("Cleaning X data...", verbose, status=status)

    profile_config = PROFILES.get(profile_name, {})
    x_config = profile_config.get("data", {}).get("x", {})
    communities = x_config.get("communities", [])
    
    if not communities:
        _log(f"No communities specified for X platform in profile '{profile_name}'. Cannot clean X data.", verbose, is_error=True, status=status)
        return []

    all_cleaned_x_data = []

    for community_name in communities:
        community_prefix = community_name
        profile_dir = get_community_dir(profile_name)
        latest_file = get_latest_x_data(directory=profile_dir, prefix=community_prefix + "_")

        if not latest_file or not os.path.exists(latest_file):
            _log(f"No latest X data file found for profile {profile_name} with prefix '{community_prefix}'. Skipping cleaning for this community.", verbose, is_error=True, status=status)
            continue

        _log(f"Loading data from {latest_file} for cleaning (community: {community_name}).", verbose, status=status)
        with open(latest_file, 'r', encoding='utf-8') as f:
            x_data = json.load(f)

        original_tweet_count = len(x_data)
        _log(f"Original tweet count for community '{community_name}': {original_tweet_count}", verbose, status=status)
        
        cleaned_tweets = []
        for tweet in x_data:
            likes = tweet.get("engagement", {}).get("likes", 0)
            _log(f"  Processing tweet ID '{tweet.get("data", {}).get("tweet_id", "N/A")}' with {likes} likes.", verbose, status=status)
            if likes >= 20:
                cleaned_tweets.append(tweet)
            else:
                _log(f"  Removing tweet ID '{tweet.get("data", {}).get("tweet_id", "N/A")}' due to {likes} likes (less than 20).", verbose, status=status)

        removed_tweet_count = original_tweet_count - len(cleaned_tweets)

        _log(f"Processed {original_tweet_count} tweets for community '{community_name}'. Removed {removed_tweet_count} tweets with less than 20 likes.", verbose, status=status)

        if removed_tweet_count > 0:
            _log(f"Updating latest X data file: {latest_file} (community: {community_name})", verbose, status=status)
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_tweets, f, indent=2, ensure_ascii=False)
            _log(f"X data cleaning complete and file updated for community '{community_name}'.", verbose, status=status)
        else:
            _log(f"No tweets to remove for community '{community_name}'. X data file not updated.", verbose, status=status)
        
        all_cleaned_x_data.extend(cleaned_tweets)

    return all_cleaned_x_data
