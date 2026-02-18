import json

from typing import Dict, List, Any
from services.support.storage.base_storage import BaseStorage

from services.support.logger_util import _log as log
from services.support.postgres_util import get_postgres_connection, update_data

class LinkedInActionStorage(BaseStorage):
    def _get_table_name(self) -> str:
        return f"{self.profile_name}_linkedin"

    def _get_conflict_column(self) -> str:
        return "post_urn"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "batch_id": "TEXT NOT NULL",
            "profile_name": "TEXT NOT NULL",
            "post_id": "TEXT NOT NULL",
            "post_urn": "TEXT NOT NULL UNIQUE",
            "source": "TEXT",
            "scraped_at": "TIMESTAMP",
            "post_text": "TEXT NOT NULL",
            "author_name": "TEXT",
            "author_image": "TEXT",
            "profile_url": "TEXT",
            "post_date": "TIMESTAMP",
            "likes": "INTEGER DEFAULT 0",
            "comments": "INTEGER DEFAULT 0",
            "reposts": "INTEGER DEFAULT 0",
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
        for post in content:
            mapped_post = self._map_linkedin_post_data(post)
            mapped_post["generated_reply"] = post.get("generated_reply")
            mapped_content.append(mapped_post)

        return super().push_content(mapped_content, batch_id, verbose)

    def update_status(self, content_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            updates = {'status': status}
            if additional_updates:
                updates.update(additional_updates)

            success = update_data(conn, self.table_name, updates, "post_id = %s", (content_id,), verbose)

            conn.close()
            return success

        except Exception as e:
            from services.support.logger_util import _log as log
            log(f"Failed to update LinkedIn post {content_id} status: {e}", verbose, is_error=True, log_caller_file="action.py")
            return False

    def _map_linkedin_post_data(self, post: Dict[str, Any]) -> Dict[str, Any]:
        data = post.get("data", {})

        if post.get("post_id") and post.get("post_text"):
            engagement = post.get("engagement", {})
            mapped = {
                "post_id": post.get("post_id"),
                "post_urn": post.get("post_urn"),
                "source": "linkedin_feed",
                "scraped_at": post.get("created_at"),
                "post_text": post.get("post_text"),
                "author_name": post.get("author_name"),
                "author_image": post.get("author_image"),
                "profile_url": post.get("profile_url"),
                "post_date": post.get("post_date"),
                "likes": engagement.get("likes", 0),
                "comments": engagement.get("comments", 0),
                "reposts": engagement.get("reposts", 0),
                "media_urls": json.dumps(post.get("media_urls", []))
            }
            
        else:
            engagement = post.get("engagement", {})
            mapped = {
                "post_id": data.get("post_id"),
                "post_urn": data.get("post_urn"),
                "source": post.get("source"),
                "scraped_at": post.get("scraped_at"),
                "post_text": data.get("text"),
                "author_name": data.get("author_name"),
                "author_image": data.get("author_image"),
                "profile_url": data.get("profile_url"),
                "post_date": data.get("post_date"),
                "likes": engagement.get("likes", 0),
                "comments": engagement.get("comments", 0),
                "reposts": engagement.get("reposts", 0),
                "media_urls": json.dumps(data.get("media_urls", []))
            }

        return mapped

    def _unmap_linkedin_post_data(self, post: Dict[str, Any]) -> Dict[str, Any]:
        media_urls = post.get("media_urls")
        if isinstance(media_urls, str):
            media_urls = json.loads(media_urls)
        elif media_urls is None:
            media_urls = []

        return {
            "post_id": post["post_id"],
            "post_urn": post.get("post_urn"),
            "source": post["source"],
            "scraped_at": post["scraped_at"],
            "data": {
                "post_id": post["post_id"],
                "post_urn": post.get("post_urn"),
                "text": post["post_text"],
                "author_name": post["author_name"],
                "author_image": post.get("author_image", ""),
                "profile_url": post["profile_url"],
                "post_date": post["post_date"]
            },
            "engagement": {
                "likes": post["likes"],
                "comments": post["comments"],
                "reposts": post["reposts"]
            },
            "media_urls": media_urls,
            "generated_reply": post.get("generated_reply"),
            "profile_name": post.get("profile_name")
        }

    def pull_approved_content(self, batch_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        approved_posts = super().pull_approved_content(batch_id, verbose)

        mapped_posts = []
        for post in approved_posts:
            mapped_post = self._unmap_linkedin_post_data(post)
            mapped_post["generated_reply"] = post.get("generated_reply")
            mapped_post["profile_name"] = post.get("profile_name")
            mapped_posts.append(mapped_post)

        return mapped_posts

    def get_all_approved_and_posted_replies(self, verbose: bool = False) -> List[Dict[str, Any]]:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []

            table_name = self.table_name

            query = f"""
                SELECT * FROM {table_name}
                WHERE status IN ('approved', 'posted')
                AND generated_reply IS NOT NULL
                ORDER BY created_at DESC
            """

            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            column_names = [desc[0] for desc in cursor.description]
            results = [dict(zip(column_names, row)) for row in rows]

            cursor.close()
            conn.close()

            log(f"Retrieved {len(results)} approved/posted LinkedIn replies for context", verbose, log_caller_file="action.py")
            return results

        except Exception as e:
            log(f"Error retrieving approved/posted LinkedIn replies: {e}", verbose, is_error=True, log_caller_file="action.py")
            return []
