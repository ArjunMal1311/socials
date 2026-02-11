import os
import sys
import argparse

from dotenv import load_dotenv

from profiles import PROFILES

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.support.logger_util import _log as log
from services.support.path_config import initialize_directories
from services.support.storage.storage_factory import get_storage

from services.utils.learning.support.instagram_learning import process_instagram_learning

def main():
    load_dotenv()
    initialize_directories()

    parser = argparse.ArgumentParser(description="Learning Utility - Explain concepts from social media posts")
    parser.add_argument("profile", type=str, help="Profile name to use")
    
    args = parser.parse_args()
    profile_name = args.profile

    if profile_name not in PROFILES:
        log(f"Profile '{profile_name}' not found.", True, is_error=True)
        sys.exit(1)

    profile_config = PROFILES[profile_name]
    global_props = profile_config.get('properties', {}).get('global', {})
    verbose = global_props.get('verbose', False)
    model_name = global_props.get('model_name', 'gemini-2.5-flash-lite')
    
    prompts = profile_config.get('prompts', {})
    learning_prompt = prompts.get('learning_prompt')
    
    if not learning_prompt:
        log(f"No 'learning_prompt' found for profile '{profile_name}'. Please add it to profiles.py", verbose, is_error=True)
        sys.exit(1)

    storage = get_storage('instagram', profile_name, 'learning', verbose)
    if not storage:
        log("Failed to initialize Instagram Learning Storage.", verbose, is_error=True)
        sys.exit(1)

    scraper_config = profile_config.get('properties', {}).get('platform', {}).get('instagram', {}).get('scraper', {})
    profiles_scraper_config = scraper_config.get('profiles_scraper', {})
    target_profiles = profiles_scraper_config.get('target_profiles', [])
    
    if not target_profiles:
        log("No target profiles found in profiles_scraper configuration.", verbose, is_error=True)
        sys.exit(1)

    log(f"Starting Learning Utility for profile '{profile_name}'", verbose)
    
    process_instagram_learning(
        profile_name=profile_name,
        target_profiles=target_profiles,
        learning_prompt=learning_prompt,
        model_name=model_name,
        storage=storage,
        verbose=verbose
    )

    log("Learning Utility completed successfully.", verbose)

if __name__ == "__main__":
    main()
