import json

from typing import Dict, List, Any
from services.support.storage.base_storage import BaseStorage
from services.support.postgres_util import get_postgres_connection, update_data

class ProductHuntActionStorage(BaseStorage):
    def _get_table_name(self) -> str:
        return f"{self.profile_name}_producthunt"

    def _get_conflict_column(self) -> str:
        return "product_id"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "batch_id": "TEXT NOT NULL",
            "profile_name": "TEXT NOT NULL",
            "product_id": "TEXT NOT NULL UNIQUE",
            "source": "TEXT",
            "scraped_at": "TIMESTAMP",
            "product_name": "TEXT",
            "product_description": "TEXT",
            "website": "TEXT",
            "source_url": "TEXT",
            "logo": "TEXT",
            "founders": "JSONB",
            "upvotes_count": "INTEGER DEFAULT 0",
            "tagline": "TEXT",
            "status": "TEXT DEFAULT 'pending_review'",
            "created_at": "TIMESTAMP DEFAULT NOW()",
            "updated_at": "TIMESTAMP DEFAULT NOW()"
        }

    def push_content(self, content: List[Dict[str, Any]], batch_id: str, verbose: bool = False) -> bool:
        mapped_content = []
        for product in content:
            mapped_product = self._map_product_data(product)
            mapped_content.append(mapped_product)

        return super().push_content(mapped_content, batch_id, verbose)

    def update_status(self, content_id: str, status: str, additional_updates: Dict[str, Any] = None, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            updates = {'status': status}
            if additional_updates:
                updates.update(additional_updates)

            success = update_data(conn, self.table_name, updates, "product_id = %s", (content_id,), verbose)

            conn.close()
            return success

        except Exception as e:
            from services.support.logger_util import _log as log
            log(f"Failed to update product {content_id} status: {e}", verbose, is_error=True, log_caller_file="action.py")
            return False

    def _map_product_data(self, product: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "product_id": product.get("id"),
            "source": product.get("source"),
            "scraped_at": product.get("scraped_at"),
            "product_name": product.get("core", {}).get("name"),
            "product_description": product.get("core", {}).get("description"),
            "website": product.get("core", {}).get("website"),
            "source_url": product.get("core", {}).get("source_url"),
            "logo": product.get("core", {}).get("logo"),
            "founders": json.dumps(product.get("founders", [])),
            "upvotes_count": product.get("data", {}).get("upvotes_count", 0),
            "tagline": product.get("data", {}).get("tagline")
        }
