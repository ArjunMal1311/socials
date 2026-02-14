import os
import re
import time
import json
import threading

from collections import deque
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.path_config import get_pool_dir, ensure_dir_exists

console = Console()

class APIKeyPool:
    def __init__(self, api_keys_string: str = None, rpm: int = 60, verbose: bool = False):
        self.api_keys = []
        self.key_usage_times = {}
        self.rpm = rpm
        self.lock = threading.Lock()
        self.key_index = 0
        self.verbose = verbose
        self._cooldowns = {}
        self.usage_file = os.path.join(ensure_dir_exists(get_pool_dir()), "api_key_usage.json")
        self.load_keys(api_keys_string, verbose)

    def set_explicit_key(self, api_key: str):
        with self.lock:
            self.api_keys = [api_key.strip()]
            self.key_usage_times = {api_key.strip(): deque()}
            self.key_index = 0

    def load_keys(self, api_keys_string: str = None, verbose: bool = False):
        with self.lock:
            self.api_keys = []
            self.key_usage_times = {}
            self.key_index = 0
            self._cooldowns = {}

            keys_to_load = []
            if api_keys_string:
                keys_to_load = [key.strip() for key in api_keys_string.split(',') if key.strip()]
            elif os.getenv('GEMINI_API'):
                keys_to_load = [key.strip() for key in os.getenv('GEMINI_API').split(',') if key.strip()]

            if not keys_to_load:
                log("Warning: No API keys provided or found in GEMINI_API environment variable. Pool is empty.", verbose, is_error=False, log_caller_file="api_key_pool.py")
                return

            self.api_keys.extend(keys_to_load)
            self.key_usage_times = {key: deque() for key in self.api_keys}

    def _get_usage_counts(self):
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_usage_counts(self, counts):
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(counts, f, indent=2)
        except Exception:
            pass

    def get_key(self):
        with self.lock:
            if not self.api_keys:
                return None

            current_time = time.time()
            usage_counts = self._get_usage_counts()

            available_keys = []
            for key in self.api_keys:
                cooldown_until = self._cooldowns.get(key)
                if not (cooldown_until and cooldown_until > current_time):
                    available_keys.append(key)

            if not available_keys:
                selected_key = self.api_keys[self.key_index]
                self.key_index = (self.key_index + 1) % len(self.api_keys)
            else:
                selected_key = min(available_keys, key=lambda k: usage_counts.get(k, 0))

            while self.key_usage_times[selected_key] and \
                  self.key_usage_times[selected_key][0] <= current_time - 60:
                self.key_usage_times[selected_key].popleft()

            if len(self.key_usage_times[selected_key]) < self.rpm:
                self.key_usage_times[selected_key].append(current_time)
                
                usage_counts[selected_key] = usage_counts.get(selected_key, 0) + 1
                self._save_usage_counts(usage_counts)
                
                return selected_key
            else:
                time_to_wait = 60 - (current_time - self.key_usage_times[selected_key][0])
                if time_to_wait > 0:
                    time.sleep(time_to_wait)
                
                return self.get_key()

    def mark_cooldown(self, api_key: str, seconds: float = 65.0):
        with self.lock:
            if api_key:
                self._cooldowns[api_key] = time.time() + max(1.0, seconds)
                log(f"Key ending with {api_key[-4:]} put on cooldown for {int(seconds)}s", self.verbose, log_caller_file="api_key_pool.py")

    def report_failure(self, api_key: str, error: Exception | str):
        message = str(error) if error is not None else ""
        if re.search(r"\b429\b|rate limit|quota|Resource has been exhausted|Too Many Requests", message, re.IGNORECASE):
            self.mark_cooldown(api_key, seconds=70.0)
        else:
            pass

    def size(self) -> int:
        with self.lock:
            return len(self.api_keys)

    def release_key(self, api_key: str, success: bool):
        with self.lock:
            if not success:
                self.report_failure(api_key, "API call failed, putting key on cooldown.")