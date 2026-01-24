from typing import Dict, Any
from services.support.logger_util import _log as log
from services.support.storage.base_storage import BaseStorage
from services.support.postgres_util import get_postgres_connection, create_table_if_not_exists, upsert_data

class ConnectionStorage(BaseStorage):
    def __init__(self, profile_name: str):
        super().__init__(profile_name)

    def _get_table_name(self) -> str:
        return f"{self.profile_name}_connections"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "profile_name": "TEXT",
            "platform": "TEXT",
            "connection_type": "TEXT",
            "target_username": "TEXT",
            "target_url": "TEXT PRIMARY KEY",
            "target_id": "TEXT",
            "status": "TEXT",
            "source": "TEXT",
            "sent_at": "TIMESTAMP",
            "error_message": "TEXT",
        }

    def _get_conflict_column(self) -> str:
        return "target_url"

    def _map_to_db_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def _map_from_db_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return data

    def _format_for_json(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return record

    def upsert_data(self, data: Dict[str, Any], verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            table_name = self.table_name

            if not create_table_if_not_exists(conn, table_name, self._get_table_schema(), verbose):
                log(f"Failed to create table {table_name}", verbose, is_error=True, log_caller_file="connection_storage.py")
                conn.close()
                return False

            success = upsert_data(conn, table_name, data, verbose, conflict_column=self._get_conflict_column())
            conn.close()
            return success

        except Exception as e:
            log(f"Failed to upsert data to {self.table_name}: {e}", verbose, is_error=True, log_caller_file="connection_storage.py")
            return False
