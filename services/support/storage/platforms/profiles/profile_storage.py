import os

from typing import Dict, Any, List
from services.support.logger_util import _log as log
from services.support.storage.base_storage import BaseStorage
from services.support.postgres_util import get_postgres_connection, create_table_if_not_exists, select_data, insert_data, upsert_data

class ProfilesStorage(BaseStorage):
    def __init__(self, profile_name: str):
        super().__init__(profile_name)

    def _get_table_name(self) -> str:
        return f"profiles_sync"

    def _get_profiles_table_name(self) -> str:
        return "profiles"

    def _get_table_schema(self) -> Dict[str, str]:
        return {
            "profile_name": "TEXT",
            "sync_type": "TEXT",
            "source_profile": "TEXT",
            "target_profile": "TEXT",
            "data_type": "TEXT",
            "data": "JSONB",
            "sync_timestamp": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "status": "TEXT",
        }

    def _get_profiles_table_schema(self) -> Dict[str, str]:
        return {
            "name": "TEXT PRIMARY KEY",
            "data": "JSONB",
            "properties": "JSONB",
            "prompts": "JSONB",
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        }

    def sync_profiles(self, verbose: bool = False) -> bool:
        try:
            log(f"Starting profile sync for {self.profile_name}", verbose, log_caller_file="profile_storage.py")

            if not self.download_profiles(verbose):
                log("Failed to download profiles from Supabase", verbose, is_error=True, log_caller_file="profile_storage.py")
                return False

            conn = get_postgres_connection(verbose)
            if conn:
                table_name = self.table_name

                if create_table_if_not_exists(conn, table_name, self._get_table_schema(), verbose):
                    sync_record = {
                        'profile_name': self.profile_name,
                        'sync_type': 'download_sync',
                        'source_profile': 'supabase',
                        'target_profile': 'local',
                        'data_type': 'profile_data',
                        'data': {'synced': True, 'direction': 'supabase_to_local'},
                        'status': 'completed'
                    }

                    insert_data(conn, table_name, sync_record, verbose, conflict_column=None)

                conn.close()

            log(f"Profile sync completed for {self.profile_name} (Supabase → Local)", verbose, log_caller_file="profile_storage.py")
            return True

        except Exception as e:
            log(f"Failed to sync profiles: {e}", verbose, is_error=True, log_caller_file="profile_storage.py")
            return False

    def get_sync_history(self, verbose: bool = False) -> List[Dict[str, Any]]:
        try:
            conn = get_postgres_connection(verbose)
            if not conn:
                return []

            table_name = self.table_name
            where_clause = "profile_name = %s"
            params = (self.profile_name,)

            sync_history = select_data(conn, table_name, where_clause, params, verbose)
            conn.close()

            return sync_history

        except Exception as e:
            log(f"Failed to get sync history: {e}", verbose, is_error=True, log_caller_file="profile_storage.py")
            return []

    def upload_profiles(self, verbose: bool = False) -> bool:
        try:
            log("Starting profiles upload to Supabase", verbose, log_caller_file="profile_storage.py")

            current_dir = os.path.dirname(__file__)
            profiles_path = os.path.join(current_dir, "..", "..", "..", "..", "..", "profiles.py")
            profiles_path = os.path.abspath(profiles_path)

            if not os.path.exists(profiles_path):
                log(f"Profiles file not found: {profiles_path}", verbose, is_error=True, log_caller_file="profile_storage.py")
                return False

            import importlib.util
            spec = importlib.util.spec_from_file_location("profiles", profiles_path)
            if spec is None or spec.loader is None:
                log("Failed to load profiles module", verbose, is_error=True, log_caller_file="profile_storage.py")
                return False

            profiles_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(profiles_module)

            if not hasattr(profiles_module, 'PROFILES'):
                log("PROFILES not found in profiles.py", verbose, is_error=True, log_caller_file="profile_storage.py")
                return False

            PROFILES = profiles_module.PROFILES

            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            profiles_table = self._get_profiles_table_name()

            if not create_table_if_not_exists(conn, profiles_table, self._get_profiles_table_schema(), verbose):
                log(f"Failed to create profiles table {profiles_table}", verbose, is_error=True, log_caller_file="profile_storage.py")
                conn.close()
                return False

            success_count = 0
            for profile_name, profile_data in PROFILES.items():
                profile_record = {
                    'name': profile_name,
                    'data': profile_data.get('data', {}),
                    'properties': profile_data.get('properties', {}),
                    'prompts': profile_data.get('prompts', {})
                }

                success = upsert_data(conn, profiles_table, profile_record, verbose, conflict_column='name')
                if success:
                    success_count += 1
                    log(f"Uploaded profile: {profile_name}", verbose, log_caller_file="profile_storage.py")
                else:
                    log(f"Failed to upload profile: {profile_name}", verbose, is_error=True, log_caller_file="profile_storage.py")

            conn.close()

            if success_count == len(PROFILES):
                log(f"Successfully uploaded {len(PROFILES)} profiles to Supabase", verbose, log_caller_file="profile_storage.py")
                return True
            else:
                log(f"Only uploaded {success_count}/{len(PROFILES)} profiles to Supabase", verbose, is_error=True, log_caller_file="profile_storage.py")
                return False

        except Exception as e:
            log(f"Failed to upload profiles: {e}", verbose, is_error=True, log_caller_file="profile_storage.py")
            return False

    def download_profiles(self, verbose: bool = False) -> bool:
        try:
            log("Starting profiles download from Supabase", verbose, log_caller_file="profile_storage.py")

            conn = get_postgres_connection(verbose)
            if not conn:
                return False

            profiles_table = self._get_profiles_table_name()

            profiles_data = select_data(conn, profiles_table, verbose=verbose)
            conn.close()


            if not profiles_data:
                log("No profiles found in Supabase", verbose, log_caller_file="profile_storage.py")
                return False

            new_profiles = {}
            for record in profiles_data:
                profile_name = record['name']
                new_profiles[profile_name] = {
                    'name': profile_name,
                    'data': record.get('data', {}),
                    'properties': record.get('properties', {}),
                    'prompts': record.get('prompts', {})
                }

            current_dir = os.path.dirname(__file__)
            profiles_path = os.path.join(current_dir, "..", "..", "..", "..", "..", "profiles.py")
            profiles_path = os.path.abspath(profiles_path)

            profiles_content = "PROFILES = {\n"
            for profile_name, profile_data in new_profiles.items():
                profiles_content += f'    "{profile_name}": {{\n'
                profiles_content += f'        "name": "{profile_name}",\n'
                profiles_content += f'        "data": {repr(profile_data["data"])},\n'
                profiles_content += f'        "properties": {repr(profile_data["properties"])},\n'
                profiles_content += f'        "prompts": {repr(profile_data["prompts"])}\n'
                profiles_content += '    },\n'
            profiles_content += "}\n"

            with open(profiles_path, 'w') as f:
                f.write(profiles_content)
            log(f"Successfully downloaded and updated {len(new_profiles)} profiles to local profiles.py", verbose, log_caller_file="profile_storage.py")
            return True

        except Exception as e:
            log(f"Failed to download profiles: {e}", verbose, is_error=True, log_caller_file="profile_storage.py")
            return False

