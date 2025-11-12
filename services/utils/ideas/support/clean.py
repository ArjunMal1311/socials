import os
import json

from typing import Optional
from datetime import datetime
from rich.status import Status
from rich.console import Console
from services.support.path_config import get_reddit_profile_dir
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
        original_comments_count = len(post.get("comments", []))
        cleaned_comments = [
            comment for comment in post.get("comments", [])
            if not (comment.get("score") == 1 and comment.get("replies_count") == 0)
        ]
        removed_comments_in_post = original_comments_count - len(cleaned_comments)
        total_removed_comments += removed_comments_in_post
        
        if removed_comments_in_post > 0 and verbose:
            _log(f"  Removed {removed_comments_in_post} comments from post '{post.get("title", "N/A")}'", verbose, status=status)
        
        post["comments"] = cleaned_comments
        cleaned_posts.append(post)
    
    removed_posts_count = original_post_count - len(cleaned_posts)

    _log(f"Cleaned {total_removed_comments} comments from {original_post_count} posts.", verbose, status=status)

    if total_removed_comments > 0 or removed_posts_count > 0:
        _log(f"Updating latest Reddit data file: {latest_file}", verbose, status=status)
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_posts, f, indent=2, ensure_ascii=False)
        _log("Reddit data cleaning complete and file updated.", verbose, status=status)
    else:
        _log("No comments or posts to remove. Reddit data file not updated.", verbose, status=status)
