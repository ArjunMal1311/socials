import re
import json
import inspect
import os

from datetime import datetime
from rich.console import Console
from rich.markup import escape
from typing import Optional, Dict, Any

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None, log_caller_file: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
    if not log_caller_file:
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                log_caller_file = os.path.basename(frame.f_back.f_code.co_filename)
        except Exception:
            log_caller_file = "unknown"

    caller_info = f"[[dim][blue]{escape(log_caller_file)}[/blue][/dim]]" if log_caller_file else "[[dim][blue]unknown[/blue][/dim]]"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_prefix = f"{timestamp} | {caller_info} | "

    if is_error:
        if status:
            status.stop()
        log_message = message
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        color = "bold red"
        console.print(f"{log_prefix}[{color}]{log_message}{quota_str}[/{color}]")
        if status:
            status.start()
        
    elif status:
        status.update(f"{log_prefix}{message}")
        if verbose:
            color = "white"
            console.print(f"{log_prefix}[{color}]{message}[/{color}]")
            if data:
                console.print(json.dumps(data, indent=2, ensure_ascii=False))

    else:
        color = "white"
        console.print(f"{log_prefix}[{color}]{message}[/{color}]")
        if data and verbose:
            console.print(json.dumps(data, indent=2, ensure_ascii=False))

