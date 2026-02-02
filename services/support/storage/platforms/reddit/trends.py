from typing import Dict, Any

from services.support.storage.base_storage import BaseStorage

class RedditTrendsStorage(BaseStorage):
    def __init__(self, profile_name: str):
        super().__init__(profile_name)

    def _get_table_name(self) -> str:
        return f"{self.profile_name}_reddit_trends"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "profile_name": "VARCHAR(255) NOT NULL",
            "analysis_date": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "trends": "JSONB",
            "keywords": "TEXT[]",
            "sentiment": "TEXT",
            "content_ideas": "JSONB",
            "posts_analyzed": "INTEGER",
            "generated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        }

    def _get_conflict_column(self) -> str:
        return None
