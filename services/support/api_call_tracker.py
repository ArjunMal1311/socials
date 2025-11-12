import os
import json

from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from services.support.path_config import get_api_log_file_path, ensure_dir_exists

class APICallTracker:
    def __init__(self, log_file: str = None):
        if log_file is None:
            log_file = get_api_log_file_path()
        self.log_file = os.path.abspath(log_file)
        ensure_dir_exists(os.path.dirname(self.log_file))
        self.call_log: deque[Dict[str, Any]] = deque()
        self.service_quotas = {
            "gemini": {
                "gemini-2.5-pro": {"rpm": 5, "tpm": 125000, "rpd": 100},
                "gemini-2.5-flash": {"rpm": 10, "tpm": 250000, "rpd": 250},
                "gemini-2.5-flash-preview": {"rpm": 10, "tpm": 250000, "rpd": 250},
                "gemini-2.5-flash-lite": {"rpm": 15, "tpm": 250000, "rpd": 1000},
                "gemini-2.5-flash-lite-preview": {"rpm": 15, "tpm": 250000, "rpd": 1000},
                "gemini-2.0-flash": {"rpm": 15, "tpm": 1000000, "rpd": 200},
                "gemini-2.0-flash-lite": {"rpm": 30, "tpm": 1000000, "rpd": 200},
                "gemini-flash-latest": {"rpm": 15, "tpm": 1000000, "rpd": 200},
                "gemini-flash-latest-lite": {"rpm": 30, "tpm": 1000000, "rpd": 200}
            },
            "sheets": {
                "read": {"rpm": 60, "tpm": -1, "rpd": -1},
                "write": {"rpm": 60, "tpm": -1, "rpd": -1},
            },
            "reddit": {
                "subreddit_hot": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "subreddit_new": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "subreddit_top": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "subreddit_rising": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "subreddit_week": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "subreddit_day": {"rpm": 60, "tpm": -1, "rpd": 1000},
                "post_comments": {"rpm": 60, "tpm": -1, "rpd": 1000},
            },
            "google_search": {
                "search_query": {"rpm": 100, "tpm": -1, "rpd": 10000}
            }
        }
        self._load_log()

    def _load_log(self):
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r') as f:
                try:
                    loaded_log = json.load(f)
                    for entry in loaded_log:
                        
                        entry['timestamp_dt'] = datetime.fromisoformat(entry['timestamp'])
                        self.call_log.append(entry)
                except json.JSONDecodeError:
                    self.call_log = deque()

    def _save_log(self):
        pruned_log = [entry for entry in self.call_log if entry['timestamp_dt'] > datetime.now() - timedelta(days=2)]
        with open(self.log_file, 'w') as f:
            json.dump(list(pruned_log), f, indent=2, default=str)

    def record_call(self, service: str, method: str, model: Optional[str] = None, api_key_suffix: Optional[str] = None, success: bool = True, response: Optional[Any] = None):
        timestamp = datetime.now()
        call_details = {
            "timestamp": timestamp.isoformat(),
            "timestamp_dt": timestamp,
            "service": service,
            "method": method,
            "model": model,
            "api_key_suffix": api_key_suffix,
            "success": success,
            "response": str(response) if response else None 
        }
        self.call_log.append(call_details)
        self._save_log()

    def _get_current_counts(self, service: str, method: str, model: Optional[str] = None, api_key_suffix: Optional[str] = None) -> Tuple[int, int]:
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        today_start = datetime(now.year, now.month, now.day)

        rpm_count = 0
        rpd_count = 0

        while self.call_log and self.call_log[0]['timestamp_dt'] < today_start - timedelta(days=1):
            self.call_log.popleft()

        for call in self.call_log:
            if call['service'] == service and call['method'] == method:
                if service == "gemini" and call.get('model') != model:
                    continue
                if api_key_suffix and call.get('api_key_suffix') != api_key_suffix:
                    continue
                
                if call['timestamp_dt'] > minute_ago:
                    rpm_count += 1
                if call['timestamp_dt'] > today_start:
                    rpd_count += 1
        return rpm_count, rpd_count

    def can_make_call(self, service: str, method: str, model: Optional[str] = None, api_key_suffix: Optional[str] = None) -> Tuple[bool, str]:
        rpm_count, rpd_count = self._get_current_counts(service, method, model, api_key_suffix)

        if service == "gemini":
            if model not in self.service_quotas["gemini"]:
                return False, f"Unknown Gemini model: {model}"
            quotas = self.service_quotas["gemini"][model]
        elif service == "sheets":
            if method not in self.service_quotas["sheets"]:
                return False, f"Unknown Sheets method: {method}"
            quotas = self.service_quotas["sheets"][method]
        elif service == "reddit":
            if method not in self.service_quotas["reddit"]:
                return False, f"Unknown Reddit method: {method}"
            quotas = self.service_quotas["reddit"][method]
        elif service == "google_search":
            if method not in self.service_quotas["google_search"]:
                return False, f"Unknown Google Search method: {method}"
            quotas = self.service_quotas["google_search"][method]
        else:
            return False, f"Unknown service: {service}"

        if quotas.get("quota_type") == "rpm" and rpm_count >= quotas.get("limit", 0):
            return False, f"Rate limit (RPM) exceeded for {service}/{method} (model: {model})."
        
        if quotas.get("quota_type") == "rpd" and rpd_count >= quotas.get("limit", 0):
            return False, f"Rate limit (RPD) exceeded for {service}/{method} (model: {model})."

        return True, "Call allowed."

    def get_quot_info(self, service: str, method_name: str, model: Optional[str] = None, api_key_suffix: str = "") -> Dict[str, Any]:
        rpm_count, rpd_count = self._get_current_counts(service, method_name, model, api_key_suffix)
        
        quotas = None
        if service == "gemini":
            quotas = self.service_quotas["gemini"].get(method_name)
        elif service == "sheets":
            quotas = self.service_quotas["sheets"].get(method_name)
        elif service == "reddit":
            quotas = self.service_quotas["reddit"].get(method_name)
        elif service == "google_search":
            quotas = self.service_quotas["google_search"].get(method_name)
        else:
            return {"error": "Quota information not found.", "message": "Unknown service.", "service": service, "method": method_name}

        if not quotas:
            return {"error": "Quota information not found."}

        info = {
            "service": service,
            "method": method_name,
            "model": None,
            "rpm_current": None,
            "rpm_limit": None,
            "rpd_current": None,
            "rpd_limit": None,
            "message": f"Quota for {service}.{method_name} reached."
        }

        if quotas.get("quota_type") == "rpm":
            info["rpm_current"] = rpm_count
            info["rpm_limit"] = quotas.get("limit")
        elif quotas.get("quota_type") == "rpd":
            info["rpd_current"] = rpd_count
            info["rpd_limit"] = quotas.get("limit")
            
        return info
