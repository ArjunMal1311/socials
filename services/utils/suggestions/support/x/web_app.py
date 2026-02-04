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

from services.utils.suggestions.support.linkedin.content_filter import get_latest_scraped_linkedin_file

def load_filtered_content(profile_name):
    log(f"Loading filtered content for profile: {profile_name}", verbose=False, log_caller_file="web_app.py")

    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))

    try:
        import sys
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        try:
            from services.utils.suggestions.support.reddit.content_filter import get_latest_filtered_reddit_file
            reddit_filepath = get_latest_filtered_reddit_file(profile_name)
            if reddit_filepath:
                if not os.path.isabs(reddit_filepath):
                    reddit_filepath = os.path.join(project_root, reddit_filepath)

                try:
                    with open(reddit_filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'filtered_reddit_posts' in data:
                        log(f"Found Reddit filtered content with {len(data['filtered_reddit_posts'])} posts", verbose=False, log_caller_file="web_app.py")
                        return data
                except Exception as e:
                    log(f"Error reading Reddit filtered file: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        except ImportError:
            pass

        try:
            from services.utils.suggestions.support.linkedin.content_filter import get_latest_filtered_linkedin_file
            filepath = get_latest_filtered_linkedin_file(profile_name)
            log(f"LinkedIn filtered file path: {filepath}", verbose=False, log_caller_file="web_app.py")

            if filepath:
                if not os.path.isabs(filepath):
                    filepath = os.path.join(project_root, filepath)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if 'filtered_posts' in data:
                        log(f"Found LinkedIn filtered content with {len(data['filtered_posts'])} posts", verbose=False, log_caller_file="web_app.py")
                        return data
                except Exception as e:
                    log(f"Error reading LinkedIn filtered file: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        except ImportError:
            pass

        filepath = get_latest_scraped_file(profile_name)
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if 'filtered_tweets' in data:
                    return data
            except Exception as e:
                log(f"Error loading X filtered content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

        return None

    except Exception as e:
        log(f"Error loading filtered content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def load_new_generated_content(profile_name):
    import os
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return None

    linkedin_files = [f for f in os.listdir(suggestions_dir) if f.startswith('new_posts_content_linkedin_') and f.endswith('.json')]
    if linkedin_files:
        linkedin_files.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, linkedin_files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading LinkedIn new posts: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    x_files = [f for f in os.listdir(suggestions_dir) if f.startswith('new_tweets_content_x_') and f.endswith('.json')]
    if x_files:
        x_files.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, x_files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading X new tweets: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    return None

def load_approved_content(profile_name):
    import os
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return None

    linkedin_files_with_media = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_linkedin_') and f.endswith('_with_media.json')]
    if linkedin_files_with_media:
        linkedin_files_with_media.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, linkedin_files_with_media[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading LinkedIn approved content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    linkedin_files = [f for f in os.listdir(suggestions_dir) if f.startswith('approved_content_linkedin_') and f.endswith('.json') and not f.endswith('_with_media.json')]
    if linkedin_files:
        linkedin_files.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, linkedin_files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading LinkedIn approved content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    filepath = get_latest_approved_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading X approved content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def load_generated_content(profile_name):
    import os
    suggestions_dir = get_suggestions_dir(profile_name)
    if not os.path.exists(suggestions_dir):
        return None

    linkedin_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_linkedin_') and f.endswith('_reviewed.json')]
    if linkedin_files:
        linkedin_files.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, linkedin_files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading LinkedIn reviewed content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    linkedin_files = [f for f in os.listdir(suggestions_dir) if f.startswith('suggestions_content_linkedin_') and f.endswith('.json') and not f.endswith('_reviewed.json')]
    if linkedin_files:
        linkedin_files.sort(reverse=True)
        filepath = os.path.join(suggestions_dir, linkedin_files[0])
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading LinkedIn generated content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")

    filepath = get_latest_suggestions_file(profile_name)
    if not filepath:
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading X generated content: {e}", verbose=False, is_error=True, log_caller_file="web_app.py")
        return None

def save_approved_content(profile_name, approved_posts, platform='x'):
    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    platform_prefix = f"{platform}_" if platform != 'x' else ""
    filename = f"approved_content_{platform_prefix}{timestamp}.json"

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

def save_reviewed_content(profile_name, generated_posts, platform='x'):
    suggestions_dir = get_suggestions_dir(profile_name)
    os.makedirs(suggestions_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    platform_prefix = f"{platform}_" if platform != 'x' else ""
    filename = f"suggestions_content_{platform_prefix}{timestamp}_reviewed.json"

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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: white;
            color: black;
            line-height: 1.5;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 2px;
        }
        .top-bar {
            text-align: center;
            padding: 20px;
            border-bottom: 1px solid #ccc;
            margin-bottom: 20px;
        }
        .title {
            color: black;
            margin: 0 0 10px 0;
            font-size: 24px;
            font-weight: 600;
        }
        .stats {
            color: #666;
            font-size: 14px;
            margin: 0;
        }
        .nav-links {
            margin-top: 15px;
        }
        .nav-link {
            color: black;
            text-decoration: none;
            font-size: 14px;
            margin: 0 10px;
            padding: 5px 10px;
            border: 1px solid black;
            border-radius: 2px;
        }
        .nav-link:hover {
            background: #f0f0f0;
        }
        .post-grid {
            display: grid;
            gap: 20px;
        }
        .post {
            border: 1px solid #ccc;
            border-radius: 2px;
            padding: 20px;
            background: #f9f9f9;
        }
        .post-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .post-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        .radio-option, .checkbox-option {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 14px;
        }
        .radio-option input[type="radio"],
        .checkbox-option input[type="checkbox"] {
            margin: 0;
        }
        .caption-textarea {
            width: 100%;
            min-height: 100px;
            border: 1px solid #ccc;
            border-radius: 2px;
            padding: 12px;
            font-family: inherit;
            font-size: 14px;
            margin-top: 10px;
            resize: vertical;
        }
        .tweet-text {
            color: black;
            margin: 15px 0;
            font-size: 16px;
            line-height: 1.6;
        }
        .tweet-meta {
            color: #666;
            font-size: 12px;
            margin: 10px 0;
        }
        .engagement {
            background: #e0e0e0;
            color: black;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
            display: inline-block;
            margin: 2px 4px 0 0;
        }
        .media-preview, .media-container {
            margin-top: 15px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 2px;
            border: 1px solid #ccc;
        }
        .media-preview {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            justify-content: center;
        }
        .media-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }
        .media-text {
            color: #666;
            font-size: 12px;
            font-weight: 500;
        }
        .image-thumb, .media-item img, .media-item video {
            max-width: 150px;
            max-height: 100px;
            border-radius: 2px;
            border: 1px solid #ccc;
            object-fit: contain;
        }
        .media-item img, .media-item video {
            max-width: 200px;
            max-height: 200px;
        }
        .tweet-link {
            color: black;
            font-size: 14px;
            text-decoration: none;
            margin-top: 10px;
            display: inline-block;
            padding: 5px 10px;
            border: 1px solid black;
            border-radius: 2px;
        }
        .tweet-link:hover {
            background: #f0f0f0;
        }
        .submit-section {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ccc;
        }
        .submit-btn {
            background: black;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 2px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
        }
        .submit-btn:hover {
            background: #333;
        }
        .workflow-steps {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        .step {
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 14px;
            font-weight: 500;
            border: 1px solid #ccc;
        }
        .step.active {
            background: black;
            color: white;
        }
        .step.completed {
            background: #666;
            color: white;
        }
        .step.pending {
            background: white;
            color: #666;
        }
        .error-message {
            background: #f0f0f0;
            color: black;
            border: 1px solid #ccc;
            padding: 15px;
            border-radius: 2px;
            text-align: center;
            margin: 20px 0;
        }
        .success-title {
            color: black;
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 10px;
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
            profile_name = self.path.split('/')[1]
            self.handle_approval(profile_name)
        elif self.path.endswith('/review'):
            profile_name = self.path.split('/')[1]
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
                    {'<p>Ready to approve filtered content</p>' if has_filtered and not has_approved else ''}
                    {'<p>Ready to review generated captions</p>' if has_generated else ''}
                    {'<p>Run scraping and filtering first</p>' if not has_filtered else ''}
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

        is_linkedin = 'filtered_posts' in filtered_data
        posts_field = 'filtered_posts' if is_linkedin else 'filtered_tweets'

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
        html_parts.append(f'<a href="/{profile_name}" class="nav-link">Back</a>')
        html_parts.append('</div>')
        html_parts.append('</div>')

        html_parts.append(f'<form method="POST" action="/{profile_name}/approve">')
        html_parts.append('<div class="post-grid">')

        is_linkedin = 'filtered_posts' in filtered_data
        is_reddit = 'filtered_reddit_posts' in filtered_data
        posts_field = 'filtered_posts' if is_linkedin else ('filtered_reddit_posts' if is_reddit else 'filtered_tweets')

        for i, post in enumerate(filtered_data[posts_field]):
            html_parts.append('<div class="post">')
            html_parts.append('<div class="post-header">')
            html_parts.append('<div>')
            if is_linkedin:
                engagement = post.get('engagement', {})
                html_parts.append(f'<span class="engagement">{engagement.get("likes", 0)} likes</span>')
                html_parts.append(f'<span class="engagement">{engagement.get("comments", 0)} comments</span>')
                html_parts.append(f'<span class="engagement">{engagement.get("reposts", 0)} reposts</span>')
            elif is_reddit:
                engagement = post.get('engagement', {})
                html_parts.append(f'<span class="engagement">{engagement.get("score", 0)} upvotes</span>')
                html_parts.append(f'<span class="engagement">{engagement.get("num_comments", 0)} comments</span>')
                html_parts.append(f'<span class="engagement">{post.get("data", {}).get("subreddit", "unknown")} subreddit</span>')
            else:
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

            if is_linkedin:
                tweet_text = post.get('data', {}).get('text', 'No text')
                tweet_date = post.get('data', {}).get('post_date')
                tweet_url = post.get('data', {}).get('profile_url')
            elif is_reddit:
                title = post.get('data', {}).get('title', 'No title')
                content = post.get('data', {}).get('content', '')
                tweet_text = f"{title}\n\n{content}" if content else title
                tweet_date = post.get('data', {}).get('created_utc')
                tweet_url = post.get('data', {}).get('url')
            else:
                tweet_text = post.get('tweet_text', 'No text')
                tweet_date = post.get('tweet_date')
                tweet_url = post.get('tweet_url')

            truncated_text = tweet_text[:150] + ('...' if len(tweet_text) > 150 else '')
            html_parts.append(f'<div class="tweet-text">{truncated_text}</div>')

            if tweet_date:
                try:
                    date_str = tweet_date[:10] if not is_linkedin else tweet_date.split('T')[0]
                    html_parts.append(f'<div class="tweet-meta">Posted: {date_str}</div>')
                except:
                    html_parts.append(f'<div class="tweet-meta">Posted: {tweet_date[:10] if len(tweet_date) > 10 else tweet_date}</div>')

            if tweet_url:
                link_text = "View profile" if is_linkedin else "View original"
                html_parts.append(f'<a href="{tweet_url}" target="_blank" class="tweet-link">{link_text}</a>')

            if is_linkedin:
                media_urls = post.get('data', {}).get('media_urls', [])
            elif is_reddit:
                from services.utils.suggestions.support.reddit.media_downloader import extract_reddit_media_urls
                content = post.get('data', {}).get('content', '')
                post_url = post.get('data', {}).get('url', '')
                media_urls = extract_reddit_media_urls(content, post_url)
            else:
                media_urls = post.get('media_urls', [])

            if media_urls:
                html_parts.append('<div class="media-preview">')
                if media_urls and len(media_urls) > 0:
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
        approved_data = load_approved_content(profile_name)
        new_content_data = load_new_generated_content(profile_name)

        if not approved_data and not new_content_data:
            self.send_error_page(f"No content found for {profile_name}. Run 'generate' and 'generate_new' commands first.")
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        total_items = 0
        if approved_data:
            approved_posts = approved_data.get('approved_posts', [])
            total_items += len(approved_posts)
        if new_content_data:
            if new_content_data.get('platform') == 'linkedin':
                new_items = new_content_data.get('new_posts', [])
            elif new_content_data.get('platform') == 'reddit':
                new_items = new_content_data.get('new_tweets', [])
            else:
                new_items = new_content_data.get('new_tweets', [])
            total_items += len(new_items)

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
        html_parts.append(f'<div class="stats">{total_items} items to review</div>')
        html_parts.append('<div class="nav-links">')
        html_parts.append(f'<a href="/{profile_name}" class="nav-link">Back</a>')
        html_parts.append('</div>')
        html_parts.append('</div>')

        html_parts.append(f'<form method="POST" action="/{profile_name}/review">')
        html_parts.append('<div class="post-grid">')

        item_index = 0

        if approved_data:
            approved_posts = approved_data.get('approved_posts', [])
            is_linkedin_approved = approved_data.get('platform') == 'linkedin'
            is_reddit_approved = approved_data.get('platform') == 'reddit'

            for post in approved_posts:
                html_parts.append('<div class="post">')
                html_parts.append('<div class="post-header">')
                html_parts.append('<div>')
                if is_linkedin_approved:
                    engagement = post.get('engagement', {})
                    html_parts.append(f'<span class="engagement">{engagement.get("likes", 0)} likes</span>')
                    html_parts.append(f'<span class="engagement">{engagement.get("comments", 0)} comments</span>')
                    html_parts.append(f'<span class="engagement">{engagement.get("reposts", 0)} reposts</span>')
                elif is_reddit_approved:
                    engagement = post.get('engagement', {})
                    html_parts.append(f'<span class="engagement">{engagement.get("score", 0)} upvotes</span>')
                    html_parts.append(f'<span class="engagement">{engagement.get("num_comments", 0)} comments</span>')
                    html_parts.append(f'<span class="engagement">{post.get("data", {}).get("subreddit", "unknown")} subreddit</span>')
                else:
                    html_parts.append(f'<span class="engagement">{post.get("likes", 0)} likes</span>')
                    html_parts.append(f'<span class="engagement">{post.get("retweets", 0)} RT</span>')
                    html_parts.append(f'<span class="engagement">{post.get("replies", 0)} replies</span>')
                html_parts.append('<span class="engagement">APPROVED</span>')
                html_parts.append('</div>')
                html_parts.append('<div class="post-actions">')
                html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{item_index}" value="approve" id="approve-{item_index}" checked><label for="approve-{item_index}">Schedule</label></div>')
                html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{item_index}" value="reject" id="reject-{item_index}"><label for="reject-{item_index}">Skip</label></div>')
                html_parts.append('</div>')
                html_parts.append('</div>')

                if is_linkedin_approved:
                    original_text = post.get('data', {}).get('text', 'No text')
                    generated_text = post.get('generated_caption', 'No caption')
                elif is_reddit_approved:
                    title = post.get('data', {}).get('title', 'No title')
                    content = post.get('data', {}).get('content', '')
                    original_text = f"{title}\n\n{content}" if content else title
                    generated_text = post.get('generated_caption', 'No caption')
                else:
                    original_text = post.get('tweet_text', 'No text')
                    generated_text = post.get('generated_caption', 'No caption')

                html_parts.append(f'<div class="tweet-text"><strong>Original:</strong> {original_text[:200]}{"..." if len(original_text) > 200 else ""}</div>')
                html_parts.append(f'<textarea name="caption_{item_index}" class="caption-textarea">{generated_text}</textarea>')

                item_index += 1
                html_parts.append('</div>')

        if new_content_data:
            if new_content_data.get('platform') == 'linkedin':
                new_items = new_content_data.get('new_posts', [])
                item_type = "New Post"
            else:
                new_items = new_content_data.get('new_tweets', [])
                item_type = "New Tweet"

            for item in new_items:
                html_parts.append('<div class="post">')
                html_parts.append('<div class="post-header">')
                html_parts.append('<div>')
                html_parts.append(f'<span class="engagement">{item_type.upper()}</span>')
                html_parts.append('</div>')
                html_parts.append('<div class="post-actions">')
                html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{item_index}" value="approve" id="approve-{item_index}" checked><label for="approve-{item_index}">Schedule</label></div>')
                html_parts.append(f'<div class="radio-option"><input type="radio" name="decision-{item_index}" value="reject" id="reject-{item_index}"><label for="reject-{item_index}">Skip</label></div>')
                html_parts.append('</div>')
                html_parts.append('</div>')

                item_text = item.get('text', 'No content')
                html_parts.append(f'<textarea name="caption_{item_index}" class="caption-textarea">{item_text}</textarea>')

                item_index += 1
                html_parts.append('</div>')

        html_parts.append('</div>')
        html_parts.append('<div class="submit-section">')
        html_parts.append('<button type="submit" class="submit-btn">Save and Schedule</button>')
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
        log(f"Handling approval for profile: {profile_name}", verbose=False, log_caller_file="web_app.py")
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_data = urllib.parse.parse_qs(post_data)

        filtered_data = load_filtered_content(profile_name)
        if not filtered_data:
            log(f"No filtered content found for {profile_name} in handle_approval", verbose=False, is_error=True, log_caller_file="web_app.py")
            self.send_error(404, "No filtered content found")
            return

        is_linkedin = 'filtered_posts' in filtered_data
        posts_field = 'filtered_posts' if is_linkedin else 'filtered_tweets'
        platform = 'linkedin' if is_linkedin else 'x'

        approved_posts = []
        for i, post in enumerate(filtered_data[posts_field]):
            decision_key = f'decision-{i}'
            if decision_key in parsed_data and parsed_data[decision_key][0] == 'approve':
                approved_posts.append(post)

        if approved_posts:
            saved_file = save_approved_content(profile_name, approved_posts, platform)
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
                    <a href="/{profile_name}" class="nav-link">Back to Workflow</a>
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

        approved_data = load_approved_content(profile_name)
        new_content_data = load_new_generated_content(profile_name)

        if not approved_data and not new_content_data:
            self.send_error(404, "No content found")
            return

        suggestions_items = []
        item_index = 0

        if approved_data:
            approved_posts = approved_data.get('approved_posts', [])
            is_linkedin_approved = approved_data.get('platform') == 'linkedin'

            for post in approved_posts:
                decision = parsed_data.get(f'decision-{item_index}', ['reject'])[0]
                if decision == 'approve':
                    edited_caption = parsed_data.get(f'caption_{item_index}', [''])[0]

                    if is_linkedin_approved:
                        post['generated_caption'] = edited_caption
                    else:
                        post['generated_caption'] = edited_caption

                    suggestions_items.append({
                        'type': 'approved_post',
                        'platform': approved_data.get('platform', 'x'),
                        'content': post
                    })

                item_index += 1

        if new_content_data:
            if new_content_data.get('platform') == 'linkedin':
                new_items = new_content_data.get('new_posts', [])
            else:
                new_items = new_content_data.get('new_tweets', [])

            for item in new_items:
                decision = parsed_data.get(f'decision-{item_index}', ['reject'])[0]
                if decision == 'approve':
                    edited_text = parsed_data.get(f'caption_{item_index}', [''])[0]

                    item['text'] = edited_text
                    item['approved'] = True

                    suggestions_items.append({
                        'type': 'new_content',
                        'platform': new_content_data.get('platform', 'x'),
                        'content': item
                    })

                item_index += 1

        if suggestions_items:
            import json
            from services.support.path_config import get_suggestions_dir

            suggestions_dir = get_suggestions_dir(profile_name)
            os.makedirs(suggestions_dir, exist_ok=True)

            platform = suggestions_items[0]['platform'] if suggestions_items else 'x'

            existing_files = [f for f in os.listdir(suggestions_dir) if f.startswith(f"suggestions_content_{platform}_") and f.endswith('.json')]
            existing_files.sort(reverse=True)

            if existing_files:
                latest_file = os.path.join(suggestions_dir, existing_files[0])
                try:
                    with open(latest_file, 'r') as f:
                        existing_data = json.load(f)

                    if 'approved_content' not in existing_data:
                        existing_data['approved_content'] = []

                    existing_data['approved_content'].extend(suggestions_items)
                    existing_data['total_approved'] = len(existing_data['approved_content'])
                    existing_data['timestamp'] = datetime.now().isoformat()

                    with open(latest_file, 'w') as f:
                        json.dump(existing_data, f, indent=2)

                    suggestions_file = latest_file
                except Exception as e:
                    log(f"Error appending to existing suggestions file: {e}", verbose=False, log_caller_file="web_app.py")
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    suggestions_file = os.path.join(suggestions_dir, f"suggestions_content_{platform}_{timestamp}.json")

                    suggestions_data = {
                        "timestamp": datetime.now().isoformat(),
                        "profile_name": profile_name,
                        "platform": platform,
                        "approved_content": suggestions_items,
                        "total_approved": len(suggestions_items)
                    }

                    with open(suggestions_file, 'w') as f:
                        json.dump(suggestions_data, f, indent=2)
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                suggestions_file = os.path.join(suggestions_dir, f"suggestions_content_{platform}_{timestamp}.json")

                suggestions_data = {
                    "timestamp": datetime.now().isoformat(),
                    "profile_name": profile_name,
                    "platform": platform,
                    "approved_content": suggestions_items,
                    "total_approved": len(suggestions_items)
                }

                with open(suggestions_file, 'w') as f:
                    json.dump(suggestions_data, f, indent=2)

        filename = f"{len(suggestions_items)} items saved to suggestions"

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Content Saved!</title>
            <style>{get_css_styles()}</style>
        </head>
        <body>
            <div class="container">
                <div class="top-bar">
                    <div class="success-title">CONTENT SAVED TO SUGGESTIONS</div>
                    <strong>{filename}</strong><br><br>
                    <p>You can now run the <code>schedule</code> command to schedule these items.</p><br>
                    <a href="/{profile_name}" class="nav-link">Back to Workflow</a>
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
                    <a href="/" class="nav-link">Back to Home</a>
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
