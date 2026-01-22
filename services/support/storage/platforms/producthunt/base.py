from abc import ABC
from typing import List, Dict, Any

from services.support.logger_util import _log as log
from services.support.postgres_util import get_postgres_connection, create_table_if_not_exists, insert_data, select_data

class BaseProductHuntStorage(ABC):
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.table_name = self._get_table_name()

    def _get_conflict_column(self) -> str:
        return "product_id"

class BaseProductHuntStorage(ABC):
    def __init__(self, profile_name: str):
        self.profile_name = profile_name
        self.table_name = self._get_table_name()

    def _get_table_name(self) -> str:
        raise NotImplementedError("_get_table_name must be implemented by platform-specific storage classes")

    def _get_table_schema(self) -> dict:
        raise NotImplementedError("_get_table_schema must be implemented by platform-specific storage classes")

    def push_content(self, content: List[Dict[str, Any]], batch_id: str, verbose: bool = False) -> bool:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            table_name = self.table_name

            if not create_table_if_not_exists(conn, table_name, self._get_table_schema(), verbose):
                log(f"Failed to create table {table_name}", verbose, is_error=True, log_caller_file="base.py")
                conn.close()
                return False

            success_count = 0
            for item in content:
                profile_name = item.get('profile_name', self.profile_name)
                record = {
                    'profile_name': profile_name,
                    'batch_id': batch_id,
                    **item
                }

                if insert_data(conn, table_name, record, verbose, conflict_column=self._get_conflict_column()):
                    success_count += 1
                else:
                    log(f"Failed to insert item into {table_name}", verbose, is_error=True, log_caller_file="base.py")

            conn.close()

            if success_count == len(content):
                log(f"Pushed {len(content)} items to {table_name}", verbose, log_caller_file="base.py")
                return True
            else:
                log(f"Only pushed {success_count}/{len(content)} items to {table_name}", verbose, is_error=True, log_caller_file="base.py")
                return False

        except Exception as e:
            log(f"Failed to push content to {self.table_name}: {e}", verbose, is_error=True, log_caller_file="base.py")
            return False
