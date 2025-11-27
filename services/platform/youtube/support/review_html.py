import os
import html

from rich.console import Console
from typing import List, Dict, Any

console = Console()

MEDIA_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}

def _render_media_tags(video_path: str) -> str:
    if not video_path:
        return '<div class="empty">No media</div>'
    ext = os.path.splitext(video_path)[1].lower()
    if ext in MEDIA_VIDEO_EXTS:
        filename = os.path.basename(video_path)
        return f'<video controls preload="metadata" src="media/{html.escape(filename)}"></video>'
    return '<div class="empty">Unsupported media type</div>'


def build_youtube_review_html(profile_name: str, items: List[Dict[str, Any]], verbose: bool = False) -> str:
    title = f"YouTube Replies Review - {profile_name}"

    item_blocks = []
    for idx, item in enumerate(items, start=1):
        video_url = item.get('video_url', '') or ''
        generated_reply = html.escape(item.get('generated_reply', '') or '')
        scraped_comments = item.get('scraped_comments', []) or []
        video_path = item.get('video_path', '') or ''
        reply_id = html.escape(str(item.get('id', idx)))
        status_val = html.escape(str(item.get('status', 'pending')))
        header = f"Reply {idx}"
        media_html = _render_media_tags(video_path)

        comments_html_parts = []
        for comment in scraped_comments[:10]:
            author = html.escape(comment.get('author', 'Unknown'))
            comment_text = html.escape(comment.get('comment', ''))
            likes = comment.get('likes', 0)
            comments_html_parts.append(f"""
                <div class="comment-item">
                    <span class="author">{author}</span>
                    <span class="likes">{likes} likes</span>
                    <p>{comment_text}</p>
                </div>
            """
            )
        comments_html = ''.join(comments_html_parts)

        block = f"""
<section class="card" data-reply-id="{reply_id}" data-index="{idx-1}">
  <div class="media">
    {media_html}
  </div>
  <div class="content">
    <div class="meta">
      <div class="title">{header}</div>
      <div class="links"><a href="{html.escape(video_url)}" target="_blank" rel="noopener">Open Video</a></div>
    </div>
    <div class="generated-reply">
      <strong>Generated Reply</strong>
      <textarea class="reply-input">{generated_reply}</textarea>
      <div class="toolbar">
        <select class="status-select">
          <option value="pending"{' selected' if status_val=='pending' else ''}>pending</option>
          <option value="approved"{' selected' if status_val=='approved' else ''}>approved</option>
          <option value="rejected"{' selected' if status_val=='rejected' else ''}>rejected</option>
          <option value="posted"{' selected' if status_val=='posted' else ''}>posted</option>
        </select>
        <button class="btn-update">Update</button>
        <button class="btn-delete danger">Delete</button>
        <span class="save-indicator" aria-live="polite"></span>
      </div>
    </div>
    <div class="scraped-comments">
      <strong>Scraped Comments (Top 10)</strong>
      {comments_html}
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
    .generated-reply, .scraped-comments {{ background: rgba(255,255,255,0.02); padding: 12px; border-radius: 8px; border: 1px solid var(--border); }}
    .generated-reply strong, .scraped-comments strong {{ color: var(--muted); font-size: 12px; letter-spacing: .02em; text-transform: uppercase; }}
    .generated-reply textarea.reply-input {{ margin-top: 6px; width: 100%; min-height: 120px; resize: vertical; border-radius: 8px; border: 1px solid var(--border); background: #0f0f12; color: var(--fg); padding: 10px; }}
    .toolbar {{ margin-top: 8px; display: flex; gap: 8px; align-items: center; }}
    .btn-update {{ background: var(--ok); color: #fff; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    .btn-delete {{ background: var(--danger); color: #fff; border: 0; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    select.status-select {{ background: #0f0f12; color: var(--fg); border: 1px solid var(--border); border-radius: 6px; padding: 6px; }}
    .save-indicator {{ font-size: 12px; color: var(--muted); min-width: 80px; }}
    .comment-item {{ background: #0f0f12; border: 1px solid var(--border); padding: 8px; border-radius: 5px; margin-bottom: 5px; }}
    .comment-item .author {{ font-weight: bold; color: var(--fg); }}
    .comment-item .likes {{ float: right; color: var(--muted); font-size: 0.9em; }}
    @media (max-width: 900px) {{ .card {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>{html.escape(title)}</h1>
    <div class="actions">
      <button id="refresh">Refresh</button>
    </div>
    {' '.join(item_blocks)}
  </div>
  <script>
    async function post(url, payload) {{
      const res = await fetch(url, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(payload) }});
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }}

    function initCard(card) {{
      const replyId = card.getAttribute('data-reply-id');
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
          const payload = replyId ? {{ id: replyId, fields }} : {{ index, fields }};
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
          const payload = replyId ? {{ id: replyId }} : {{ index }};
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
</html>"""
    return html_doc
