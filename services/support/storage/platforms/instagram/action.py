import json

from typing import Dict, List, Any
from services.support.storage.base_storage import BaseStorage

from services.support.logger_util import _log
from services.support.postgres_util import get_postgres_connection, select_data, update_data

class InstagramActionStorage(BaseStorage):
    def _get_table_name(self) -> str:
        return f"{self.profile_name}_reels"

    def _get_conflict_column(self) -> str:
        return "reel_id"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "batch_id": "TEXT NOT NULL",
            "profile_name": "TEXT NOT NULL",
            "reel_id": "TEXT NOT NULL UNIQUE",
            "reel_url": "TEXT",
            "reel_text": "TEXT",
            "reel_date": "TIMESTAMP",
            "likes": "INTEGER DEFAULT 0",
            "comments": "INTEGER DEFAULT 0",
            "views": "INTEGER DEFAULT 0",
            "shares": "INTEGER DEFAULT 0",
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
        for reel in content:
            mapped_reel = self._map_reel_data(reel)
            mapped_reel["generated_reply"] = reel.get("generated_reply")
            mapped_content.append(mapped_reel)

        return super().push_content(mapped_content, batch_id, verbose)

    def update_status(self, content_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            updates = {'status': status}
            if additional_updates:
                updates.update(additional_updates)

            success = update_data(conn, self.table_name, updates, "reel_id = %s", (content_id,), verbose)

            conn.close()
            return success

        except Exception as e:
            from services.support.logger_util import _log as log
            log(f"Failed to update reel {content_id} status: {e}", verbose, is_error=True, log_caller_file="action.py")
            return False

    def _map_reel_data(self, reel: Dict[str, Any]) -> Dict[str, Any]:
        media_urls = reel.get("media_urls", [])
        if not media_urls:
            media_urls = []

        return {
            "reel_id": reel.get("reel_id"),
            "reel_url": reel.get("reel_url"),
            "reel_text": reel.get("reel_text", ""),
            "reel_date": reel.get("reel_date"),
            "likes": reel.get("likes", 0),
            "comments": reel.get("comments", 0),
            "views": reel.get("views", 0),
            "shares": reel.get("shares", 0),
            "media_urls": json.dumps(media_urls)
        }

    def _unmap_reel_data(self, reel: Dict[str, Any]) -> Dict[str, Any]:
        media_urls = reel.get("media_urls")
        if isinstance(media_urls, str):
            media_urls = json.loads(media_urls)
        elif media_urls is None:
            media_urls = []

        return {
            "reel_id": reel["reel_id"],
            "reel_url": reel["reel_url"],
            "reel_text": reel.get("reel_text", ""),
            "reel_date": reel["reel_date"],
            "likes": reel["likes"],
            "comments": reel["comments"],
            "views": reel["views"],
            "shares": reel["shares"],
            "media_urls": media_urls
        }

    def pull_approved_content(self, batch_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        approved_reels = super().pull_approved_content(batch_id, verbose)

        mapped_reels = []
        for reel in approved_reels:
            mapped_reel = self._unmap_reel_data(reel)
            mapped_reel["generated_reply"] = reel.get("generated_reply")
            mapped_reel["profile_name"] = reel.get("profile_name")
            mapped_reels.append(mapped_reel)

        return mapped_reels

    def get_all_approved_and_posted_reels(self, verbose: bool = False) -> List[Dict[str, Any]]:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []

            table_name = self.table_name

            where_clause = "status IN (%s, %s) AND generated_reply IS NOT NULL AND generated_reply != ''"
            params = ('approved', 'posted')
            approved_and_posted_reels = select_data(conn, table_name, where_clause, params, verbose)

            conn.close()

            formatted_reels = []
            for reel in approved_and_posted_reels:
                formatted_reels.append({
                    'reel_text': reel.get('reel_text', ''),
                    'reply': reel.get('generated_reply', ''),
                    'approved': True
                })

            _log(f"Fetched {len(formatted_reels)} approved and posted reels for context from {table_name}", verbose, log_caller_file="action.py")
            return formatted_reels

        except Exception as e:
            _log(f"Failed to fetch approved reels from {self.table_name}: {e}", verbose, is_error=True, log_caller_file="action.py")
            return []
