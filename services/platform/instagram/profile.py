# socials instagram <profile> profiles

import os
import sys
import json
import argparse

from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.support.logger_util import _log as log
from services.support.path_config import ensure_dir_exists, get_platform_profile_dir

from services.platform.instagram.support.scout_utils import scout_profile_posts

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Instagram Profile Posts Scraper")
    parser.add_argument("profile", type=str, help="The configuration profile to use")
    
    args = parser.parse_args()
    profile = args.profile

    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES.", False, is_error=True, log_caller_file="profile.py")
        sys.exit(1)

    # profile parameters
    profile_props = PROFILES[profile].get('properties', {})
    instagram_props = profile_props.get('platform', {}).get('instagram', {})
    scout_config = instagram_props.get('scout', {}).get('profiles_scout', {})
    
    target_profiles = scout_config.get('target_profiles', [])
    count = scout_config.get('count', 5)
    
    verbose = profile_props.get('global', {}).get('verbose', False)
    headless = profile_props.get('global', {}).get('headless', True)

    if not target_profiles:
        log("No target profiles defined in configuration.", verbose, is_error=True, log_caller_file="profile.py")
        sys.exit(1)

    log(f"Starting scouting for targets: {target_profiles} (count: {count})", verbose, log_caller_file="profile.py")

    driver = None
    all_posts = []
    try:
        for target in target_profiles:
            with Status(f"[white]Scraping profile: {target}...[/white]", spinner="dots", console=console) as status:
                driver_instance, posts = scout_profile_posts(profile_name=profile, target_profile=target, count=count, verbose=verbose, headless=headless, status=status)
                
                if driver_instance:
                    driver = driver_instance

                if posts:
                    all_posts.extend(posts)
                    log(f"Found {len(posts)} posts for {target}", verbose, log_caller_file="profile.py")
                else:
                    log(f"No posts found for {target}", verbose, log_caller_file="profile.py")

        if all_posts:
            # Detailed Enrichment Pass for Posts (/p/)
            posts_to_enrich = [p for p in all_posts if "/p/" in p.get('post_url', '')]
            if posts_to_enrich:
                log(f"Enriching {len(posts_to_enrich)} posts using 'Default' profile session...", verbose, log_caller_file="profile.py")
                
                # Close the grid scout driver
                if driver:
                    driver.quit()
                    driver = None
                
                # Setup "Default" driver for detailed scraping
                from services.platform.instagram.support.scout_utils import scout_instagram_post_details
                from services.support.path_config import get_browser_data_dir
                from services.support.web_driver_handler import setup_driver
                
                # Use "Default" profile as requested by user
                default_browser_data_dir = get_browser_data_dir("Default", "instagram")
                driver, _ = setup_driver(default_browser_data_dir, profile="Default", headless=headless)
                
                if driver:
                    with Status("[white]Scraping post details...[/white]", spinner="dots", console=console) as status:
                        for post in all_posts:
                            if "/p/" in post.get('post_url', ''):
                                details = scout_instagram_post_details(driver, post['post_url'], verbose=verbose, status=status)
                                post['caption'] = details.get('caption') or post.get('caption')
                                post['image_urls'] = details.get('image_urls', [])
                                if post['image_urls']:
                                    post['thumbnail_url'] = post['image_urls'][0]
                                log(f"Enriched post: {post['post_url']}", verbose, log_caller_file="profile.py")

            output_dir = os.path.join(get_platform_profile_dir("instagram", profile), "profiles")
            ensure_dir_exists(output_dir)
            output_file = os.path.join(output_dir, "posts.json")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_posts, f, ensure_ascii=False, indent=4)
                
            log(f"Saved total {len(all_posts)} posts to {output_file}", verbose, log_caller_file="profile.py")

    except Exception as e:
        log(f"An unexpected error occurred: {e}", verbose, is_error=True, log_caller_file="profile.py")
    finally:
        if driver:
            driver.quit()
            log("WebDriver closed.", verbose, log_caller_file="profile.py")

if __name__ == "__main__":
    main()
