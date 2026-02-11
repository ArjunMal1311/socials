import json
from typing import Dict, List, Any
from services.support.storage.base_storage import BaseStorage
from services.support.logger_util import _log

class InstagramLearningStorage(BaseStorage):
    def _get_table_name(self) -> str:
        return "learning_content"

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
            "explanation": "TEXT",
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
            "explanation": item.get("explanation", ""),
            "media_path": item.get("media_path", ""),
            "cdn_link": item.get("cdn_link", ""),
            "raw_data": json.dumps(item)
        }
