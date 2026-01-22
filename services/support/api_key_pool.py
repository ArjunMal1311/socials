import os
import re
import time
import threading

from collections import deque
from rich.console import Console
from services.support.logger_util import _log as log

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

    def get_key(self):
        with self.lock:
            if not self.api_keys:
                return None

            while True:
                current_key = self.api_keys[self.key_index]
                self.key_index = (self.key_index + 1) % len(self.api_keys)

                current_time = time.time()
                cooldown_until = self._cooldowns.get(current_key)
                if cooldown_until and cooldown_until > current_time:
                    continue
                
                while self.key_usage_times[current_key] and \
                      self.key_usage_times[current_key][0] <= current_time - 60:
                    self.key_usage_times[current_key].popleft()
                
                if len(self.key_usage_times[current_key]) < self.rpm:
                    self.key_usage_times[current_key].append(current_time)
                    return current_key
                else:
                    time_to_wait = 60 - (current_time - self.key_usage_times[current_key][0])
                    if time_to_wait > 0:
                        time.sleep(time_to_wait)

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