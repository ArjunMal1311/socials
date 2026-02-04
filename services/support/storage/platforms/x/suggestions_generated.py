from typing import Dict, Any

from services.support.storage.base_storage import BaseStorage

class XSuggestionsGeneratedStorage(BaseStorage):
    def __init__(self, profile_name: str):
        super().__init__(profile_name)

    def _get_table_name(self) -> str:
        return f"{self.profile_name}_x_generated_captions"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "profile_name": "VARCHAR(255) NOT NULL",
            "batch_id": "VARCHAR(255) NOT NULL",
            "content_id": "VARCHAR(255) UNIQUE NOT NULL",
            "tweet_url": "TEXT",
            "original_content": "TEXT",
            "generated_caption": "TEXT",
            "media_urls": "TEXT[]",
            "downloaded_media_paths": "TEXT[]",
            "date": "VARCHAR(255)",
            "likes": "INTEGER DEFAULT 0",
            "retweets": "INTEGER DEFAULT 0",
            "replies": "INTEGER DEFAULT 0",
            "views": "INTEGER DEFAULT 0",
            "bookmarks": "INTEGER DEFAULT 0",
            "total_engagement": "INTEGER DEFAULT 0",
            "comments": "INTEGER DEFAULT 0",
            "age_days": "INTEGER DEFAULT 0",
            "scraped_date": "VARCHAR(255)",
            "tweet_date": "VARCHAR(255)",
            "profile_image_url": "TEXT",
            "engagement_score": "INTEGER DEFAULT 0",
            "finalized": "BOOLEAN DEFAULT FALSE",
            "generation_timestamp": "VARCHAR(255)",
            "status": "VARCHAR(50) DEFAULT 'pending'",
            "generated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        }

    def _get_conflict_column(self) -> str:
        return "content_id"

    def update_status(self, content_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        # This method will be implemented more fully later, for now a placeholder.
        # The `push_content` in BaseStorage handles the initial status setting.
        # This is primarily for manual approval/rejection and posting updates.
        print(f"Update status for content_id {content_id} to {status} with additional updates {additional_updates}")
        return True

