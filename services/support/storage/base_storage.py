from abc import ABC
from typing import List, Dict, Any, Optional

from services.support.logger_util import _log as log
from services.support.postgres_util import get_postgres_connection, create_table_if_not_exists, insert_data, select_data

class BaseStorage(ABC):
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.table_name = self._get_table_name()

    def _get_conflict_column(self) -> str:
        return "null"

    def push_content(self, content: List[Dict[str, Any]], batch_id: str, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            table_name = self.table_name

            if not create_table_if_not_exists(conn, table_name, self._get_table_schema(), verbose):
                log(f"Failed to create table {table_name}", verbose, is_error=True, log_caller_file="base_storage.py")
                conn.close()
                return False

            success_count = 0
            for item in content:
                profile_name = item.get('profile_name', self.profile_name)
                conflict_column = self._get_conflict_column()

                status = 'pending_review'

                if conflict_column != "null":
                    conflict_value = item.get(conflict_column)
                    if conflict_value:
                        existing_records = select_data(
                            conn, table_name,
                            f"{conflict_column} = %s",
                            (conflict_value,),
                            verbose
                        )
                        if existing_records:
                            existing_status = existing_records[0].get('status')
                            if existing_status in ['approved', 'posted']:
                                status = 'posted'
                            else:
                                status = 'duplicate_not_posted'

                record = {
                    'profile_name': profile_name,
                    'batch_id': batch_id,
                    'status': status,
                    **item
                }

                if insert_data(conn, table_name, record, verbose, conflict_column=self._get_conflict_column()):
                    success_count += 1
                else:
                    log(f"Failed to insert item into {table_name}", verbose, is_error=True, log_caller_file="base_storage.py")

            conn.close()

            if success_count == len(content):
                log(f"Pushed {len(content)} items to {table_name}", verbose, log_caller_file="base_storage.py")
                return True
            else:
                log(f"Only pushed {success_count}/{len(content)} items to {table_name}", verbose, is_error=True, log_caller_file="base_storage.py")
                return False

        except Exception as e:
            log(f"Failed to push content to {self.table_name}: {e}", verbose, is_error=True, log_caller_file="base_storage.py")
            return False

    def pull_approved_content(self, batch_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []

            table_name = self.table_name

            where_clause = "batch_id = %s AND status = %s"
            params = (batch_id, 'approved')
            approved_content = select_data(conn, table_name, where_clause, params, verbose)

            conn.close()

            log(f"Pulled {len(approved_content)} approved items from {table_name}", verbose, log_caller_file="base_storage.py")
            return approved_content

        except Exception as e:
            log(f"Failed to pull approved content from {self.table_name}: {e}", verbose, is_error=True, log_caller_file="base_storage.py")
            return []

    def update_status(self, content_id: str, status: str, additional_updates: Optional[Dict[str, Any]] = None, verbose: bool = False) -> bool:
        raise NotImplementedError("update_status must be implemented by platform-specific storage classes")

    def get_batch_content(self, batch_id: str, verbose: bool = False) -> List[Dict[str, Any]]:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []

            table_name = self.table_name

            content = select_data(conn, table_name, "batch_id = %s", (batch_id,), verbose)

            conn.close()

            log(f"Retrieved {len(content)} items for batch {batch_id}", verbose, log_caller_file="base_storage.py")
            return content

        except Exception as e:
            log(f"Failed to get batch content for {batch_id}: {e}", verbose, is_error=True, log_caller_file="base_storage.py")
            return []

    def get_all_processed_urls(self, verbose: bool = False) -> List[str]:
        raise NotImplementedError("get_all_processed_urls must be implemented by platform-specific storage classes")
