import os
import json

from profiles import PROFILES

from datetime import datetime
from rich.status import Status
from rich.console import Console
from typing import List, Dict, Any, Optional
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

def _calculate_reddit_raw_score(item: Dict[str, Any]) -> float:
    score = item.get("engagement", {}).get("score", 0)
    num_comments = item.get("engagement", {}).get("num_comments", 0)
    upvote_ratio = item.get("engagement", {}).get("upvote_ratio", 0.0)
    return score + (num_comments * 5) + (upvote_ratio * 100)

def _calculate_x_raw_score(item: Dict[str, Any]) -> float:
    likes = item.get("engagement", {}).get("likes", 0)
    retweets = item.get("engagement", {}).get("retweets", 0)
    bookmarks = item.get("engagement", {}).get("bookmarks", 0)
    views = item.get("engagement", {}).get("views", 0)
    return likes + (retweets * 10) + (bookmarks * 5) + (views * 0.01)

def _normalize_scores(scores: List[float]) -> List[float]:
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    
    if max_score == min_score:
        return [100.0] * len(scores)
        
    return [((score - min_score) / (max_score - min_score)) * 100 for score in scores]

def add_composite_scores(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> None:
    _log(f"Adding composite scores for profile '{profile_name}'...", verbose, status=status)

    reddit_profile_dir = get_reddit_profile_dir(profile_name)
    latest_reddit_file = get_latest_reddit_data(directory=reddit_profile_dir, prefix="reddit_scraped_data_")

    if latest_reddit_file and os.path.exists(latest_reddit_file):
        _log(f"Loading Reddit data from {latest_reddit_file}", verbose, status=status)
        with open(latest_reddit_file, 'r', encoding='utf-8') as f:
            reddit_data = json.load(f)
        
        reddit_raw_scores = [_calculate_reddit_raw_score(item) for item in reddit_data]
        reddit_normalized_scores = _normalize_scores(reddit_raw_scores)
        
        for i, item in enumerate(reddit_data):
            item["engagement"]["composite_score"] = round(reddit_normalized_scores[i], 4)
            
        _log(f"Updating Reddit data file: {latest_reddit_file}", verbose, status=status)
        with open(latest_reddit_file, 'w', encoding='utf-8') as f:
            json.dump(reddit_data, f, indent=2, ensure_ascii=False)
    else:
        _log(f"No Reddit data file found for profile {profile_name}. Skipping Reddit composite scoring.", verbose, is_error=True, status=status)

    x_profile_config = PROFILES.get(profile_name, {}).get("data", {}).get("x", {})
    x_communities = x_profile_config.get("communities", [])

    if not x_communities:
        _log(f"No X communities specified for profile '{profile_name}'. Skipping X composite scoring.", verbose, is_error=True, status=status)
        return

    all_x_data_with_filepath = []

    for community_name in x_communities:
        x_community_dir = get_community_dir(profile_name)
        latest_x_file = get_latest_x_data(directory=x_community_dir, prefix=community_name + "_")

        if latest_x_file and os.path.exists(latest_x_file):
            _log(f"Loading X data from {latest_x_file} (community: {community_name}) for global normalization.", verbose, status=status)
            with open(latest_x_file, 'r', encoding='utf-8') as f:
                x_data_for_community = json.load(f)
            
            for item in x_data_for_community:
                all_x_data_with_filepath.append({
                    "filepath": latest_x_file,
                    "data": item
                })
        else:
            _log(f"No X data file found for community '{community_name}'. Skipping for global normalization.", verbose, is_error=True, status=status)

    if all_x_data_with_filepath:
        x_raw_scores = [_calculate_x_raw_score(item["data"]) for item in all_x_data_with_filepath]
        x_normalized_scores = _normalize_scores(x_raw_scores)

        updated_x_data_by_filepath = {}
        for i, item_with_filepath in enumerate(all_x_data_with_filepath):
            item_with_filepath["data"]["engagement"]["composite_score"] = round(x_normalized_scores[i], 4)
            filepath = item_with_filepath["filepath"]
            if filepath not in updated_x_data_by_filepath:
                updated_x_data_by_filepath[filepath] = []
            updated_x_data_by_filepath[filepath].append(item_with_filepath["data"])
        
        for filepath, data_to_save in updated_x_data_by_filepath.items():
            _log(f"Updating X data file: {filepath}", verbose, status=status)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    else:
        _log(f"No X data available for global normalization and composite scoring.", verbose, is_error=True, status=status)

    _log("Composite score calculation and saving completed.", verbose, status=status)
