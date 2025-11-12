import re
import time
import threading

from datetime import datetime
from rich.console import Console

console = Console()

def _log(message: str, verbose: bool, is_error: bool = False):
    if verbose or is_error:
        log_message = message
        if is_error and not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red" if is_error else "white"
        console.print(f"[rate_limiter.py] {timestamp}|[{color}]{log_message}[/{color}]")

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
                _log(f"Rate limit reached for API key. Waiting...", self.verbose)
                sleep_time = key_requests[0] - minute_ago
                if sleep_time > 0:
                    time.sleep(sleep_time)
                key_requests = key_requests[1:]
            
            key_requests.append(time.time())
            self.requests_per_key[api_key] = key_requests
            return max(0, sleep_time)