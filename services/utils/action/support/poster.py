import os
import json

from datetime import datetime

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.platform.x.support.home import post_approved_home_mode_replies

console = Console()

def post_approved_content(profile_names: list, storages: dict, batch_id: str, drivers: dict, verbose: bool = False):
    log(f"Posting approved content for batch: {batch_id} across profiles: {', '.join(profile_names)}", verbose, log_caller_file="poster.py")

    try:
        all_approved_tweets = []
        for profile_name in profile_names:
            storage = storages[profile_name]
            approved_tweets = storage.pull_approved_content(batch_id, verbose)
            if approved_tweets:
                all_approved_tweets.extend(approved_tweets)
                log(f"Found {len(approved_tweets)} approved tweets for profile {profile_name}", verbose, log_caller_file="poster.py")

        if not all_approved_tweets:
            log("No approved tweets found for posting across any profile", verbose, log_caller_file="poster.py")
            return

        log(f"Found {len(all_approved_tweets)} total approved tweets to post across {len(profile_names)} profiles", verbose, log_caller_file="poster.py")

        tweets_by_profile = {}
        for tweet in all_approved_tweets:
            profile_name = tweet.get('profile_name')
            if profile_name not in tweets_by_profile:
                tweets_by_profile[profile_name] = []
            tweets_by_profile[profile_name].append(tweet)

        for profile_name in profile_names:
            if profile_name not in PROFILES:
                raise ValueError(f"Profile '{profile_name}' not found in PROFILES")
            if profile_name not in drivers:
                raise ValueError(f"No driver found for profile '{profile_name}'")

        total_posted = 0
        total_failed = 0

        for profile_name in profile_names:
            profile_tweets = tweets_by_profile.get(profile_name, [])
            if not profile_tweets:
                log(f"No approved tweets for profile {profile_name}", verbose, log_caller_file="poster.py")
                continue

            driver = drivers[profile_name]
            log(f"Posting {len(profile_tweets)} approved replies for profile {profile_name}", verbose, log_caller_file="poster.py")

            with Status(f'[white]Posting {len(profile_tweets)} approved replies for {profile_name}...[/white]', spinner="dots", console=console) as status:
                posted_count = 0
                failed_count = 0

                replies_dir = os.path.join("tmp", "replies", profile_name)
                os.makedirs(replies_dir, exist_ok=True)
                replies_path = os.path.join(replies_dir, 'replies.json')

                clean_tweets = []
                for tweet in profile_tweets:
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
                    log(f"Failed to save approved tweets to JSON for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                    total_failed += len(profile_tweets)
                    continue

                try:
                    result = post_approved_home_mode_replies(
                        driver=driver,
                        profile_name=profile_name,
                        post_via_api=False,
                        verbose=verbose
                    )

                    posted_count = result.get('posted', 0)
                    failed_count = result.get('failed', 0)

                    for i, tweet in enumerate(profile_tweets):
                        if i < posted_count:
                            try:
                                storage.update_status(
                                    content_id=tweet['tweet_id'],
                                    status='posted',
                                    additional_updates={'posted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                                    verbose=verbose
                                )
                            except Exception as e:
                                log(f"Failed to update status for tweet {tweet['tweet_id']}: {e}", verbose, is_error=True, log_caller_file="poster.py")

                except Exception as e:
                    log(f"Failed to post approved replies for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                    failed_count = len(profile_tweets)

                status.stop()

                total_posted += posted_count
                total_failed += failed_count

                log(f"Profile {profile_name} posting complete - Posted: {posted_count}, Failed: {failed_count}", verbose, log_caller_file="poster.py")

        log(f"All profiles posting complete - Total Posted: {total_posted}, Total Failed: {total_failed}", verbose, log_caller_file="poster.py")

    except Exception as e:
        log(f"Failed to post approved content: {e}", verbose, is_error=True, log_caller_file="poster.py")
        raise
