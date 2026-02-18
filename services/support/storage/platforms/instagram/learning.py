import json
from typing import Dict, List, Any
from services.support.storage.base_storage import BaseStorage
from services.support.logger_util import _log

class InstagramLearningStorage(BaseStorage):
    def _get_table_name(self) -> str:
        return f"{self.profile_name}_learning_instagram"

    def _get_conflict_column(self) -> str:
        return "post_url"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "batch_id": "TEXT",
            "profile_name": "TEXT NOT NULL",
            "post_url": "TEXT NOT NULL UNIQUE",
            "post_type": "TEXT",
            "caption": "TEXT",
            "short_explanation": "TEXT",
            "long_explanation": "TEXT",
            "media_path": "TEXT",
            "cdn_link": "TEXT",
            "raw_data": "JSONB",
            "status": "TEXT DEFAULT 'pending_review'",
            "created_at": "TIMESTAMP DEFAULT NOW()",
            "updated_at": "TIMESTAMP DEFAULT NOW()"
        }

    def push_content(self, content: List[Dict[str, Any]], batch_id: str, verbose: bool = False) -> bool:
        mapped_content = []
        for item in content:
            mapped_item = self._map_learning_data(item, batch_id)
            mapped_content.append(mapped_item)

        return super().push_content(mapped_content, batch_id, verbose)

    def _map_learning_data(self, item: Dict[str, Any], batch_id: str) -> Dict[str, Any]:
        return {
            "batch_id": batch_id,
            "profile_name": item.get("profile_name"),
            "post_url": item.get("post_url"),
            "post_type": item.get("post_type", "unknown"),
            "caption": item.get("caption", ""),
            "short_explanation": item.get("short_explanation", ""),
            "long_explanation": item.get("long_explanation", ""),
            "media_path": item.get("media_path", ""),
            "cdn_link": item.get("cdn_link", ""),
            "raw_data": json.dumps(item)
        }

    def get_all_processed_urls(self, verbose: bool = False) -> List[str]:
        from services.support.postgres_util import get_postgres_connection, select_data
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []
            
            results = select_data(conn, self.table_name, verbose=verbose)
            conn.close()
            
            return [r.get('post_url') for r in results if r.get('post_url')]
        except Exception as e:
            _log(f"Failed to fetch processed URLs from DB: {e}", verbose, is_error=True)
            return []

