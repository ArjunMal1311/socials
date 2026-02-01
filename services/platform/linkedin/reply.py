# socials linkedin <profile> reply home

import os
import sys
import argparse

from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories, get_linkedin_replies_dir

from services.platform.linkedin.support.reply_utils import run_linkedin_reply_mode, post_approved_linkedin_replies

console = Console()

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="LinkedIn Replies CLI Tool")

    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration")
    parser.add_argument("mode", choices=["home"], help="Reply mode: 'home' for home feed replies")

    args = parser.parse_args()

    if args.profile not in PROFILES:
        log(f"Profile '{args.profile}' not found in PROFILES.", verbose=True, is_error=True, log_caller_file="reply.py")
        sys.exit(1)

    profile_props = PROFILES[args.profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    linkedin_props = platform_props.get('linkedin', {})
    reply_props = linkedin_props.get('reply', {})

    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)
    max_posts = reply_props.get('count', 10)

    browser_profile = args.profile

    replies_file = os.path.join(get_linkedin_replies_dir(args.profile), "replies.json")

    if args.mode == "home":
        with Status(f'[white]Running LinkedIn reply mode for home feed...[/white]', spinner="dots", console=console) as status:
            driver, replies_data = run_linkedin_reply_mode(args.profile, browser_profile, max_posts=max_posts, verbose=verbose, headless=headless, status=status)
            status.stop()

            if replies_data:
                log(f"Generated {len(replies_data)} LinkedIn replies", verbose, log_caller_file="reply.py")
                console.print(f"[green]Generated {len(replies_data)} LinkedIn replies[/green]")
                console.print(f"[yellow]Review replies in: {replies_file}[/yellow]")
                console.print("[yellow]Edit the file and set 'approved': true for replies you want to post[/yellow]")
                console.print("[yellow]Press Enter here when you are done reviewing the generated replies and want to post them.[/yellow]")

                input()

                with Status(f"[white]Posting approved LinkedIn replies for {args.profile}...[/white]", spinner="dots", console=console) as status:
                    summary = post_approved_linkedin_replies(driver, args.profile, verbose=verbose, status=status)
                    status.stop()
                    log(f"Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}", verbose, log_caller_file="reply.py")
                    console.print(f"[green]Processed: {summary['processed']}, Posted: {summary['posted']}, Failed: {summary['failed']}[/green]")
            else:
                log("No replies were generated", verbose, is_error=True, log_caller_file="reply.py")
                console.print("[red]No replies were generated[/red]")

            if driver:
                driver.quit()

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
