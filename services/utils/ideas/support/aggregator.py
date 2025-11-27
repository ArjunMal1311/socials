import os
import json

from profiles import PROFILES

from typing import Optional
from rich.status import Status
from rich.console import Console
from datetime import datetime, timezone
from services.support.logger_util import _log as log
from services.platform.x.support.file_manager import get_latest_dated_json_file as get_latest_x_data
from services.platform.reddit.support.file_manager import get_latest_dated_json_file as get_latest_reddit_data
from services.support.path_config import get_reddit_profile_dir, get_community_dir, get_ideas_aggregated_dir, ensure_dir_exists

console = Console()

def aggregate_platform_data(profile_name: str, verbose: bool = False, status: Optional[Status] = None) -> None:
    log(f"Aggregating platform data for profile '{profile_name}'...", verbose, status=status, log_caller_file="aggregator.py")

    all_items = []
    x_item_count = 0
    reddit_item_count = 0

    reddit_profile_dir = get_reddit_profile_dir(profile_name)
    latest_reddit_file = get_latest_reddit_data(directory=reddit_profile_dir, prefix="reddit_scraped_data_")

    if latest_reddit_file and os.path.exists(latest_reddit_file):
        log(f"Loading Reddit data from {latest_reddit_file}", verbose, status=status, log_caller_file="aggregator.py")
        with open(latest_reddit_file, 'r', encoding='utf-8') as f:
            reddit_data = json.load(f)
        all_items.extend(reddit_data)
        reddit_item_count = len(reddit_data)
    else:
        log(f"No Reddit data file found for profile {profile_name}. Skipping Reddit aggregation.", verbose, is_error=True, status=status, log_caller_file="aggregator.py")

    x_profile_config = PROFILES.get(profile_name, {}).get("data", {}).get("x", {})
    x_communities = x_profile_config.get("communities", [])

    if not x_communities:
        log(f"No X communities specified for profile '{profile_name}'. Skipping X aggregation.", verbose, is_error=True, status=status, log_caller_file="aggregator.py")
    else:
        for community_name in x_communities:
            x_community_dir = get_community_dir(profile_name)
            latest_x_file = get_latest_x_data(directory=x_community_dir, prefix=community_name + "_")

            if latest_x_file and os.path.exists(latest_x_file):
                log(f"Loading X data from {latest_x_file} (community: {community_name})", verbose, status=status, log_caller_file="aggregator.py")
                with open(latest_x_file, 'r', encoding='utf-8') as f:
                    x_data_for_community = json.load(f)
                all_items.extend(x_data_for_community)
                x_item_count += len(x_data_for_community)
            else:
                log(f"No X data file found for community '{community_name}'. Skipping aggregation for this community.", verbose, is_error=True, status=status, log_caller_file="aggregator.py")

    if not all_items:
        log("No data to aggregate from any platform.", verbose, is_error=True, status=status, log_caller_file="aggregator.py")
        return

    total_items = len(all_items)
    aggregated_at = datetime.now(timezone.utc).isoformat()

    all_items.sort(key=lambda x: x.get("engagement", {}).get("composite_score", 0), reverse=True)

    final_aggregated_data = {
        "aggregated_at": aggregated_at,
        "total_items": total_items,
        "sources": {
            "reddit": reddit_item_count,
            "x": x_item_count
        },
        "items": all_items
    }

    output_dir = get_ideas_aggregated_dir(profile_name)
    ensure_dir_exists(output_dir)
    output_file_path = os.path.join(output_dir, "aggregate.json")

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(final_aggregated_data, f, indent=2, ensure_ascii=False)
        log(f"Aggregated data saved to {output_file_path}", verbose, status=status, log_caller_file="aggregator.py")
    except Exception as e:
        log(f"Error saving aggregated data to {output_file_path}: {e}", verbose, is_error=True, status=status, log_caller_file="aggregator.py")
    
    log("Platform data aggregation completed.", verbose, status=status, log_caller_file="aggregator.py")
