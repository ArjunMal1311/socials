import os
import shutil

BASE_TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")

def get_base_dir() -> str:
    return BASE_TMP_DIR

def get_browser_data_dir(profile_name: str, platform: str = None) -> str:
    if platform:
        platform_dir = os.path.join(BASE_TMP_DIR, "browser-data", f"{profile_name}_{platform}")
        base_dir = os.path.join(BASE_TMP_DIR, "browser-data", profile_name)

        if not os.path.exists(platform_dir) and os.path.exists(base_dir):
            try:
                print(f"Copying browser data from {profile_name} to {profile_name}_{platform}...")
                shutil.copytree(base_dir, platform_dir)
                print(f"Successfully created platform-specific browser directory: {profile_name}_{platform}")
            except Exception as e:
                print(f"Warning: Could not copy browser data: {e}")
                return base_dir

        return platform_dir

    return os.path.join(BASE_TMP_DIR, "browser-data", profile_name)

def get_cache_dir() -> str:
    return os.path.join(BASE_TMP_DIR, "cache")

def get_downloads_dir() -> str:
    return os.path.join(BASE_TMP_DIR, "downloads")

def get_eternity_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "eternity-x", profile_name)

def get_logs_dir() -> str:
    return os.path.join(BASE_TMP_DIR, "logs")

def get_pool_dir() -> str:
    return os.path.join(BASE_TMP_DIR, "pool")

def get_replies_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "replies-x", profile_name)

def get_schedule_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "schedule", profile_name)

def get_scrape_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "scrape", profile_name)

def get_community_scrape_dir(profile_name: str) -> str:
    return os.path.join(get_scrape_dir(profile_name), "community")

def get_home_scrape_dir(profile_name: str) -> str:
    return os.path.join(get_scrape_dir(profile_name), "home")

def get_profiles_scrape_dir(profile_name: str) -> str:
    return os.path.join(get_scrape_dir(profile_name), "profiles")

def get_url_scrape_dir(profile_name: str) -> str:
    return os.path.join(get_scrape_dir(profile_name), "url")

def get_suggestions_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "suggestions", profile_name)

def get_instagram_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "instagram", profile_name)

def get_instagram_reels_dir(profile_name: str) -> str:
    return os.path.join(get_instagram_profile_dir(profile_name), "reels")

def get_instagram_videos_dir(profile_name: str) -> str:
    return os.path.join(get_instagram_profile_dir(profile_name), "videos")

def get_youtube_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "youtube", profile_name)

def get_youtube_videos_dir(profile_name: str) -> str:
    return os.path.join(get_downloads_dir(), "youtube", profile_name, "videos")

def get_youtube_captions_dir(profile_name: str) -> str:
    return os.path.join(get_youtube_profile_dir(profile_name), "captions")

def get_youtube_shorts_dir(profile_name: str) -> str:
    return os.path.join(get_youtube_profile_dir(profile_name), "shorts")

def get_youtube_replies_for_review_dir(profile_name: str) -> str:
    return os.path.join(get_youtube_profile_dir(profile_name), "replies_for_review")

def get_youtube_schedule_videos_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "schedule-videos", profile_name)

