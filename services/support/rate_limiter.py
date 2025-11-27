import time
import threading

from rich.console import Console
from services.support.logger_util import _log as log

console = Console()

class RateLimiter:
    def __init__(self, rpm_limit=60, verbose: bool = False):
        self.rpm_limit = rpm_limit
        self.requests_per_key = {}
        self.lock = threading.Lock()
        self.verbose = verbose

    def wait_if_needed(self, api_key):
        now = time.time()
        with self.lock:
            if api_key not in self.requests_per_key:
                self.requests_per_key[api_key] = []
            
            key_requests = self.requests_per_key[api_key]
            minute_ago = now - 60
            key_requests = [req for req in key_requests if req > minute_ago]
            
            sleep_time = 0
            if len(key_requests) >= self.rpm_limit:
                log(f"Rate limit reached for API key. Waiting...", self.verbose, log_caller_file="rate_limiter.py")
                sleep_time = key_requests[0] - minute_ago
                if sleep_time > 0:
                    time.sleep(sleep_time)
                key_requests = key_requests[1:]
            
            key_requests.append(time.time())
            self.requests_per_key[api_key] = key_requests
            return max(0, sleep_time)