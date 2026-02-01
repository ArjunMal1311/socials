import os
import shutil

# Base directory
BASE_TMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tmp")

# =============================================================================
# BASE FUNCTIONS
# =============================================================================

def get_base_dir() -> str:
    """Get the base tmp directory."""
    return BASE_TMP_DIR

def ensure_dir_exists(path: str) -> str:
    """Create directory if it doesn't exist and return the path."""
    os.makedirs(path, exist_ok=True)
    return path

def get_profiles_file_path() -> str:
    """Get path to profiles.py file."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'profiles.py'))

# =============================================================================
# SHARED DIRECTORIES (non-platform specific)
# =============================================================================

def get_browser_data_dir(profile_name: str, platform: str = None) -> str:
    """Get browser data directory for profile (optionally platform-specific)."""
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
    """Get cache directory."""
    return os.path.join(BASE_TMP_DIR, "cache")

def get_downloads_dir() -> str:
    """Get downloads directory."""
    return os.path.join(BASE_TMP_DIR, "downloads")

def get_logs_dir() -> str:
    """Get logs directory."""
    return os.path.join(BASE_TMP_DIR, "logs")

def get_pool_dir() -> str:
    """Get pool directory."""
    return os.path.join(BASE_TMP_DIR, "pool")

# =============================================================================
# PLATFORM HIERARCHY FUNCTIONS
# =============================================================================

def get_platform_dir(platform: str) -> str:
    """Get platform base directory: platform/{platform}"""
    return os.path.join(BASE_TMP_DIR, "platform", platform)

def get_platform_profile_dir(platform: str, profile: str) -> str:
    """Get platform profile directory: platform/{platform}/{profile}"""
    return os.path.join(get_platform_dir(platform), profile)

# =============================================================================
# X (Twitter) PLATFORM
# =============================================================================

def get_x_scraper_dir(profile: str) -> str:
    """Get X scraper directory: platform/x/{profile}/scraper"""
    return os.path.join(get_platform_profile_dir("x", profile), "scraper")

def get_x_scraper_home_dir(profile: str) -> str:
    """Get X home feed scraper directory: platform/x/{profile}/scraper/home"""
    return os.path.join(get_x_scraper_dir(profile), "home")

def get_x_scraper_community_dir(profile: str) -> str:
    """Get X community scraper directory: platform/x/{profile}/scraper/community"""
    return os.path.join(get_x_scraper_dir(profile), "community")

def get_x_scraper_profiles_dir(profile: str) -> str:
    """Get X profiles scraper directory: platform/x/{profile}/scraper/profiles"""
    return os.path.join(get_x_scraper_dir(profile), "profiles")

def get_x_scraper_url_dir(profile: str) -> str:
    """Get X URL scraper directory: platform/x/{profile}/scraper/url"""
    return os.path.join(get_x_scraper_dir(profile), "url")

def get_x_replies_dir(profile: str) -> str:
    """Get X replies directory: platform/x/{profile}/replies"""
    return os.path.join(get_platform_profile_dir("x", profile), "replies")

def get_x_posts_dir(profile: str) -> str:
    """Get X posts directory: platform/x/{profile}/posts"""
    return os.path.join(get_platform_profile_dir("x", profile), "posts")

def get_x_media_dir(profile: str) -> str:
    """Get X media directory: platform/x/{profile}/media"""
    return os.path.join(get_platform_profile_dir("x", profile), "media")

# =============================================================================
# LINKEDIN PLATFORM
# =============================================================================

def get_linkedin_scraper_dir(profile: str) -> str:
    """Get LinkedIn scraper directory: platform/linkedin/{profile}/scraper"""
    return os.path.join(get_platform_profile_dir("linkedin", profile), "scraper")

def get_linkedin_replies_dir(profile: str) -> str:
    """Get LinkedIn replies directory: platform/linkedin/{profile}/replies"""
    return os.path.join(get_platform_profile_dir("linkedin", profile), "replies")

def get_linkedin_connections_dir(profile: str) -> str:
    """Get LinkedIn connections directory: platform/linkedin/{profile}/connections"""
    return os.path.join(get_platform_profile_dir("linkedin", profile), "connections")

def get_linkedin_posts_dir(profile: str) -> str:
    """Get LinkedIn posts directory: platform/linkedin/{profile}/posts"""
    return os.path.join(get_platform_profile_dir("linkedin", profile), "posts")

def get_linkedin_messages_dir(profile: str) -> str:
    """Get LinkedIn messages directory: platform/linkedin/{profile}/messages"""
    return os.path.join(get_platform_profile_dir("linkedin", profile), "messages")

# =============================================================================
# REDDIT PLATFORM
# =============================================================================

def get_reddit_scraper_dir(profile: str) -> str:
    """Get Reddit scraper directory: platform/reddit/{profile}/scraper"""
    return os.path.join(get_platform_profile_dir("reddit", profile), "scraper")

def get_reddit_analysis_dir(profile: str) -> str:
    """Get Reddit analysis directory: platform/reddit/{profile}/analysis"""
    return os.path.join(get_platform_profile_dir("reddit", profile), "analysis")

# =============================================================================
# YOUTUBE PLATFORM
# =============================================================================

def get_youtube_videos_dir(profile: str) -> str:
    """Get YouTube videos directory: platform/youtube/{profile}/videos"""
    return os.path.join(get_platform_profile_dir("youtube", profile), "videos")

def get_youtube_captions_dir(profile: str) -> str:
    """Get YouTube captions directory: platform/youtube/{profile}/captions"""
    return os.path.join(get_platform_profile_dir("youtube", profile), "captions")

def get_youtube_shorts_dir(profile: str) -> str:
    """Get YouTube shorts directory: platform/youtube/{profile}/shorts"""
    return os.path.join(get_platform_profile_dir("youtube", profile), "shorts")

def get_youtube_replies_dir(profile: str) -> str:
    """Get YouTube replies directory: platform/youtube/{profile}/replies"""
    return os.path.join(get_platform_profile_dir("youtube", profile), "replies")

def get_schedule_videos_dir(profile: str) -> str:
    """Get scheduled videos directory."""
    return os.path.join(BASE_TMP_DIR, "schedule-videos", profile)

# =============================================================================
# OTHER PLATFORMS
# =============================================================================

def get_instagram_reels_dir(profile: str) -> str:
    """Get Instagram reels directory: platform/instagram/{profile}/reels"""
    return os.path.join(get_platform_profile_dir("instagram", profile), "reels")

def get_instagram_videos_dir(profile: str) -> str:
    """Get Instagram videos directory: platform/instagram/{profile}/videos"""
    return os.path.join(get_platform_profile_dir("instagram", profile), "videos")

def get_google_analysis_dir(profile: str) -> str:
    """Get Google analysis directory: platform/google/{profile}/analysis"""
    return os.path.join(get_platform_profile_dir("google", profile), "analysis")

def get_product_hunt_scraper_dir(profile: str) -> str:
    """Get Product Hunt scraper directory: platform/producthunt/{profile}/scraper"""
    return os.path.join(get_platform_profile_dir("producthunt", profile), "scraper")

def get_ycombinator_scraper_dir(profile: str) -> str:
    """Get Y Combinator scraper directory: platform/ycombinator/{profile}/scraper"""
    return os.path.join(get_platform_profile_dir("ycombinator", profile), "scraper")

# =============================================================================
# SPECIAL DIRECTORIES
# =============================================================================

def get_ideas_titles_dir(profile: str) -> str:
    """Get ideas titles directory."""
    path = os.path.join(BASE_TMP_DIR, "ideas", profile, "titles")
    return ensure_dir_exists(path)

def get_ideas_scripts_dir(profile: str) -> str:
    """Get ideas scripts directory."""
    path = os.path.join(BASE_TMP_DIR, "ideas", profile, "scripts")
    return ensure_dir_exists(path)

def get_ideas_aggregated_dir(profile: str) -> str:
    """Get ideas aggregated directory."""
    path = os.path.join(BASE_TMP_DIR, "ideas", profile, "aggregated")
    return ensure_dir_exists(path)

# =============================================================================
# UTILS SYSTEM
# =============================================================================

def get_utils_dir() -> str:
    """Get utils base directory: utils/"""
    return os.path.join(BASE_TMP_DIR, "utils")

def get_connections_dir(profile: str) -> str:
    """Get connections directory: utils/connections/{profile}"""
    path = os.path.join(get_utils_dir(), "connections", profile)
    return ensure_dir_exists(path)

def get_suggestions_dir(profile: str) -> str:
    """Get suggestions directory: utils/suggestions/{profile}"""
    path = os.path.join(get_utils_dir(), "suggestions", profile)
    return ensure_dir_exists(path)

def get_suggestions_media_dir(profile: str) -> str:
    """Get suggestions media directory: utils/suggestions/{profile}/media"""
    path = os.path.join(get_suggestions_dir(profile), "media")
    return ensure_dir_exists(path)

# =============================================================================
# LOG FILE FUNCTIONS
# =============================================================================

def get_api_log_file_path() -> str:
    """Get API calls log file path."""
    return os.path.join(get_logs_dir(), "api_calls_log.json")

def get_gemini_log_file_path() -> str:
    """Get Gemini API calls log file path."""
    return os.path.join(get_logs_dir(), "gemini_api_calls_log.json")

def get_reddit_log_file_path(profile_name: str = None) -> str:
    """Get Reddit API calls log file path."""
    if profile_name:
        return os.path.join(get_logs_dir(), f"reddit_api_calls_log_{profile_name}.json")
    return os.path.join(get_logs_dir(), "reddit_api_calls_log.json")

def get_youtube_log_file_path() -> str:
    """Get YouTube API calls log file path."""
    return os.path.join(get_logs_dir(), "youtube_api_calls_log.json")

def get_google_log_file_path(profile_name: str = None) -> str:
    """Get Google API calls log file path."""
    if profile_name:
        return os.path.join(get_logs_dir(), f"google_api_calls_log_{profile_name}.json")
    return os.path.join(get_logs_dir(), "google_api_calls_log.json")

# =============================================================================
# OUTPUT FILE FUNCTIONS
# =============================================================================

def get_x_scraper_output_file_path(profile: str, scrape_type: str, target_name: str, timestamp: str) -> str:
    """Get X scraper output file path."""
    if scrape_type == "community":
        base_dir = get_x_scraper_community_dir(profile)
    elif scrape_type == "home":
        base_dir = get_x_scraper_home_dir(profile)
    elif scrape_type == "profiles":
        base_dir = get_x_scraper_profiles_dir(profile)
    elif scrape_type == "url":
        base_dir = get_x_scraper_url_dir(profile)
    else:
        base_dir = get_x_scraper_dir(profile)
    return os.path.join(base_dir, f"{target_name}_{timestamp}.json")

def get_reddit_scraper_output_file_path(profile: str, timestamp: str) -> str:
    """Get Reddit scraper output file path."""
    return os.path.join(get_reddit_scraper_dir(profile), f"reddit_scraped_data_{timestamp}.json")

def get_reddit_analysis_output_file_path(profile: str, timestamp: str) -> str:
    """Get Reddit analysis output file path."""
    return os.path.join(get_reddit_analysis_dir(profile), f"reddit_content_suggestions_{timestamp}.txt")

def get_linkedin_scraper_output_file_path(profile: str, target_type: str, timestamp: str) -> str:
    """Get LinkedIn scraper output file path."""
    return os.path.join(get_linkedin_scraper_dir(profile), f"linkedin_{target_type}_{timestamp}.json")

def get_product_hunt_output_file_path(profile: str, timestamp: str) -> str:
    """Get Product Hunt output file path."""
    return os.path.join(get_product_hunt_scraper_dir(profile), f"product_hunt_{timestamp}.json")

def get_ycombinator_output_file_path(profile: str, timestamp: str) -> str:
    """Get Y Combinator output file path."""
    return os.path.join(get_ycombinator_scraper_dir(profile), f"ycombinator_{timestamp}.json")

# =============================================================================
# SCHEDULE FILE FUNCTIONS
# =============================================================================

def get_schedule_file_path(profile: str) -> str:
    """Get X schedule JSON file path."""
    return os.path.join(get_x_posts_dir(profile), "schedule.json")

def get_schedule2_file_path(profile: str) -> str:
    """Get X schedule2 JSON file path."""
    return os.path.join(get_x_posts_dir(profile), "schedule2.json")

def get_eternity_schedule_file_path(profile: str) -> str:
    """Get X eternity schedule JSON file path."""
    return os.path.join(get_x_replies_dir(profile), "schedule.json")

def get_action_schedule_file_path(profile: str) -> str:
    """Get X action schedule JSON file path."""
    return os.path.join(get_x_replies_dir(profile), "schedule.json")

def get_turbin_schedule_file_path(profile: str) -> str:
    """Get X turbin schedule JSON file path."""
    return os.path.join(get_x_replies_dir(profile), "schedule.json")

# =============================================================================
# HTML AND MEDIA FUNCTIONS
# =============================================================================

def get_review_html_path(profile: str, mode: str = "action") -> str:
    """Get review HTML file path."""
    if mode == "eternity":
        base_dir = get_x_replies_dir(profile)
    elif mode == "turbin":
        base_dir = get_x_replies_dir(profile)
    else:
        base_dir = get_x_replies_dir(profile)
    return os.path.join(base_dir, "review.html")

def get_temp_media_dir(profile: str, mode: str = "action") -> str:
    """Get temporary media directory."""
    if mode == "eternity":
        base_dir = get_x_replies_dir(profile)
    elif mode == "turbin":
        base_dir = get_x_replies_dir(profile)
    else:
        base_dir = get_x_replies_dir(profile)

    temp_dir = os.path.join(base_dir, "_temp_media")
    return ensure_dir_exists(temp_dir)

# =============================================================================
# INITIALIZATION
# =============================================================================

def initialize_directories() -> None:
    """Initialize all base directories."""
    directories = [
        get_base_dir(),
        get_cache_dir(),
        get_downloads_dir(),
        get_logs_dir(),
        get_pool_dir(),
    ]

    for directory in directories:
        ensure_dir_exists(directory)
