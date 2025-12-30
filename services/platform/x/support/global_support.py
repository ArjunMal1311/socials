import os
import shutil

from profiles import PROFILES

from services.support.logger_util import _log as log
from services.support.web_driver_handler import setup_driver
from services.support.path_config import get_browser_data_dir, get_profiles_file_path

def init_profile(profile_name: str):
    if profile_name not in PROFILES:
        log(f"Profile '{profile_name}' not found in PROFILES. Creating new profile...", verbose=True, log_caller_file="global_functions.py")

        profiles_file_path = get_profiles_file_path()
        try:
            with open(profiles_file_path, 'r') as f:
                content = f.read()

            lines = content.split('\n')
            insert_index = -1

            brace_count = 0
            in_profiles = False
            for i, line in enumerate(lines):
                if 'PROFILES = {' in line:
                    in_profiles = True
                    brace_count = 1
                elif in_profiles:
                    brace_count += line.count('{')
                    brace_count -= line.count('}')

                    if brace_count == 0 and '}' in line.strip():
                        insert_index = i
                        break

            if insert_index > 0:
                profile_lines = [
                    f'    "{profile_name}": {{',
                    f'        "name": "",',
                    f'        "prompt": "",',
                    f'        "engagement_analysis_prompt": "",',
                    f'        "data": {{',
                    f'            "reddit": {{',
                    f'                "subreddits": [],',
                    f'                "time_filter": [],',
                    f'                "reddit_min_comments": 0,',
                    f'                "reddit_include_comments": False,',
                    f'                "max_posts_per_sub": 0,',
                    f'                "reddit_user_prompt": ""',
                    f'            }},',
                    f'            "google_search": {{',
                    f'                "search_queries": [],',
                    f'                "time_filter": "",',
                    f'                "num_results": 0,',
                    f'                "google_user_prompt": ""',
                    f'            }},',
                    f'            "youtube_scraper": {{',
                    f'                "search_query": "",',
                    f'                "max_videos": 0,',
                    f'                "time_filter": "",',
                    f'                "max_duration_minutes": 0,',
                    f'                "youtube_user_prompt": ""',
                    f'            }}',
                    f'        }},',
                    f'        "target_profiles": [],',
                    f'        "properties": {{',
                    f'            "count": 17,',
                    f'            "ignore_video_tweets": False,',
                    f'            "verbose": False,',
                    f'            "headless": True,',
                    f'            "browser_profile": "Default",',
                    f'            "max_tweets": 500,',
                    f'            "specific_url": ""',
                    f'        }},',
                    f'        "prompts": {{',
                    f'            "content_ideas": "",',
                    f'            "script_generation_prompt": "",',
                    f'            "idea_prompt": "",',
                    f'            "reply_generation": ""',
                    f'        }}',
                    f'    }},'
                ]

                for profile_line in reversed(profile_lines):
                    lines.insert(insert_index, profile_line)

                with open(profiles_file_path, 'w') as f:
                    f.write('\n'.join(lines))

                log(f"Successfully added profile '{profile_name}' to profiles.py", verbose=True, log_caller_file="global_functions.py")
            else:
                log(f"Could not find PROFILES closing brace in profiles.py", verbose=True, is_error=True, log_caller_file="global_functions.py")
                return False

        except Exception as e:
            log(f"Failed to add profile '{profile_name}' to profiles.py: {e}", verbose=True, is_error=True, log_caller_file="global_functions.py")
            return False

    browser_dir = get_browser_data_dir(profile_name)

    if os.path.exists(browser_dir):
        log(f"Browser profile '{profile_name}' already exists at: {browser_dir}", verbose=True, log_caller_file="global_functions.py")
        return True

    try:
        os.makedirs(browser_dir, exist_ok=True)
        log(f"Successfully initialized browser profile '{profile_name}' at: {browser_dir}", verbose=True, log_caller_file="global_functions.py")
        return True
    except Exception as e:
        log(f"Failed to initialize browser profile '{profile_name}': {e}", verbose=True, is_error=True, log_caller_file="global_functions.py")
        return False

def delete_profile(profile_name: str):
    if profile_name not in PROFILES:
        log(f"Profile '{profile_name}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", verbose=True, is_error=True, log_caller_file="global_functions.py")
        return False

    browser_dir = get_browser_data_dir(profile_name)

    del PROFILES[profile_name]
    log(f"Removed profile '{profile_name}' from PROFILES dictionary", verbose=True, log_caller_file="global_functions.py")

    profiles_file_path = get_profiles_file_path()
    try:
        with open(profiles_file_path, 'r') as f:
            content = f.read()

        lines = content.split('\n')
        new_lines = []
        skip_lines = False
        brace_count = 0

        for line in lines:
            if f'    "{profile_name}": {{' in line:
                skip_lines = True
                brace_count = 1
                continue
            elif skip_lines:
                brace_count += line.count('{')
                brace_count -= line.count('}')
                if brace_count == 0 and line.rstrip() == '    },':
                    skip_lines = False
                    continue
                continue
            else:
                new_lines.append(line)

        with open(profiles_file_path, 'w') as f:
            f.write('\n'.join(new_lines))

        log(f"Successfully removed profile '{profile_name}' from profiles.py", verbose=True, log_caller_file="global_functions.py")
    except Exception as e:
        log(f"Failed to remove profile '{profile_name}' from profiles.py: {e}", verbose=True, is_error=True, log_caller_file="global_functions.py")
        return False

    if os.path.exists(browser_dir):
        try:
            shutil.rmtree(browser_dir)
            log(f"Successfully deleted browser data directory for profile '{profile_name}'", verbose=True, log_caller_file="global_functions.py")
        except Exception as e:
            log(f"Warning: Could not delete browser directory {browser_dir}: {e}", verbose=True, log_caller_file="global_functions.py")

    return True

def login_profile(profile_name: str):
    if profile_name not in PROFILES:
        log(f"Profile '{profile_name}' not found in PROFILES. Available profiles: {', '.join(PROFILES.keys())}", verbose=True, is_error=True, log_caller_file="global_support.py")
        return False

    browser_dir = get_browser_data_dir(profile_name)

    if not os.path.exists(browser_dir):
        log(f"Browser profile '{profile_name}' does not exist. Please run 'socials x {profile_name} global init' first.", verbose=True, is_error=True, log_caller_file="global_support.py")
        return False

    try:
        log(f"Opening browser for profile '{profile_name}' to login to X...", verbose=True, log_caller_file="global_support.py")

        driver, _ = setup_driver(browser_dir, profile=profile_name, headless=False, verbose=True)

        driver.get("https://x.com/login")
        log(f"Opened X login page. Please login manually in the browser.", verbose=True, log_caller_file="global_support.py")

        input("Press Enter to continue after logging in...")

        driver.quit()
        log(f"Browser closed. Profile '{profile_name}' login session completed.", verbose=True, log_caller_file="global_support.py")
        return True

    except Exception as e:
        log(f"Failed to open browser for profile '{profile_name}': {e}", verbose=True, is_error=True, log_caller_file="global_support.py")
        return False