def ensure_dir_exists(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path

def get_schedule_file_path(profile_name: str) -> str:
    return os.path.join(get_schedule_dir(profile_name), "schedule.json")

def get_eternity_schedule_file_path(profile_name: str) -> str:
    return os.path.join(get_eternity_dir(profile_name), "schedule.json")

def get_action_schedule_file_path(profile_name: str) -> str:
    return os.path.join(get_replies_dir(profile_name), "schedule.json")

def get_turbin_schedule_file_path(profile_name: str) -> str:
    return os.path.join(get_replies_dir(profile_name), "schedule.json")

def get_review_html_path(profile_name: str, mode: str = "action") -> str:
    if mode == "eternity":
        return os.path.join(get_eternity_dir(profile_name), "review.html")
    elif mode == "turbin":
        return os.path.join(get_replies_dir(profile_name), "review.html")
    else:
        return os.path.join(get_replies_dir(profile_name), "review.html")

def get_api_log_file_path() -> str:
    return os.path.join(get_logs_dir(), "api_calls_log.json")

def get_gemini_log_file_path() -> str:
    return os.path.join(get_logs_dir(), "gemini_api_calls_log.json")

def get_reddit_log_file_path(profile_name: str) -> str:
    return os.path.join(get_logs_dir(), "reddit_api_calls_log.json")

def get_youtube_log_file_path(profile_name: str) -> str:
    return os.path.join(get_logs_dir(), "youtube_api_calls_log.json")

def get_temp_media_dir(profile_name: str, mode: str = "action") -> str:
    if mode == "eternity":
        base_dir = get_eternity_dir(profile_name)
    elif mode == "turbin":
        base_dir = get_replies_dir(profile_name)
    else:
        base_dir = get_replies_dir(profile_name)
    
    temp_dir = os.path.join(base_dir, "_temp_media")
    return ensure_dir_exists(temp_dir)

def get_schedule2_file_path(profile_name: str) -> str:
    return os.path.join(get_schedule_dir(profile_name), "schedule2.json")

def get_profiles_file_path() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'profiles.py'))

def get_scrape_output_file_path(profile_name: str, scrape_type: str, target_name: str, timestamp: str) -> str:
    if scrape_type == "community":
        base_dir = get_community_scrape_dir(profile_name)
    elif scrape_type == "home":
        base_dir = get_home_scrape_dir(profile_name)
    elif scrape_type == "profiles":
        base_dir = get_profiles_scrape_dir(profile_name)
    elif scrape_type == "url":
        base_dir = get_url_scrape_dir(profile_name)
    else:
        base_dir = get_scrape_dir(profile_name)
    return os.path.join(base_dir, f"{target_name}_{timestamp}.json")

def get_linkedin_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "linkedin", profile_name)

def get_linkedin_output_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "linkedin", profile_name)

def get_titles_output_dir(profile_name: str) -> str:
    path = os.path.join(BASE_TMP_DIR, "ideas", profile_name, "titles")
    return ensure_dir_exists(path)

def get_scripts_output_dir(profile_name: str) -> str:
    path = os.path.join(BASE_TMP_DIR, "ideas", profile_name, "scripts")
    return ensure_dir_exists(path)

def get_linkedin_html_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "linkedin", profile_name, "html")

def get_linkedin_data_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "linkedin", profile_name, "data")

def get_reddit_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "reddit", profile_name)

def get_reddit_analysis_dir(profile_name: str) -> str:
    return os.path.join(get_reddit_profile_dir(profile_name), "analysis")

def get_google_log_file_path(profile_name: str) -> str:
    return os.path.join(get_logs_dir(), "google_api_calls_log.json")

def get_google_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "google", profile_name)

def get_google_analysis_dir(profile_name: str) -> str:
    return os.path.join(get_google_profile_dir(profile_name), "analysis")

def get_product_hunt_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "product_hunt", profile_name)

def get_product_hunt_output_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "product-hunt", profile_name)

def get_product_hunt_scrape_output_file_path(profile_name: str, timestamp: str) -> str:
    base_dir = get_product_hunt_output_dir(profile_name)
    return os.path.join(base_dir, f"product_hunt_{timestamp}.json")

def get_yc_profile_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "ycombinator", profile_name)

def get_yc_output_dir(profile_name: str) -> str:
    return os.path.join(BASE_TMP_DIR, "ycombinator", profile_name)

def get_yc_scrape_output_file_path(profile_name: str, timestamp: str) -> str:
    base_dir = get_yc_output_dir(profile_name)
    return os.path.join(base_dir, f"ycombinator_{timestamp}.json")

def get_ideas_aggregated_dir(profile_name: str) -> str:
    path = os.path.join(BASE_TMP_DIR, "ideas", profile_name, "aggregated")
    return ensure_dir_exists(path)

def initialize_directories() -> None:
    directories = [
        get_base_dir(),
        get_cache_dir(),
        get_downloads_dir(),
        get_logs_dir(),
        get_pool_dir(),
    ]
    
    for directory in directories:
        ensure_dir_exists(directory)
