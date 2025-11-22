import datetime

from typing import List, Dict, Any, Optional

def format_reddit_post(post: Dict[str, Any], time_filter: str, include_comments: bool = False, comments: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    formatted_post = {
        "source": "reddit",
        "scraped_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "engagement": {
            "score": post.get('score', 0),
            "upvote_ratio": post.get('upvote_ratio', 0.0),
            "num_comments": post.get('num_comments', 0),
        },
        "data": {
            "subreddit": post.get('subreddit', 'N/A'),
            "time_filter": time_filter,
            "title": post.get('title', 'N/A'),
            "content": post.get('selftext', post.get('url', 'N/A')), 
            "url": post.get('url', 'N/A'),
            "created_utc": post.get('created_utc', 0),
            "flair": post.get('link_flair_text', ''),
            "is_video": post.get('is_video', False),
            "awards_count": post.get('total_awards_received', 0)
        }
    }

    if include_comments and comments is not None:
        formatted_post["data"]["comments"] = [
            {
                "body": comment.get('body', 'N/A'),
                "score": comment.get('score', 0),
                "replies_count": comment.get('replies_count', 0),
                "is_awarded": bool(comment.get('total_awards_received', 0))
            } for comment in comments
        ]
    else:
        formatted_post["data"]["comments"] = []

    return formatted_post

def format_reddit_posts_list(posts: List[Dict[str, Any]], time_filter: str, include_comments: bool = False, all_comments: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    formatted_posts = []
    for post in posts:
        post_comments = all_comments.get(post["id"]) if all_comments else None
        formatted_posts.append(format_reddit_post(post, time_filter, include_comments, post_comments))
    return formatted_posts
