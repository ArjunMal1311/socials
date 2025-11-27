import os
import json

from datetime import datetime
from rich.console import Console
from typing import Dict, Any, List, Optional, Tuple
from services.support.logger_util import _log as log
from services.support.path_config import get_eternity_schedule_file_path

console = Console()

def _eternity_schedule_paths(profile_name: str) -> Tuple[str, str]:
    schedule_path = get_eternity_schedule_file_path(profile_name)
    schedule_folder = os.path.dirname(schedule_path)
    return schedule_folder, schedule_path


def _load_eternity_schedule(profile_name: str) -> List[Dict[str, Any]]:
    _, schedule_path = _eternity_schedule_paths(profile_name)
    if not os.path.exists(schedule_path):
        return []
    with open(schedule_path, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _save_eternity_schedule(profile_name: str, items: List[Dict[str, Any]]) -> None:
    _, schedule_path = _eternity_schedule_paths(profile_name)
    with open(schedule_path, 'w') as f:
        json.dump(items, f, indent=2)


def _resolve_credentials(profile_name: Optional[str]) -> Tuple[str, str, str, str]:
    prefix = (profile_name or '').strip().upper()
    if not prefix:
        return "", "", "", ""
    consumer_key = os.getenv(f"{prefix}_X_CONSUMER_KEY") or ""
    consumer_secret = os.getenv(f"{prefix}_X_CONSUMER_SECRET") or ""
    access_token = os.getenv(f"{prefix}_X_ACCESS_TOKEN") or ""
    access_token_secret = os.getenv(f"{prefix}_X_ACCESS_TOKEN_SECRET") or ""
    return consumer_key, consumer_secret, access_token, access_token_secret


def _get_tweepy_client(profile_name: Optional[str], verbose: bool = False):
    try:
        import tweepy
    except Exception as e:
        log(f"tweepy is not installed: {e} Install with: pip install tweepy", verbose, is_error=True, log_caller_file="post_approved_tweets.py")
        return None

    consumer_key, consumer_secret, access_token, access_token_secret = _resolve_credentials(profile_name)

    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        scope_hint = (profile_name or '').strip().upper() or 'PROFILE'
        log(
            f"Twitter API keys missing for profile {scope_hint}.\n" +
            f"Set these environment variables: {scope_hint}_X_CONSUMER_KEY, {scope_hint}_X_CONSUMER_SECRET, {scope_hint}_X_ACCESS_TOKEN, {scope_hint}_X_ACCESS_TOKEN_SECRET",
            verbose, is_error=True, log_caller_file="post_approved_tweets.py"
        )
        return None

    try:
        client = tweepy.Client(
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        return client
    except Exception as e:
        log(f"Failed to create tweepy client: {e}", verbose, is_error=True, log_caller_file="post_approved_tweets.py")
        return None


def post_tweet_reply(tweet_id: str, reply_text: str, profile_name: Optional[str] = None, verbose: bool = False) -> bool:
    log(f"Attempting to post reply to tweet ID {tweet_id}: '{reply_text[:80]}'", verbose, log_caller_file="post_approved_tweets.py")
    client = _get_tweepy_client(profile_name, verbose=verbose)
    if not client:
        return False
    try:
        response = client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        log(f"Successfully posted reply to {tweet_id}", verbose, log_caller_file="post_approved_tweets.py")
        return True
    except Exception as e:
        log(f"Twitter API error posting reply to {tweet_id}: {e}", verbose, is_error=True, log_caller_file="post_approved_tweets.py")
        return False


def post_approved_replies(profile_name: str, limit: Optional[int] = None, mode: str = "eternity", verbose: bool = False) -> Dict[str, Any]:
    items = _load_eternity_schedule(profile_name)
    if not items:
        return {"processed": 0, "posted": 0, "failed": 0}

    approved = [it for it in items if str(it.get('status', '')).lower() == 'approved']
    if limit is not None:
        approved = approved[:max(0, int(limit))]

    posted = 0
    failed = 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for it in approved:
        tweet_id = it.get('tweet_id')
        reply = it.get('generated_reply')
        if not tweet_id or not reply:
            failed += 1
            continue
        ok = post_tweet_reply(str(tweet_id), str(reply), profile_name=profile_name, verbose=verbose)
        if ok:
            posted += 1
            it['status'] = 'posted'
            it['posted_date'] = now_str
        else:
            failed += 1

    _save_eternity_schedule(profile_name, items)

    return {"processed": len(approved), "posted": posted, "failed": failed} 


def check_profile_credentials(profile_name: str, verbose: bool = False) -> Dict[str, Any]:
    prefix = (profile_name or '').strip().upper()
    vars_required = [
        f"{prefix}_X_CONSUMER_KEY",
        f"{prefix}_X_CONSUMER_SECRET",
        f"{prefix}_X_ACCESS_TOKEN",
        f"{prefix}_X_ACCESS_TOKEN_SECRET",
    ]
    results: Dict[str, Any] = {"profile": prefix, "vars": {}, "ok": True}
    for var in vars_required:
        val = os.getenv(var) or ""
        last4 = val[-4:] if val else ""
        present = bool(val)
        results["vars"][var] = {"present": present, "last4": last4}
        if not present:
            results["ok"] = False
    return results 