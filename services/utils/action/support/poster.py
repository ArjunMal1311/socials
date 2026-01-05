import os
import json

from datetime import datetime

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.x.support.home import post_approved_home_mode_replies

console = Console()

def post_approved_content(profile_name: str, storage, batch_id: str, driver, verbose: bool = False):
    log(f"Posting approved content for batch: {batch_id}", verbose, log_caller_file="poster.py")

    try:
        approved_tweets = storage.pull_approved_content(batch_id, verbose)

        if not approved_tweets:
            log("No approved tweets found for posting", verbose, log_caller_file="poster.py")
            return

        log(f"Found {len(approved_tweets)} approved tweets to post", verbose, log_caller_file="poster.py")

        if profile_name not in PROFILES:
            raise ValueError(f"Profile '{profile_name}' not found in PROFILES")

        profile_props = PROFILES[profile_name].get('properties', {})
        headless = profile_props.get('headless', True)

        with Status(f'[white]Posting {len(approved_tweets)} approved replies...[/white]', spinner="dots", console=console) as status:
            posted_count = 0
            failed_count = 0

            replies_dir = os.path.join("tmp", "replies", profile_name)
            os.makedirs(replies_dir, exist_ok=True)
            replies_path = os.path.join(replies_dir, 'replies.json')

            clean_tweets = []
            for tweet in approved_tweets:
                clean_tweet = {}
                for key, value in tweet.items():
                    if isinstance(value, datetime):
                        clean_tweet[key] = value.isoformat()
                    else:
                        clean_tweet[key] = value
                clean_tweet['status'] = 'approved'
                clean_tweets.append(clean_tweet)

            try:
                with open(replies_path, 'w', encoding='utf-8') as f:
                    json.dump(clean_tweets, f, indent=2, ensure_ascii=False)
                log(f"Successfully saved {len(clean_tweets)} approved tweets to {replies_path}", verbose, log_caller_file="poster.py")
            except Exception as e:
                log(f"Failed to save approved tweets to JSON: {e}", verbose, is_error=True, log_caller_file="poster.py")
                raise

            try:
                result = post_approved_home_mode_replies(
                    driver=driver,
                    profile_name=profile_name,
                    post_via_api=False,
                    verbose=verbose
                )

                posted_count = result.get('posted', 0)
                failed_count = result.get('failed', 0)

                for i, tweet in enumerate(approved_tweets):
                    if i < posted_count:
                        try:
                            storage.update_status(
                                content_id=tweet['tweet_id'],
                                status='posted',
                                additional_updates={'posted_at': '2024-01-01 12:00:00'},
                                verbose=verbose
                            )
                        except Exception as e:
                            log(f"Failed to update status for tweet {tweet['tweet_id']}: {e}", verbose, is_error=True, log_caller_file="poster.py")

            except Exception as e:
                log(f"Failed to post approved replies: {e}", verbose, is_error=True, log_caller_file="poster.py")
                failed_count = len(approved_tweets)

            status.stop()

        log(f"Posting complete - Posted: {posted_count}, Failed: {failed_count}", verbose, log_caller_file="poster.py")

    except Exception as e:
        log(f"Failed to post approved content: {e}", verbose, is_error=True, log_caller_file="poster.py")
        raise
