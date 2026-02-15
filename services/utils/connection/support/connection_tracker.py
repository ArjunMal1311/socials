import os
import json

from datetime import datetime
from typing import Dict, Any, List

from services.support.logger_util import _log as log
from services.support.path_config import get_connections_dir

def get_connection_tracking_file_path(profile_name: str, platform: str = "linkedin") -> str:
    connections_dir = get_connections_dir(profile_name)
    return os.path.join(connections_dir, f"{platform}_connection_requests.json")

def load_connection_tracking(profile_name: str, platform: str = "linkedin") -> Dict[str, Any]:
    tracking_file = get_connection_tracking_file_path(profile_name, platform)

    if os.path.exists(tracking_file):
        try:
            with open(tracking_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                log(f"Loaded existing connection tracking with {len(data)} entries", False, log_caller_file="connection_tracker.py")
                return data
        except Exception as e:
            log(f"Error loading connection tracking file: {e}", False, is_error=True, log_caller_file="connection_tracker.py")

    return {}

def save_connection_tracking(profile_name: str, tracking_data: Dict[str, Any], platform: str = "linkedin") -> None:
    tracking_file = get_connection_tracking_file_path(profile_name, platform)

    try:
        with open(tracking_file, 'w', encoding='utf-8') as f:
            json.dump(tracking_data, f, indent=2, ensure_ascii=False)
        log(f"Saved connection tracking with {len(tracking_data)} entries", False, log_caller_file="connection_tracker.py")
    except Exception as e:
        log(f"Error saving connection tracking file: {e}", False, is_error=True, log_caller_file="connection_tracker.py")

def is_already_processed(tracking_data: Dict[str, Any], platform: str, target_id: str) -> bool:
    return platform in tracking_data and target_id in tracking_data[platform]

def mark_as_processed(tracking_data: Dict[str, Any], platform: str, target_id: str, success: bool, source: str = "product_hunt", connection_type: str = "connection_request") -> None:
    if platform not in tracking_data:
        tracking_data[platform] = {}
    tracking_data[platform][target_id] = {
        "action": connection_type,
        "timestamp": datetime.now().isoformat(),
        "success": success,
        "source": source
    }

def get_pending_urls(all_urls: List[str], tracking_data: Dict[str, Any], platform: str) -> List[str]:
    pending = []
    for url in all_urls:
        if not is_already_processed(tracking_data, platform, url):
            pending.append(url)

    log(f"Found {len(pending)} pending URLs for {platform} out of {len(all_urls)} total", False, log_caller_file="connection_tracker.py")
    return pending

def get_stats(tracking_data: Dict[str, Any], platform: str) -> Dict[str, int]:
    total = len(tracking_data.get(platform, {}))
    successful = sum(1 for entry in tracking_data.get(platform, {}).values() if entry.get("success", False))
    failed = total - successful

    return {
        "total_processed": total,
        "successful": successful,
        "failed": failed
    }
