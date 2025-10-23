import re
import os
import json

from datetime import datetime
from rich.console import Console
from urllib.parse import urlparse
from services.support.path_config import get_replies_dir
from http.server import HTTPServer, SimpleHTTPRequestHandler

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
        console.print(f"[action_mode_server.py] {timestamp}|[{color}]{log_message}[/{color}]")


class ActionModeRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root_dir=None, verbose: bool = False, **kwargs):
        self.root_dir = root_dir or os.getcwd()
        self.verbose = verbose
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        _log(f"HTTP {self.client_address[0]} - {format % args}", self.verbose)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == '/' or path == '' or path == '/index.html':
                return self._serve_path('review.html')

            safe_path = os.path.normpath(path).lstrip('/')
            return self._serve_path(safe_path)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            content_length = int(self.headers.get('Content-Length', '0') or '0')
            raw_body = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(raw_body.decode('utf-8') or '{}')

            if path == '/api/update':
                return self._handle_update(data)
            if path == '/api/delete':
                return self._handle_delete(data)
            if path == '/api/refresh':
                return self._json_response({'ok': True})

            self.send_response(404)
            self.end_headers()
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def _serve_path(self, rel_path: str):
        full_path = os.path.join(self.root_dir, rel_path)
        full_path = os.path.abspath(full_path)
        if not full_path.startswith(os.path.abspath(self.root_dir)):
            self.send_response(403)
            self.end_headers()
            return
        if os.path.isdir(full_path):
            full_path = os.path.join(full_path, 'index.html')
        if not os.path.exists(full_path):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        if full_path.endswith('.html'):
            self.send_header('Content-Type', 'text/html; charset=utf-8')
        elif full_path.endswith('.json'):
            self.send_header('Content-Type', 'application/json; charset=utf-8')
        elif full_path.endswith('.mp4'):
            self.send_header('Content-Type', 'video/mp4')
        elif full_path.endswith('.webm'):
            self.send_header('Content-Type', 'video/webm')
        elif full_path.endswith('.jpg') or full_path.endswith('.jpeg'):
            self.send_header('Content-Type', 'image/jpeg')
        elif full_path.endswith('.png'):
            self.send_header('Content-Type', 'image/png')
        elif full_path.endswith('.gif'):
            self.send_header('Content-Type', 'image/gif')
        else:
            self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        with open(full_path, 'rb') as f:
            self.wfile.write(f.read())

    def _json_response(self, obj, status=200):
        payload = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _schedule_path(self):
        return os.path.join(self.root_dir, 'schedule.json')

    def _load_schedule(self):
        schedule_path = self._schedule_path()
        if not os.path.exists(schedule_path):
            return []
        with open(schedule_path, 'r') as f:
            return json.load(f)

    def _save_schedule(self, items):
        schedule_path = self._schedule_path()
        with open(schedule_path, 'w') as f:
            json.dump(items, f, indent=2)

    def _handle_update(self, data):
        tweet_id = data.get('tweet_id')
        index = data.get('index')
        fields = data.get('fields', {})
        items = self._load_schedule()
        target_idx = None
        if tweet_id is not None:
            for i, it in enumerate(items):
                if str(it.get('tweet_id')) == str(tweet_id):
                    target_idx = i
                    break
        elif isinstance(index, int) and 0 <= index < len(items):
            target_idx = index
        if target_idx is None:
            return self._json_response({'ok': False, 'error': 'not_found'}, status=404)
        allowed = {'generated_reply', 'tweet_text', 'status'}
        for k, v in fields.items():
            if k in allowed:
                items[target_idx][k] = v
        self._save_schedule(items)
        return self._json_response({'ok': True, 'item': items[target_idx]})

    def _handle_delete(self, data):
        tweet_id = data.get('tweet_id')
        index = data.get('index')
        items = self._load_schedule()
        if tweet_id is not None:
            new_items = [it for it in items if str(it.get('tweet_id')) != str(tweet_id)]
        elif isinstance(index, int) and 0 <= index < len(items):
            new_items = items[:index] + items[index+1:]
        else:
            return self._json_response({'ok': False, 'error': 'not_found'}, status=404)
        self._save_schedule(new_items)
        return self._json_response({'ok': True, 'count': len(new_items)})


def start_action_mode_review_server(profile_name: str, port: int = 8765, verbose: bool = False):
    root_dir = get_replies_dir(profile_name)
    if not os.path.exists(os.path.join(root_dir, 'review.html')):
        _log(f"review.html not found under {root_dir}. Generate it first.", verbose, is_error=False)
    handler_factory = lambda *args, **kwargs: ActionModeRequestHandler(*args, root_dir=root_dir, verbose=verbose, **kwargs)
    httpd = HTTPServer(('127.0.0.1', port), handler_factory)

    def shutdown_server():
        _log("Shutting down Action Mode review server...", verbose)
        httpd.shutdown()

    httpd.shutdown_server = shutdown_server
    _log(f"Serving Action Mode review for '{profile_name}' at http://127.0.0.1:{port}", verbose)
    _log("Press Ctrl+C in this terminal to stop the review server manually (or Enter in the main terminal once done).", verbose)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return httpd

