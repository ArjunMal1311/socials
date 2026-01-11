import os
import json
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

def get_filtered_file(profile_name):
    suggestions_dir = f"tmp/suggestions/{profile_name}"
    if not os.path.exists(suggestions_dir):
        return None

    filtered_files = [f for f in os.listdir(suggestions_dir) if f.startswith('filtered_content_') and f.endswith('.json')]
    if not filtered_files:
        return None

    filtered_files.sort(reverse=True)
    return os.path.join(suggestions_dir, filtered_files[0])

def load_filtered_content(profile_name):
    filepath = get_filtered_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None

def save_approved_content(profile_name, approved_posts):
    suggestions_dir = f"tmp/suggestions/{profile_name}"
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

class ApprovalHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path_parts = self.path.strip('/').split('/')
        if len(path_parts) == 1 and path_parts[0]:
            profile_name = path_parts[0]
            self.serve_approval_page(profile_name)
        else:
            self.serve_home()

    def do_POST(self):
        if self.path.startswith('/approve/'):
            profile_name = self.path.split('/approve/')[1]
            self.handle_approval(profile_name)
        else:
            self.send_error(404)

    def serve_home(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Content Approval</title>
            <style>
                body {
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                    text-align: center;
                    margin: 0;
                    padding: 50px 20px;
                    background: #0a0a0a;
                    color: #e0e0e0;
                    min-height: 100vh;
                }
                .container {
                    background: #1a1a1a;
                    padding: 40px;
                    border-radius: 8px;
                    border: 1px solid #333;
                    box-shadow: 0 0 20px rgba(0,255,255,0.1);
                    display: inline-block;
                    max-width: 600px;
                }
                h1 {
                    color: #00ffff;
                    margin: 0 0 20px 0;
                    font-size: 28px;
                }
                p {
                    color: #e0e0e0;
                    margin: 10px 0;
                    font-size: 16px;
                }
                .example {
                    background: #2a2a2a;
                    padding: 15px;
                    border-radius: 4px;
                    margin-top: 20px;
                    font-family: monospace;
                    color: #00ffff;
                    border: 1px solid #333;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>CONTENT APPROVAL SYSTEM</h1>
                <p>Navigate to /profile_name to approve content</p>
                <div class="example">Example: http://localhost:5000/</div>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def serve_approval_page(self, profile_name):
        filtered_data = load_filtered_content(profile_name)
        if not filtered_data:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"No filtered content found. Run 'socials utils " + profile_name.encode() + b" suggestions filter' first.")
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html_parts = []
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html>")
        html_parts.append("<head>")
        html_parts.append(f"<title>Content Approval - {profile_name}</title>")
        html_parts.append("<style>")
        html_parts.append("""
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
            .radio-option {
                display: flex;
                align-items: center;
                gap: 5px;
                font-size: 12px;
                color: #e0e0e0;
            }
            .radio-option input[type="radio"] {
                margin: 0;
                accent-color: #00ffff;
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
            .media-preview {
                margin-top: 10px;
                padding: 8px;
                background: #141414;
                border-radius: 4px;
                border: 1px solid #333;
            }
            .media-text {
                color: #00ffff;
                font-size: 12px;
                margin-bottom: 5px;
            }
            .images {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
            }
            .image-thumb {
                max-width: 120px;
                max-height: 90px;
                border-radius: 3px;
                border: 1px solid #333;
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
        """)
        html_parts.append("</style>")
        html_parts.append("</head>")
        html_parts.append("<body>")
        html_parts.append('<div class="container">')
        html_parts.append('<div class="top-bar">')
        html_parts.append(f'<h1 class="title">Content Approval - {profile_name}</h1>')
        html_parts.append(f'<div class="stats">{filtered_data["filtered_count"]} posts | {filtered_data["filter_criteria"]["min_age_days"]}-{filtered_data["filter_criteria"]["max_age_days"]} days old</div>')
        html_parts.append('</div>')

        html_parts.append(f'<form method="POST" action="/approve/{profile_name}">')
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
                        html_parts.append('<div class="images">')
                        for url in image_urls[:2]:  # Show max 2 images in grid
                            html_parts.append(f'<img src="{url}" class="image-thumb" alt="Post image">')
                        html_parts.append('</div>')
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
            <style>
                body {{
                    font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                    text-align: center;
                    margin: 0;
                    padding: 50px 20px;
                    background: #0a0a0a;
                    color: #e0e0e0;
                    min-height: 100vh;
                }}
                .success {{
                    background: #1a1a1a;
                    padding: 40px;
                    border-radius: 8px;
                    border: 1px solid #333;
                    box-shadow: 0 0 20px rgba(0,255,255,0.1);
                    display: inline-block;
                    max-width: 500px;
                }}
                .success-title {{
                    color: #00ff00;
                    font-size: 24px;
                    margin-bottom: 20px;
                    text-shadow: 0 0 10px rgba(0,255,0,0.5);
                }}
                .success strong {{
                    color: #00ffff;
                }}
                .back-link {{
                    color: #00ffff;
                    text-decoration: none;
                    font-weight: 500;
                    margin-top: 20px;
                    display: inline-block;
                }}
                .back-link:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="success">
                <div class="success-title">APPROVALS SAVED</div>
                <strong>{len(approved_posts)} posts approved</strong><br><br>
                {'File saved: ' + filename if filename else 'No posts approved'}<br><br>
                <a href="/{profile_name}" class="back-link">BACK TO APPROVAL</a>
            </div>
        </body>
        </html>
        """

        self.wfile.write(html.encode())

def run_server(port=5000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, ApprovalHandler)
    print(f"Server running at http://localhost:{port}")
    print("Navigate to http://localhost:5000/profile_name")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
        httpd.shutdown()

