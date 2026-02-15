from services.support.logger_util import _log as log
from services.support.path_config import get_browser_data_dir

from services.platform.x.support.reply_home import setup_driver
from services.platform.x.support.follow_utils import follow_user

def extract_usernames_from_x_urls(urls):
    usernames = []
    for url in urls:
        if isinstance(url, str):
            if 'twitter.com/' in url or 'x.com/' in url:
                if 'twitter.com/' in url:
                    username_part = url.split('twitter.com/')[-1].split('/')[0].split('?')[0]
                else:
                    username_part = url.split('x.com/')[-1].split('/')[0].split('?')[0]

                username = username_part.lstrip('@')
                if username and username != 'home' and not username.startswith('status/'):
                    usernames.append(username)
    return usernames

def process_x_connections(usernames, profile_name, verbose, status, limit=15, headless=True):
    if not usernames:
        return {"successful": 0, "failed": 0}

    successful = 0
    failed = 0

    user_data_dir = get_browser_data_dir(profile_name)

    try:
        log("Setting up WebDriver for X connections...", verbose, status, log_caller_file="x_connector.py")
        driver, setup_messages = setup_driver(user_data_dir, profile=profile_name, headless=headless)
        for msg in setup_messages:
            log(msg, verbose, status, log_caller_file="x_connector.py")

        processed_usernames = usernames[:limit] if len(usernames) > limit else usernames

        for username in processed_usernames:
            try:
                log(f"Attempting to follow {username} on X", verbose, status, log_caller_file="x_connector.py")
                success, result = follow_user(driver, username, verbose=verbose, status=status)

                if success:
                    successful += 1
                    log(f"Successfully followed {username} on X", verbose, status, log_caller_file="x_connector.py")
                elif result == "already_following":
                    successful += 1
                    log(f"Already following {username} on X", verbose, status, log_caller_file="x_connector.py")
                else:
                    failed += 1
                    log(f"Failed to follow {username} on X: {result}", verbose, is_error=True, status=status, log_caller_file="x_connector.py")

            except Exception as e:
                failed += 1
                log(f"Error following {username} on X: {e}", verbose, is_error=True, status=status, log_caller_file="x_connector.py")

        if driver:
            driver.quit()

    except Exception as e:
        log(f"Error setting up WebDriver for X connections: {e}", verbose, is_error=True, log_caller_file="x_connector.py")
        return {"successful": 0, "failed": len(processed_usernames)}

    return {"successful": successful, "failed": failed}
