import os
import json

from tabnanny import verbose
from rich.console import Console
from urllib.parse import urlparse
from services.support.logger_util import _log as log
from http.server import HTTPServer, SimpleHTTPRequestHandler
from services.platform.youtube.support.review_html import build_youtube_review_html
from services.support.path_config import get_youtube_replies_for_review_dir, get_youtube_shorts_dir

console = Console()

class YoutubeReviewRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root_dir=None, profile_name='Default', verbose=False, **kwargs):
        self.root_dir = root_dir or os.getcwd()
        self.profile_name = profile_name
        self.verbose = verbose
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        log(f"HTTP {self.client_address[0]} - {format % args}", self.verbose, log_caller_file="review_server.py")

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
                return self._serve_path('index.html')
            
            if path == '/api/replies':
                return self._json_response(self._load_replies())
            

            safe_path = os.path.normpath(path).lstrip('/')
            if safe_path.startswith("media/"):
                filename = safe_path[len("media/"):]
                shorts_dir = get_youtube_shorts_dir(self.profile_name)
                if os.path.exists(os.path.join(shorts_dir, filename)):
                    return self._serve_path(os.path.join(get_youtube_shorts_dir(self.profile_name), filename))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"Media file not found")
                    return

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
        if not full_path.startswith(os.path.abspath(self.root_dir)) and not (get_youtube_shorts_dir(self.profile_name) in full_path):
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

    def _replies_dir(self):
        return get_youtube_replies_for_review_dir(self.profile_name)

    def _load_replies(self):
        replies = []
        replies_path = self._replies_dir()
        if not os.path.exists(replies_path):
            return []
        for filename in os.listdir(replies_path):
            if filename.endswith('.json'):
                file_path = os.path.join(replies_path, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    reply_data = json.load(f)
                    replies.append(reply_data)
        return sorted(replies, key=lambda x: x.get('id', ''))

    def _save_replies(self, items):
        replies_path = self._replies_dir()
        os.makedirs(replies_path, exist_ok=True)
        for item in items:
            file_path = os.path.join(replies_path, f"{item['id']}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2, ensure_ascii=False)

    def _update_reply_status(self, reply_id, status):
        replies_path = self._replies_dir()
        file_path = os.path.join(replies_path, f"{reply_id}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r+', encoding='utf-8') as f:
                reply_data = json.load(f)
                reply_data['status'] = status
                f.seek(0)
                json.dump(reply_data, f, ensure_ascii=False, indent=4)
                f.truncate()
            log(f"Reply '{reply_id}' status updated to '{status}'.", True, verbose=self.verbose, log_caller_file="review_server.py")
            return True
        else:
            log(f"Reply file not found for ID: {reply_id}", True, is_error=True, verbose=self.verbose, log_caller_file="review_server.py")
            return False

    def _handle_update(self, data):
        reply_id = data.get('id')
        fields = data.get('fields', {})
        
        if not reply_id:
            return self._json_response({'ok': False, 'error': 'reply_id required'}, status=400)

        items = self._load_replies()
        target_item = None
        for item in items:
            if item.get('id') == reply_id:
                target_item = item
                break
        
        if not target_item:
            return self._json_response({'ok': False, 'error': 'not_found'}, status=404)

        allowed = {'generated_reply', 'status'}
        for k, v in fields.items():
            if k in allowed:
                target_item[k] = v
        
        self._save_replies(items)
        return self._json_response({'ok': True, 'item': target_item})

    def _handle_delete(self, data):
        reply_id = data.get('id')
        if not reply_id:
            return self._json_response({'ok': False, 'error': 'reply_id required'}, status=400)
        
        replies_path = self._replies_dir()
        file_path = os.path.join(replies_path, f"{reply_id}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
            log(f"Reply file '{reply_id}.json' deleted.", True, verbose=self.verbose, log_caller_file="review_server.py")
            return self._json_response({'ok': True})
        else:
            return self._json_response({'ok': False, 'error': 'not_found'}, status=404)

    @staticmethod
    def _load_static_replies(root_dir: str):
        replies = []
        replies_path = get_youtube_replies_for_review_dir(root_dir)
        if not os.path.exists(replies_path):
            return []
        
        log(replies_path, verbose=verbose, log_caller_file="review_server.py")
        
        for filename in os.listdir(replies_path):
            if filename.endswith('.json'):
                file_path = os.path.join(replies_path, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    reply_data = json.load(f)
                    replies.append(reply_data)
        log(f"[DEBUG] Loaded {len(replies)} replies from {replies_path}", True, verbose=True, log_caller_file="review_server.py")
        return sorted(replies, key=lambda x: x.get('id', ''))

def start_youtube_review_server(profile_name: str, port: int = 8767, verbose: bool = False):
    script_dir = os.path.dirname(__file__)
    
    review_data_dir = get_youtube_replies_for_review_dir(profile_name)
    os.makedirs(review_data_dir, exist_ok=True)
    
    replies_to_review = YoutubeReviewRequestHandler._load_static_replies(review_data_dir)
    generated_html = build_youtube_review_html(profile_name, replies_to_review, verbose)
    target_html_path = os.path.join(review_data_dir, 'index.html')
    with open(target_html_path, 'w', encoding='utf-8') as f:
        f.write(generated_html)
    log(f"Generated index.html to {target_html_path}", verbose, log_caller_file="review_server.py")

    handler_factory = lambda *args, **kwargs: YoutubeReviewRequestHandler(*args, root_dir=review_data_dir, profile_name=profile_name, verbose=verbose, **kwargs)
    httpd = HTTPServer(('127.0.0.1', port), handler_factory)
    log(f"Serving YouTube reply review for '{profile_name}' at http://127.0.0.1:{port}", verbose, log_caller_file="review_server.py")
    log("Press Ctrl+C to stop.", verbose, log_caller_file="review_server.py")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == '__main__':
    start_youtube_review_server("Default")
