import os
import sys
import json
import urllib.parse

from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))

from services.support.logger_util import _log as log
from services.support.path_config import get_suggestions_dir

from services.utils.suggestions.support.x.content_filter import get_latest_scraped_file
from services.utils.suggestions.support.x.scraping_utils import get_latest_approved_file, get_latest_suggestions_file

def load_filtered_content(profile_name):
    filepath = get_latest_scraped_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'filtered_tweets' in data:
            return data
        return None
    except Exception as e:
        log(f"Error loading filtered content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def load_approved_content(profile_name):
    filepath = get_latest_approved_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading approved content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def load_generated_content(profile_name):
    filepath = get_latest_suggestions_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading generated content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def save_approved_content(profile_name, approved_posts):
    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"approved_content_{timestamp}.json"

    data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "approved_posts": approved_posts,
        "metadata": {
            "total_approved": len(approved_posts),
            "approval_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

    filepath = os.path.join(suggestions_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return filepath

def save_reviewed_content(profile_name, generated_posts):
    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"suggestions_content_{timestamp}_reviewed.json"

    data = {
        "timestamp": datetime.now().isoformat(),
        "profile_name": profile_name,
        "generated_posts": generated_posts,
        "metadata": {
            "total_reviewed": len(generated_posts),
            "review_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    }

    filepath = os.path.join(suggestions_dir, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"Reviewed content saved to {filepath}", verbose=False, log_caller_file="web_app.py")
        return filepath
    except Exception as e:
        log(f"Error saving reviewed content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def get_css_styles():
    return """
        body {
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            margin: 0;
            padding: 15px;
            background: #0a0a0a;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        .top-bar {
            text-align: center;
            background: #1a1a1a;
            padding: 15px 20px;
            border-radius: 6px;
            border: 1px solid #333;
            margin-bottom: 20px;
        }
        .title {
            color: #00ffff;
            margin: 0;
            font-size: 18px;
            font-weight: 500;
        }
        .stats {
            color: #888;
            font-size: 12px;
            margin: 5px 0 0 0;
        }
        .nav-links {
            margin-top: 10px;
        }
        .nav-link {
            color: #00ffff;
            text-decoration: none;
            font-size: 14px;
            margin: 0 10px;
        }
        .nav-link:hover {
            text-decoration: underline;
        }
        .post-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 15px;
            max-width: 600px;
            margin: 0 auto;
        }
        .post {
            background: #1a1a1a;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 20px;
            position: relative;
            width: 100%;
            box-sizing: border-box;
        }
        .post-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }
        .post-actions {
            display: flex;
            gap: 10px;
        }
        .radio-option, .checkbox-option {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
            color: #e0e0e0;
        }
        .radio-option input[type="radio"],
        .checkbox-option input[type="checkbox"] {
            margin: 0;
            accent-color: #00ffff;
        }
        .caption-textarea {
            width: 100%;
            min-height: 80px;
            background: #000;
            color: #00ff00;
            border: 1px solid #333;
            border-radius: 4px;
            padding: 10px;
            box-sizing: border-box;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
            font-size: 14px;
            margin-top: 10px;
        }
        .tweet-text {
            color: #e0e0e0;
            margin: 10px 0;
            line-height: 1.4;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            font-size: 14px;
        }
        .tweet-meta {
            color: #888;
            font-size: 11px;
            margin: 5px 0;
        }
        .engagement {
            background: #2a2a2a;
            color: #00ffff;
            padding: 4px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            display: inline-block;
            margin: 2px 2px 0 0;
        }
        .media-preview, .media-container {
            margin-top: 10px;
            padding: 8px;
            background: #141414;
            border-radius: 4px;
            border: 1px solid #333;
        }
        .media-preview {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
        }
        .media-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
        }
        .media-text {
            color: #00ffff;
            font-size: 12px;
            margin-bottom: 5px;
        }
        .image-thumb, .media-item img, .media-item video {
            max-width: 120px;
            max-height: 90px;
            border-radius: 3px;
            border: 1px solid #333;
            object-fit: contain;
        }
        .media-item img, .media-item video {
            max-width: 150px;
            max-height: 150px;
        }
        .tweet-link {
            color: #00ffff;
            font-size: 11px;
            text-decoration: none;
            margin-top: 5px;
            display: inline-block;
        }
        .tweet-link:hover {
            text-decoration: underline;
        }
        .submit-section {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #333;
        }
        .submit-btn {
            background: #00ffff;
            color: #000;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            font-family: inherit;
            transition: all 0.2s;
        }
        .submit-btn:hover {
            background: #00cccc;
            transform: translateY(-1px);
        }
        .workflow-steps {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .step {
            padding: 10px 15px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .step.active {
            background: #00ffff;
            color: #000;
        }
        .step.completed {
            background: #00ff00;
            color: #000;
        }
        .step.pending {
            background: #333;
            color: #888;
        }
        .error-message {
            background: #1a0a0a;
            color: #ff6666;
            border: 1px solid #ff3333;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
            margin: 20px 0;
        }
    """

class ContentWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path_parts = self.path.strip('/').split('/')

        if len(path_parts) == 1 and path_parts[0] == '':
            self.serve_home()
        elif len(path_parts) == 1 and path_parts[0]:
            profile_name = path_parts[0]
            self.serve_profile_home(profile_name)
        elif len(path_parts) == 2 and path_parts[1] == 'approve':
            profile_name = path_parts[0]
            self.serve_approval_page(profile_name)
        elif len(path_parts) == 2 and path_parts[1] == 'review':
            profile_name = path_parts[0]
            self.serve_review_page(profile_name)
        elif path_parts[0] == 'static':
            self.serve_static_media()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.endswith('/approve'):
            profile_name = self.path.split('/')[0]
            self.handle_approval(profile_name)
        elif self.path.endswith('/review'):
            profile_name = self.path.split('/')[0]
            self.handle_review(profile_name)
        else:
            self.send_error(404)

    def serve_home(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Content Workflow</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <h1 class="title">CONTENT WORKFLOW SYSTEM</h1>
                    <div class="stats">Manage your social media content pipeline</div>
                </div>
                <p style="text-align: center; color: #888;">Navigate to /profile_name to manage content for that profile</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def serve_profile_home(self, profile_name):
        has_filtered = load_filtered_content(profile_name) is not None
        has_approved = load_approved_content(profile_name) is not None
        has_generated = load_generated_content(profile_name) is not None

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Content Workflow - {profile_name}</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <h1 class="title">Content Workflow - {profile_name}</h1>
                    <div class="nav-links">
                        <a href="/{profile_name}/approve" class="nav-link">Approve Content</a>
                        <a href="/{profile_name}/review" class="nav-link">Review Captions</a>
                    </div>
                </div>

                <div class="workflow-steps">
                    <div class="step {'completed' if has_filtered else 'active'}">1. Scrape & Filter</div>
                    <div class="step {'completed' if has_approved else ('active' if has_filtered else 'pending')}">2. Approve Posts</div>
                    <div class="step {'completed' if has_generated else ('active' if has_approved else 'pending')}">3. Generate Captions</div>
                    <div class="step {'active' if has_generated else 'pending'}">4. Review & Schedule</div>
                </div>

                <div style="text-align: center; margin-top: 40px;">
                    {'<p style="color: #00ff00;">✓ Ready to approve filtered content</p>' if has_filtered and not has_approved else ''}
                    {'<p style="color: #00ff00;">✓ Ready to review generated captions</p>' if has_generated else ''}
                    {'<p style="color: #ff6666;">⚠ Run scraping and filtering first</p>' if not has_filtered else ''}
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def serve_approval_page(self, profile_name):
        filtered_data = load_filtered_content(profile_name)
        if not filtered_data:
            self.send_error_page(f"No filtered content found for {profile_name}. Run scraping and filtering first.")
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html>")
        html_parts.append("<head>")
        html_parts.append(f"<title>Approve Content - {profile_name}</title>")
        html_parts.append(f"<style>{get_css_styles()}</style>")
        html_parts.append("</head>")
        html_parts.append("<body>")
        html_parts.append('<div class="container">')
        html_parts.append('<div class="top-bar">')
        html_parts.append(f'<h1 class="title">Approve Content - {profile_name}</h1>')
        html_parts.append(f'<div class="stats">{filtered_data["filtered_count"]} posts | {filtered_data["filter_criteria"]["min_age_days"]}-{filtered_data["filter_criteria"]["max_age_days"]} days old</div>')
        html_parts.append('<div class="nav-links">')
        html_parts.append(f'<a href="/{profile_name}" class="nav-link">← Back</a>')
        html_parts.append('</div>')
        html_parts.append('</div>')

        html_parts.append(f'<form method="POST" action="/{profile_name}/approve">')
        html_parts.append('<div class="post-grid">')

        for i, post in enumerate(filtered_data['filtered_tweets']):
            html_parts.append('<div class="post">')
            html_parts.append('<div class="post-header">')
            html_parts.append('<div>')
            html_parts.append(f'<span class="engagement">{post.get("likes", 0)} likes</span>')
            html_parts.append(f'<span class="engagement">{post.get("retweets", 0)} RT</span>')
            html_parts.append(f'<span class="engagement">{post.get("replies", 0)} replies</span>')
            html_parts.append(f'<span class="engagement">{post.get("views", 0)} views</span>')
            html_parts.append(f'<span class="engagement">{post.get("age_days", 0)} days</span>')
            html_parts.append('</div>')
            html_parts.append('<div class="post-actions">')
            html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{i}" value="approve" id="approve-{i}"><label for="approve-{i}">Keep</label></div>')
            html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{i}" value="reject" id="reject-{i}" checked><label for="reject-{i}">Skip</label></div>')
            html_parts.append('</div>')
            html_parts.append('</div>')

            tweet_text = post.get('tweet_text', 'No text')
            truncated_text = tweet_text[:150] + ('...' if len(tweet_text) > 150 else '')
            html_parts.append(f'<div class="tweet-text">{truncated_text}</div>')

            tweet_date = post.get('tweet_date')
            if tweet_date:
                html_parts.append(f'<div class="tweet-meta">Posted: {tweet_date[:10]}</div>')

            tweet_url = post.get('tweet_url')
            if tweet_url:
                html_parts.append(f'<a href="{tweet_url}" target="_blank" class="tweet-link">View original</a>')

            media_urls = post.get('media_urls')
            if media_urls:
                html_parts.append('<div class="media-preview">')
                if media_urls == ['video']:
                    html_parts.append('<div class="media-text">VIDEO</div>')
                elif media_urls and len(media_urls) > 0:
                    image_urls = [url for url in media_urls if isinstance(url, str) and url.startswith('http')]
                    if image_urls:
                        html_parts.append(f'<div class="media-text">{len(image_urls)} IMAGE(S)</div>')
                        for url in image_urls[:2]:
                            html_parts.append(f'<img src="{url}" class="image-thumb" alt="Post image">')
                    else:
                        html_parts.append(f'<div class="media-text">{len(media_urls)} MEDIA FILE(S)</div>')
                html_parts.append('</div>')

            html_parts.append('</div>')

        html_parts.append('</div>')
        html_parts.append('<div class="submit-section">')
        html_parts.append('<button type="submit" class="submit-btn">Save Approvals</button>')
        html_parts.append('</div>')
        html_parts.append('</form>')
        html_parts.append('</div>')
        html_parts.append('</body>')
        html_parts.append('</html>')

        html = '\n'.join(html_parts)
        self.wfile.write(html.encode())

    def serve_review_page(self, profile_name):
        suggestions_data = load_generated_content(profile_name)
        if not suggestions_data:
            self.send_error_page(f"No generated content found for {profile_name}. Run content generation first.")
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        generated_posts = suggestions_data.get('generated_posts', [])

        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html>")
        html_parts.append("<head>")
        html_parts.append(f"<title>Review Content - {profile_name}</title>")
        html_parts.append(f"<style>{get_css_styles()}</style>")
        html_parts.append("</head>")
        html_parts.append("<body>")
        html_parts.append('<div class="container">')
        html_parts.append('<div class="top-bar">')
        html_parts.append(f'<h1 class="title">Review Content - {profile_name}</h1>')
        html_parts.append(f'<div class="stats">{len(generated_posts)} posts to review</div>')
        html_parts.append('<div class="nav-links">')
        html_parts.append(f'<a href="/{profile_name}" class="nav-link">← Back</a>')
        html_parts.append('</div>')
        html_parts.append('</div>')

        html_parts.append(f'<form method="POST" action="/{profile_name}/review">')
        html_parts.append('<div class="post-grid">')

        for post in generated_posts:
            tweet_id = post.get('tweet_id', 'unknown')
            original_caption = post.get('tweet_text', 'No original text')
            generated_caption = post.get('generated_caption', 'No caption generated')
            tweet_url = post.get('tweet_url', '#')
            media_urls = post.get('downloaded_media_paths', [])

            html_parts.append('<div class="post">')
            html_parts.append('<div class="post-header">')
            html_parts.append(f'<h3>Post ID: {tweet_id}</h3>')
            html_parts.append(f'<a href="{tweet_url}" target="_blank" class="tweet-link">Original Tweet</a>')
            html_parts.append('</div>')
            html_parts.append('<div class="post-content">')
            html_parts.append(f'<h4>Original Text:</h4><p>{original_caption}</p>')
            html_parts.append(f'<h4>Generated Caption:</h4>')
            html_parts.append(f'<textarea name="caption_{tweet_id}" class="caption-textarea">{generated_caption}</textarea>')

            if media_urls:
                html_parts.append(f'<h4>Media:</h4>')
                html_parts.append('<div class="media-container">')
                for media_path in media_urls:
                    if media_path and os.path.exists(media_path):
                        relative_browser_path = os.path.join('/static', profile_name, os.path.relpath(media_path, get_suggestions_dir(profile_name)))

                        media_type = 'image' if media_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) else 'video'
                        html_parts.append('<div class="media-item">')
                        if media_type == 'image':
                            html_parts.append(f'<img src="{relative_browser_path}" alt="Media">')
                        else:
                            html_parts.append(f'<video controls src="{relative_browser_path}"></video>')
                        html_parts.append(f'<label class="checkbox-option">')
                        html_parts.append(f'<input type="checkbox" name="media_keep_{tweet_id}" value="{media_path}" checked>')
                        html_parts.append(f'Keep')
                        html_parts.append(f'</label>')
                        html_parts.append('</div>')
                html_parts.append('</div>')

            html_parts.append('</div>')
            html_parts.append('</div>')

        html_parts.append('</div>')
        html_parts.append('<div class="submit-section">')
        html_parts.append('<button type="submit" class="submit-btn">Save All Changes</button>')
        html_parts.append('</div>')
        html_parts.append('</form>')
        html_parts.append('</div>')
        html_parts.append('</body>')
        html_parts.append('</html>')

        html = ''.join(html_parts)
        self.wfile.write(html.encode())

    def serve_static_media(self):
        path_parts = self.path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[0] == 'static':
            profile_name = path_parts[1]
            media_relative_path = os.path.join(*path_parts[2:])

            media_root_dir = get_suggestions_dir(profile_name)
            full_path = os.path.join(media_root_dir, media_relative_path)

            if os.path.exists(full_path) and os.path.isfile(full_path):
                try:
                    with open(full_path, 'rb') as f:
                        content = f.read()
                    self.send_response(200)
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(full_path)
                    if mime_type:
                        self.send_header('Content-type', mime_type)
                    else:
                        self.send_header('Content-type', 'application/octet-stream')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except Exception as e:
                    log(f"Error serving static file {full_path}: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
                    self.send_error(500, "Error serving file")
            else:
                log(f"Static media file not found: {full_path}", verbose=False, is_error=True, log_caller_file="web_app.py")
                self.send_error(404, "File not found")
        else:
            self.send_error(404, "Invalid static media request")

    def handle_approval(self, profile_name):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = urllib.parse.parse_qs(post_data)

        filtered_data = load_filtered_content(profile_name)
        if not filtered_data:
            self.send_error(404, "No filtered content found")
            return

        approved_posts = []
        for i, post in enumerate(filtered_data['filtered_tweets']):
            decision_key = f'decision-{i}'
            if decision_key in parsed_data and parsed_data[decision_key][0] == 'approve':
                approved_posts.append(post)

        if approved_posts:
            saved_file = save_approved_content(profile_name, approved_posts)
            filename = os.path.basename(saved_file)
        else:
            filename = None

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Approvals Saved!</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <div class="success-title" style="color: #00ff00; font-size: 24px;">APPROVALS SAVED</div>
                    <strong>{len(approved_posts)} posts approved</strong><br><br>
                    {'File saved: ' + filename if filename else 'No posts approved'}<br><br>
                    <a href="/{profile_name}" class="nav-link">← Back to Workflow</a>
                </div>
            </div>
        </body>
        </html>
        """

        self.wfile.write(html.encode())

    def handle_review(self, profile_name):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = urllib.parse.parse_qs(post_data)

        suggestions_data = load_generated_content(profile_name)
        if not suggestions_data:
            self.send_error(404, "No generated content found")
            return

        generated_posts = suggestions_data.get('generated_posts', [])
        updated_posts = []

        for post in generated_posts:
            tweet_id = post.get('tweet_id')
            if tweet_id:
                new_caption = parsed_data.get(f'caption_{tweet_id}', [''])[0]
                kept_media = parsed_data.get(f'media_keep_{tweet_id}', [])

                post['generated_caption'] = new_caption
                post['media_urls'] = kept_media
                post['downloaded_media_paths'] = kept_media

            updated_posts.append(post)

        suggestions_data['generated_posts'] = updated_posts
        suggestions_data['metadata']['last_review_timestamp'] = datetime.now().isoformat()

        saved_file = save_reviewed_content(profile_name, updated_posts)
        filename = os.path.basename(saved_file) if saved_file else "No file saved"

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Changes Saved!</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <div class="success-title" style="color: #00ff00; font-size: 24px;">CHANGES SAVED</div>
                    <strong>{len(updated_posts)} posts reviewed</strong><br><br>
                    File saved: {filename}<br><br>
                    <a href="/{profile_name}" class="nav-link">← Back to Workflow</a>
                </div>
            </div>
        </body>
        </html>
        """

        self.wfile.write(html.encode())

    def send_error_page(self, message):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <h1 class="title">Error</h1>
                </div>
                <div class="error-message">
                    {message}
                </div>
                <div style="text-align: center; margin-top: 20px;">
                    <a href="/" class="nav-link">← Back to Home</a>
                </div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

def run_web_app(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ContentWebHandler)
    log(f"Starting unified content web app on http://localhost:{port}", verbose=False, log_caller_file="web_app.py")
    log("Press Ctrl+C to stop", verbose=False, log_caller_file="web_app.py")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped by user", verbose=False, log_caller_file="web_app.py")
        httpd.shutdown()
    except Exception as e:
        log(f"Error starting web server: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
