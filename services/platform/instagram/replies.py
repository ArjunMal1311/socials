# socials instagram <profile> replies

import os
import sys
import json
import argparse

from datetime import datetime
from dotenv import load_dotenv

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import get_instagram_replies_dir, ensure_dir_exists

from services.platform.instagram.support.replies_utils import generate_replies_for_approval, post_approved_replies

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Instagram Replies CLI Tool")

    parser.add_argument("profile", type=str, help="Profile name to use for authentication and configuration. Must match a profile defined in the profiles configuration.")
    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve all generated replies and skip manual review.")
    parser.add_argument("--dry-run", action="store_true", help="Generate replies but do not actually post them.")
    args = parser.parse_args()
    profile = args.profile

    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="replies.py")
        sys.exit(1)

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    instagram_props = platform_props.get('instagram', {})
    replies_props = instagram_props.get('replies', {})

    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    max_comments = replies_props.get('comments', 50)
    number_of_reels = replies_props.get('count', 1)
    download_reels = replies_props.get('download_reels', True)


    with Status(f'[white]Generating Instagram replies for {profile}...[/white]', spinner="dots", console=console) as status:
        generated_replies, driver = generate_replies_for_approval(profile, max_comments, number_of_reels, download_reels, verbose, headless)
        status.stop()

    if not generated_replies:
        log("No replies were generated.", verbose, is_error=True, log_caller_file="replies.py")
        if driver:
            driver.quit()
        return

    if not driver:
        log("Browser driver not available for posting. Aborting.", verbose, is_error=True, log_caller_file="replies.py")
        return

    replies_dir = get_instagram_replies_dir(profile)
    ensure_dir_exists(replies_dir)
    replies_file = os.path.join(replies_dir, "replies.json")

    results = []
    for reply_data in generated_replies:
        record = {
            'reel_id': reply_data['reel_url'].split('/reels/')[1].split('/')[0] if '/reels/' in reply_data['reel_url'] else '',
            'reel_url': reply_data['reel_url'],
            'reel_text': '',
            'reel_date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'likes': 0,
            'comments': reply_data['comments_count'],
            'views': 0,
            'shares': 0,
            'media_urls': [reply_data['video_path']] if reply_data.get('video_path') else [],
            'generated_reply': reply_data['generated_reply'],
            'profile_name': profile,
            'status': 'ready_for_approval',
            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        results.append(record)

    with open(replies_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log(f"Saved {len(results)} generated replies to {replies_file}", verbose, log_caller_file="replies.py")
    if args.auto_approve:
        for record in results:
            record['status'] = 'approved'
        with open(replies_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        log(f"Auto-approved {len(results)} replies.", verbose, log_caller_file="replies.py")
    else:
        log("Edit the file to change 'status' from 'ready_for_approval' to 'approved' for replies you want to post.", verbose, log_caller_file="replies.py")
        log("Press Enter when you are done reviewing and want to post approved replies.", verbose, log_caller_file="replies.py")
        input()

    if not os.path.exists(replies_file):
        log(f"Replies file not found: {replies_file}", verbose, is_error=True, log_caller_file="replies.py")
        driver.quit()
        return

    with open(replies_file, 'r') as f:
        try:
            items = json.load(f)
        except Exception as e:
            log(f"Failed to read replies file: {e}", verbose, is_error=True, log_caller_file="replies.py")
            driver.quit()
            return

    approved_replies = [item for item in items if item.get('generated_reply') and item.get('status') == 'approved']

    if not approved_replies:
        log("No approved replies found to post.", verbose, log_caller_file="replies.py")
        driver.quit()
        return

    formatted_replies = []
    for item in approved_replies:
        reply_data = {
            'reel_number': items.index(item) + 1,
            'reel_url': item['reel_url'],
            'comments_count': item['comments'],
            'generated_reply': item['generated_reply'],
            'video_path': item['media_urls'][0] if item['media_urls'] else None,
            'approved': True
        }
        formatted_replies.append(reply_data)

    with Status(f"[white]Posting {len(formatted_replies)} approved replies...[/white]", spinner="dots", console=console) as status:
        if args.dry_run:
            log(f"[DRY RUN] Would post {len(formatted_replies)} replies.", verbose, log_caller_file="replies.py")
            summary = {'posted': len(formatted_replies), 'failed': 0}
        else:
            summary = post_approved_replies(driver, formatted_replies, verbose, headless)
        status.stop()

    for item in items:
        if item.get('status') == 'approved':
            if item['reel_url'] in [r['reel_url'] for r in formatted_replies]:
                item['status'] = 'posted'
            else:
                item['status'] = 'failed'

    with open(replies_file, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    log(f"Posting complete - Posted: {summary['posted']}, Failed: {summary['failed']}", verbose, log_caller_file="replies.py")

    driver.quit()
    log("WebDriver closed.", verbose, log_caller_file="replies.py")

if __name__ == "__main__":
    main()
