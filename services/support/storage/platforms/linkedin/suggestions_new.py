from typing import Dict, Any

from services.support.storage.base_storage import BaseStorage

class LinkedInSuggestionsNewStorage(BaseStorage):
    def __init__(self, profile_name: str):
        super().__init__(profile_name)

    def _get_table_name(self) -> str:
        return f"{self.profile_name}_linkedin_generated_new_content"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "profile_name": "VARCHAR(255) NOT NULL",
            "batch_id": "VARCHAR(255) NOT NULL",
            "generated_text_id": "VARCHAR(255) UNIQUE NOT NULL",
            "generated_text": "TEXT",
            "filtered_content_analyzed": "TEXT",
            "approved": "BOOLEAN DEFAULT FALSE",
            "status": "VARCHAR(50) DEFAULT 'pending'",
            "generation_date": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP"
        }

    def _get_conflict_column(self) -> str:
        return "generated_text_id"

    def update_status(self, generated_text_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        # This method will be implemented more fully later, for now a placeholder.
        # The `push_content` in BaseStorage handles the initial status setting.
        # This is primarily for manual approval/rejection and posting updates.
        print(f"Update status for generated_text_id {generated_text_id} to {status} with additional updates {additional_updates}")
        return True

