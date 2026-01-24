import os
import json

from datetime import datetime

from rich.status import Status
from rich.console import Console

from services.support.logger_util import _log as log

from services.platform.x.support.home import post_approved_home_mode_replies
from services.platform.linkedin.support.reply_utils import post_approved_linkedin_replies

console = Console()

def post_platform_content(platform: str, platform_content: dict, storages: dict, drivers: dict, batch_id: str, verbose: bool = False):
    platform = platform.lower().strip()
    total_posted = 0
    total_failed = 0

    try:
        if platform in ['x', 'twitter']:
            for profile_name, approved_tweets in platform_content.items():
                if not approved_tweets:
                    continue

                if profile_name not in drivers or platform not in drivers[profile_name]:
                    log(f"No driver found for profile {profile_name} on platform {platform}", verbose, is_error=True, log_caller_file="poster.py")
                    total_failed += len(approved_tweets)
                    continue

                driver = drivers[profile_name][platform]
                log(f"Posting {len(approved_tweets)} approved {platform} replies for profile {profile_name}", verbose, log_caller_file="poster.py")

                with Status(f'[white]Posting {len(approved_tweets)} approved {platform} replies for {profile_name}...[/white]', spinner="dots", console=console) as status:
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
                        log(f"Successfully saved {len(clean_tweets)} approved {platform} items to {replies_path}", verbose, log_caller_file="poster.py")
                    except Exception as e:
                        log(f"Failed to save approved {platform} items to JSON for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                        total_failed += len(approved_tweets)
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

                        storage = storages[profile_name][platform]
                        for i, tweet in enumerate(approved_tweets):
                            if i < posted_count:
                                try:
                                    content_id = tweet.get('tweet_id') or tweet.get('content_id')
                                    if content_id:
                                        storage.update_status(
                                            content_id=content_id,
                                            status='posted',
                                            additional_updates={'posted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                                            verbose=verbose
                                        )
                                except Exception as e:
                                    content_id = tweet.get('tweet_id') or tweet.get('content_id') or 'unknown'
                                    log(f"Failed to update status for {platform} item {content_id}: {e}", verbose, is_error=True, log_caller_file="poster.py")

                    except Exception as e:
                        log(f"Failed to post approved {platform} replies for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                        failed_count = len(approved_tweets)

                    status.stop()
                    total_posted += posted_count
                    total_failed += failed_count

                    log(f"Profile {profile_name} {platform} posting complete - Posted: {posted_count}, Failed: {failed_count}", verbose, log_caller_file="poster.py")


        elif platform == 'linkedin':
            for profile_name, approved_posts in platform_content.items():
                if not approved_posts:
                    continue

                if profile_name not in drivers or platform not in drivers[profile_name]:
                    log(f"No driver found for profile {profile_name} on platform {platform}", verbose, is_error=True, log_caller_file="poster.py")
                    total_failed += len(approved_posts)
                    continue

                driver = drivers[profile_name][platform]
                log(f"Posting {len(approved_posts)} approved {platform} replies for profile {profile_name}", verbose, log_caller_file="poster.py")

                with Status(f'[white]Posting {len(approved_posts)} approved {platform} replies for {profile_name}...[/white]', spinner="dots", console=console) as status:
                    replies_dir = os.path.join("tmp", "linkedin", profile_name)
                    os.makedirs(replies_dir, exist_ok=True)
                    replies_path = os.path.join(replies_dir, 'replies.json')

                    clean_posts = []
                    for post in approved_posts:
                        clean_post = {
                            "post_id": post.get("post_id"),
                            "post_urn": post.get("post_urn"),
                            "post_text": post.get("post_text", ""),
                            "profile_url": post.get("profile_url", ""),
                            "author_name": post.get("author_name", ""),
                            "post_date": post.get("post_date"),
                            "media_urls": post.get("media_urls", []),
                            "engagement": {
                                "likes": post.get("likes", 0),
                                "comments": post.get("comments", 0),
                                "reposts": post.get("reposts", 0)
                            },
                            "generated_reply": post.get("generated_reply", ""),
                            "approved": True,
                            "posted": False,
                            "created_at": post.get("created_at")
                        }
                        clean_posts.append(clean_post)

                    posted_count = 0
                    failed_count = 0

                    try:
                        def serialize_datetime(obj):
                            if hasattr(obj, 'isoformat'):
                                return obj.isoformat() + "Z"
                            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

                        with open(replies_path, 'w', encoding='utf-8') as f:
                            json.dump(clean_posts, f, indent=2, ensure_ascii=False, default=serialize_datetime)
                        log(f"Successfully saved {len(clean_posts)} approved {platform} replies to {replies_path}", verbose, log_caller_file="poster.py")
                    except Exception as e:
                        log(f"Failed to save approved {platform} replies to JSON for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                        total_failed += len(approved_posts)
                        continue

                    try:
                        result = post_approved_linkedin_replies(
                            driver=driver,
                            profile_name=profile_name,
                            verbose=verbose,
                            status=status
                        )

                        posted_count = result.get('posted', 0)
                        failed_count = result.get('failed', 0)

                        storage = storages[profile_name][platform]
                        for i, post in enumerate(approved_posts):
                            if i < posted_count:
                                post_id = post.get("data", {}).get("post_id")
                                if post_id:
                                    storage.update_status(
                                        content_id=post_id,
                                        status='posted',
                                        additional_updates={'posted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
                                        verbose=verbose
                                    )

                    except Exception as e:
                        log(f"Failed to post approved {platform} replies for profile {profile_name}: {e}", verbose, is_error=True, log_caller_file="poster.py")
                        failed_count = len(approved_posts)

                    status.stop()
                    total_posted += posted_count
                    total_failed += failed_count

                    log(f"Profile {profile_name} {platform} posting complete - Posted: {posted_count}, Failed: {failed_count}", verbose, log_caller_file="poster.py")

        else:
            log(f"Unsupported platform for posting: {platform}", verbose, is_error=True, log_caller_file="poster.py")

    except Exception as e:
        log(f"Error posting to {platform}: {e}", verbose, is_error=True, log_caller_file="poster.py")

    return total_posted, total_failed

def post_approved_content(profile_names: list, platforms: list, storages: dict, batch_id: str, drivers: dict, verbose: bool = False):
    log(f"Posting approved content for batch: {batch_id} across profiles: {', '.join(profile_names)}", verbose, log_caller_file="poster.py")

    try:
        approved_content_by_platform = {}
        total_approved = 0

        for profile_name in profile_names:
            for platform in platforms:
                storage = storages[profile_name][platform]
                approved_content = storage.pull_approved_content(batch_id, verbose)
                if approved_content:
                    if platform not in approved_content_by_platform:
                        approved_content_by_platform[platform] = {}
                    if profile_name not in approved_content_by_platform[platform]:
                        approved_content_by_platform[platform][profile_name] = []

                    approved_content_by_platform[platform][profile_name].extend(approved_content)
                    total_approved += len(approved_content)
                    log(f"Found {len(approved_content)} approved {platform} items for profile {profile_name}", verbose, log_caller_file="poster.py")

        if total_approved == 0:
            log("No approved content found for posting across any profile or platform", verbose, log_caller_file="poster.py")
            return

        log(f"Found {total_approved} total approved items to post across {len(profile_names)} profiles and {len(platforms)} platforms", verbose, log_caller_file="poster.py")

        total_posted = 0
        total_failed = 0

        for platform in platforms:
            if platform not in approved_content_by_platform:
                continue

            platform_content = approved_content_by_platform[platform]
            posted, failed = post_platform_content(platform, platform_content, storages, drivers, batch_id, verbose)
            total_posted += posted
            total_failed += failed

        log(f"All platforms posting complete - Total Posted: {total_posted}, Total Failed: {total_failed}", verbose, log_caller_file="poster.py")

    except Exception as e:
        log(f"Failed to post approved content: {e}", verbose, is_error=True, log_caller_file="poster.py")
        raise
