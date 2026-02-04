# socials linkedin <profile> scraper profiles

import os
import sys
import json
import argparse

from datetime import datetime
from dotenv import load_dotenv
from rich.status import Status
from rich.console import Console

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.support.logger_util import _log as log
from services.platform.linkedin.support.scraper_utils import scrape_linkedin_profiles
from services.support.path_config import initialize_directories, get_linkedin_scraper_dir

console = Console()

# for linkedin for one profile the website was using some v2 thing
# and when tried for another was using feed thing
# add both approaches v2 is implemented in previous commits
# feed thing is implemented currently remove after doing

def main():
    load_dotenv()
    initialize_directories()
    parser = argparse.ArgumentParser(description="LinkedIn Scraper CLI Tool")

    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use for authentication and configuration")
    parser.add_argument("mode", choices=["profiles"], help="Scrape mode: 'profiles' for target profiles")
    parser.add_argument("target", nargs='?', help="Target for scraping (optional)")

    args = parser.parse_args()

    profile = args.profile
    if profile not in PROFILES:
        log(f"Profile '{profile}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        log("Please create a profiles.py file based on profiles.sample.py to define your profiles.", False, is_error=True, status=None, api_info=None, log_caller_file="scraper.py")
        sys.exit(1)

    profile_name = profile

    profile_props = PROFILES[profile].get('properties', {})
    global_props = profile_props.get('global', {})
    platform_props = profile_props.get('platform', {})
    linkedin_props = platform_props.get('linkedin', {})
    scraper_props = linkedin_props.get('scraper', {})

    browser_profile = global_props.get('browser_profile')
    linkedin_target_profiles = scraper_props.get('target_profiles', [])
    max_posts_linkedin_profile = scraper_props.get('count', 10)
    verbose = global_props.get('verbose', False)
    headless = global_props.get('headless', True)

    actual_browser_profile = browser_profile if browser_profile else profile_name

    if args.mode == "profiles":
        if not linkedin_target_profiles:
            log(f"No linkedin_target_profiles found for {profile}. Add linkedin_target_profiles to profiles.py", verbose, is_error=True, log_caller_file="scraper.py")
            sys.exit(1)

        with Status(f"[white]Scraping {len(linkedin_target_profiles)} LinkedIn profiles for {actual_browser_profile}...[/white]", spinner="dots", console=console) as status:
            scraped_posts = scrape_linkedin_profiles(
                linkedin_target_profiles=linkedin_target_profiles,
                profile_name=actual_browser_profile,
                max_posts_per_profile=max_posts_linkedin_profile,
                headless=headless,
                status=status,
                verbose=verbose
            )
            status.stop()

            if scraped_posts:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_dir = os.path.join(get_linkedin_scraper_dir(profile_name), "profiles")
                os.makedirs(output_dir, exist_ok=True)

                output_file = os.path.join(output_dir, f"linkedin_posts_{timestamp}.json")

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(scraped_posts, f, indent=2, ensure_ascii=False)

                log(f"LinkedIn scraping complete. Scraped {len(scraped_posts)} posts to {output_file}", verbose, log_caller_file="scraper.py")
                console.print(f"[green]Scraped {len(scraped_posts)} LinkedIn posts[/green]")
            else:
                log("No posts were scraped", verbose, is_error=True, log_caller_file="scraper.py")
                console.print("[red]No posts were scraped[/red]")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
