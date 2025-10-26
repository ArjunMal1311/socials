import os
import html
import json

from datetime import datetime
from rich.console import Console
from typing import List, Dict, Any, Optional
from services.support.path_config import get_action_schedule_file_path, get_review_html_path

console = Console()

def _log(message: str, verbose: bool, is_error: bool = False):
    if verbose or is_error:
      timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      color = "bold red" if is_error else "white"
      console.print(f"[action_mode_html.py] {timestamp}|[{color}]{message}[/{color}]")

MEDIA_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
MEDIA_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def _render_media_tags(media_files: List[str]) -> str:
    if isinstance(media_files, str):
        media_files = [media_files] if media_files else []
    if not media_files:
        return '<div class="empty">No media</div>'
    tags = []
    for mf in media_files:
        ext = os.path.splitext(mf)[1].lower()
        if ext in MEDIA_VIDEO_EXTS:
            tags.append(f'<video controls preload="metadata" src="{html.escape(mf)}"></video>')
        else:
            tags.append(f'<img loading="lazy" src="{html.escape(mf)}" />')
    return '\n'.join(tags)


def build_action_mode_schedule_html(profile_name: str, verbose: bool = False) -> Optional[str]:
    schedule_path = get_action_schedule_file_path(profile_name)
    if not os.path.exists(schedule_path):
        _log(f"Action Mode Schedule not found: {schedule_path}", verbose, is_error=True)
        return None

    try:
        with open(schedule_path, 'r') as f:
            items: List[Dict[str, Any]] = json.load(f)
    except Exception as e:
        _log(f"Failed to read Action Mode schedule file: {e}", verbose, is_error=True)
        return None

    title = f"Action Mode Review - {profile_name}"

    item_blocks = []
    for idx, item in enumerate(items, start=1):
        media_files = item.get('media_files', []) or []
        tweet_text = html.escape(item.get('tweet_text', '') or '')
        reply_text = html.escape(item.get('generated_reply', '') or '')
        tweet_url = item.get('tweet_url') or ''
        tweet_url_tag = f'<a href="{html.escape(tweet_url)}" target="_blank" rel="noopener">Open Tweet</a>' if tweet_url else ''
        header = f"Tweet {idx}"
        media_html = _render_media_tags(media_files)
        tweet_id = html.escape(str(item.get('tweet_id', idx)))
        status_val = html.escape(str(item.get('status', 'ready_for_approval')))
        block = f"""
    <section class="card" data-tweet-id="{tweet_id}" data-index="{idx-1}">
      <div class="media">
        {media_html}
      </div>
      <div class="content">
        <div class="meta">
          <div class="title">{header}</div>
          <div class="links">{tweet_url_tag}</div>
        </div>
        <div class="tweet"><strong>Tweet</strong><p>{tweet_text}</p></div>
        <div class="reply">
          <strong>Generated Reply</strong>
          <textarea class="reply-input">{reply_text}</textarea>
          <div class="toolbar">
            <select class="status-select">
              <option value="ready_for_approval"{' selected' if status_val=='ready_for_approval' else ''}>ready_for_approval</option>
              <option value="approved"{' selected' if status_val=='approved' else ''}>approved</option>
              <option value="rejected"{' selected' if status_val=='rejected' else ''}>rejected</option>
            </select>
            <button class="btn-update">Update</button>
            <button class="btn-delete danger">Delete</button>
            <span class="save-indicator" aria-live="polite"></span>
          </div>
        </div>
      </div>
    </section>
    """
        item_blocks.append(block)

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0b0b0c;
      --fg: #f2f2f3;
      --muted: #8c8c90;
      --card: #151518;
      --accent: #8a5cf6;
      --border: #232327;
      --danger: #f04747;
      --ok: #36b24a;
    }}
    html, body {{ margin: 0; padding: 0; background: var(--bg); color: var(--fg); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Noto Sans, "Apple Color Emoji", "Segoe UI Emoji"; }}
    .container {{ max-width: 1200px; margin: 24px auto; padding: 0 16px; }}
    h1 {{ font-size: 20px; font-weight: 600; margin: 8px 0 16px; }}
    .actions {{ margin-bottom: 16px; display:flex; gap:8px; }}
    .card {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    .media {{ display: grid; gap: 10px; align-content: start; }}
    img, video {{ width: 100%; border-radius: 8px; background: #000; }}
    .content {{ display: grid; gap: 12px; align-content: start; }}
    .meta {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; color: var(--muted); }}
    .title {{ color: var(--fg); font-weight: 600; }}
    .links a {{ color: var(--accent); text-decoration: none; }}
    .links a:hover {{ text-decoration: underline; }}
    .tweet, .reply {{ background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; border: 1px solid var(--border); }}
    .tweet strong, .reply strong {{ color: var(--muted); font-size: 12px; letter-spacing: .02em; text-transform: uppercase; }}
    .tweet p {{ margin: 6px 0 0; white-space: pre-wrap; }}
    .reply textarea.reply-input {{ margin-top: 6px; width: 100%; min-height: 120px; resize: vertical; border-radius: 8px; border: 1px solid var(--border); background: #0f0f12; color: var(--fg); padding: 10px; }}
    .toolbar {{ margin-top: 8px; display: flex; gap: 8px; align-items: center; }}
    .btn-update {{ background: var(--ok); color: #fff; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    .btn-delete {{ background: var(--danger); color: #fff; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    select.status-select {{ background: #0f0f12; color: var(--fg); border: 1px solid var(--border); border-radius: 6px; padding: 6px; }}
    .save-indicator {{ font-size: 12px; color: var(--muted); min-width: 80px; }}
    @media (max-width: 900px) {{ .card {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{html.escape(title)}</h1>
    <div class="actions">
      <button id="refresh">Refresh</button>
    </div>
    {''.join(item_blocks)}
  </div>
  <script>
    async function post(url, payload) {{
      const res = await fetch(url, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }}

    function initCard(card) {{
      const tweetId = card.getAttribute('data-tweet-id');
      const index = parseInt(card.getAttribute('data-index'));
      const replyInput = card.querySelector('.reply-input');
      const statusSelect = card.querySelector('.status-select');
      const btnUpdate = card.querySelector('.btn-update');
      const btnDelete = card.querySelector('.btn-delete');
      const indicator = card.querySelector('.save-indicator');

      function setIndicator(text, ok=true) {{
        indicator.textContent = text || '';
        indicator.style.color = ok ? 'var(--muted)' : 'var(--danger)';
      }}

      btnUpdate?.addEventListener('click', async () => {{
        try {{
          setIndicator('Saving...');
          btnUpdate.disabled = true;
          const fields = {{ generated_reply: replyInput.value, status: statusSelect.value }};
          const payload = tweetId ? {{ tweet_id: tweetId, fields }} : {{ index, fields }};
          const res = await post('/api/update', payload);
          if (!res.ok) throw new Error('Update failed');
          setIndicator('Saved');
        }} catch (e) {{
          console.error(e);
          setIndicator('Error saving', false);
          alert('Update failed: ' + e.message);
        }} finally {{
          btnUpdate.disabled = false;
          setTimeout(() => setIndicator(''), 2000);
        }}
      }});

      btnDelete?.addEventListener('click', async () => {{
        try {{
          if (!confirm('Delete this item?')) return;
          setIndicator('Deleting...');
          btnDelete.disabled = true;
          const payload = tweetId ? {{ tweet_id: tweetId }} : {{ index }};
          const res = await post('/api/delete', payload);
          if (!res.ok) throw new Error('Delete failed');
          card.remove();
        }} catch (e) {{
          console.error(e);
          setIndicator('Error deleting', false);
          alert('Delete failed: ' + e.message);
        }} finally {{
          btnDelete.disabled = false;
        }}
      }});
    }}

    document.querySelectorAll('.card').forEach(initCard);
    document.getElementById('refresh')?.addEventListener('click', () => location.reload());
  </script>
</body>
</html>
"""

    out_path = get_review_html_path(profile_name, "action")
    try:
        with open(out_path, 'w') as f:
            f.write(html_doc)
        _log(f"Generated Action Mode review HTML: {out_path}", verbose)
        return out_path
    except Exception as e:
        _log(f"Failed to write Action Mode review HTML: {e}", verbose, is_error=True)
        return None

