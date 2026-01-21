import json

from typing import Dict, List, Any
from .base import BaseTwitterStorage
from services.support.postgres_util import get_postgres_connection, update_data

class TwitterActionStorage(BaseTwitterStorage):
    def _get_table_name(self) -> str:
        return f"{self.profile_name}_tweets"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "batch_id": "TEXT NOT NULL",
            "profile_name": "TEXT NOT NULL",
            "tweet_id": "TEXT NOT NULL UNIQUE",
            "tweet_url": "TEXT",
            "tweet_text": "TEXT NOT NULL",
            "tweet_date": "TIMESTAMP",
            "likes": "INTEGER DEFAULT 0",
            "retweets": "INTEGER DEFAULT 0",
            "replies": "INTEGER DEFAULT 0",
            "views": "INTEGER DEFAULT 0",
            "bookmarks": "INTEGER DEFAULT 0",
            "profile_image_url": "TEXT",
            "media_urls": "JSONB",
            "status": "TEXT DEFAULT 'pending_review'",
            "generated_reply": "TEXT",
            "approved_at": "TIMESTAMP",
            "posted_at": "TIMESTAMP",
            "created_at": "TIMESTAMP DEFAULT NOW()",
            "updated_at": "TIMESTAMP DEFAULT NOW()"
        }

    def push_content(self, content: List[Dict[str, Any]], batch_id: str, verbose: bool = False) -> bool:
        mapped_content = []
        for tweet in content:
            mapped_tweet = self._map_tweet_data(tweet)
            mapped_tweet["generated_reply"] = tweet.get("generated_reply")
            mapped_content.append(mapped_tweet)

        return super().push_content(mapped_content, batch_id, verbose)

    def update_status(self, content_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            updates = {'status': status}
            if additional_updates:
                updates.update(additional_updates)

            success = update_data(conn, self.table_name, updates, "tweet_id = %s", (content_id,), verbose)

            conn.close()
            return success

        except Exception as e:
            from services.support.logger_util import _log as log
            log(f"Failed to update tweet {content_id} status: {e}", verbose, is_error=True, log_caller_file="action.py")
            return False

    def _map_tweet_data(self, tweet: Dict[str, Any]) -> Dict[str, Any]:
        media_urls = tweet.get("media_urls", [])
        if not media_urls:
            print(f"DEBUG: Empty media_urls for tweet {tweet.get('tweet_id', 'unknown')}, available keys: {list(tweet.keys())}")

        return {
            "tweet_id": tweet.get("tweet_id"),
            "tweet_url": tweet.get("tweet_url"),
            "tweet_text": tweet.get("tweet_text"),
            "tweet_date": tweet.get("tweet_date"),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "views": tweet.get("views", 0),
            "bookmarks": tweet.get("bookmarks", 0),
            "profile_image_url": tweet.get("profile_image_url"),
            "media_urls": json.dumps(media_urls)
        }

    def _unmap_tweet_data(self, tweet: Dict[str, Any]) -> Dict[str, Any]:
        media_urls = tweet.get("media_urls")
        if isinstance(media_urls, str):
            media_urls = json.loads(media_urls)
        elif media_urls is None:
            media_urls = []

        return {
            "tweet_id": tweet["tweet_id"],
            "tweet_url": tweet["tweet_url"],
            "tweet_text": tweet["tweet_text"],
            "tweet_date": tweet["tweet_date"],
            "likes": tweet["likes"],
            "retweets": tweet["retweets"],
            "replies": tweet["replies"],
            "views": tweet["views"],
            "bookmarks": tweet["bookmarks"],
            "profile_image_url": tweet["profile_image_url"],
            "media_urls": media_urls
        }

    def pull_approved_content(self, batch_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        approved_tweets = super().pull_approved_content(batch_id, verbose)

        mapped_tweets = []
        for tweet in approved_tweets:
            mapped_tweet = self._unmap_tweet_data(tweet)
            mapped_tweet["generated_reply"] = tweet.get("generated_reply")
            mapped_tweet["profile_name"] = tweet.get("profile_name")
            mapped_tweets.append(mapped_tweet)

        return mapped_tweets
