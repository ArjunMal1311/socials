import time

from rich.console import Console
from selenium.webdriver.common.by import By
from services.support.logger_util import _log as log
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

console = Console()

def post_to_community_tweet(driver, tweet_text, community_name, status=None, verbose: bool = False):
    try:
        if status:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        driver.get('https://x.com/compose/tweet')
        time.sleep(3)

        tweet_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
        )
        tweet_input.clear()
        tweet_input.send_keys(tweet_text)
        time.sleep(2)

        if status:
            log(f"Selecting community '{community_name}'...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Selecting community '{community_name}'...", verbose, status=status, log_caller_file="post_to_community.py")
        
        choose_audience_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Choose audience"]'))
        )
        choose_audience_button.click()
        time.sleep(2)

        community_xpath = f"//span[text()='{community_name}']"
        community_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, community_xpath))
        )
        community_element.click()
        time.sleep(2)
        
        if status:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        post_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
        )
        post_button.click()
        time.sleep(3)

        driver.get('https://x.com')
        time.sleep(3)
        if status:
            log(f"Successfully posted tweet to community '{community_name}'", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Successfully posted tweet to community '{community_name}'", verbose, status=status, log_caller_file="post_to_community.py")
        return True
    except Exception as e:
        log(f"Failed to post tweet to community: {e}", verbose, is_error=True, status=status, log_caller_file="post_to_community.py")
        return False

def post_regular_tweet(driver, tweet_text, status=None, verbose: bool = False):
    try:
        if status:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Navigating to tweet compose page...", verbose, status=status, log_caller_file="post_to_community.py")
        driver.get('https://x.com/compose/tweet')
        time.sleep(3)

        tweet_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
        )
        tweet_input.clear()
        tweet_input.send_keys(tweet_text)
        time.sleep(2)
        
        if status:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log("Clicking post button...", verbose, status=status, log_caller_file="post_to_community.py")
        post_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
        )
        post_button.click()
        time.sleep(3)

        driver.get('https://x.com')
        time.sleep(3)
        if status:
            log(f"Successfully posted regular tweet.", verbose, status=status, log_caller_file="post_to_community.py")
        else:
            log(f"Successfully posted regular tweet.", verbose, status=status, log_caller_file="post_to_community.py")
        return True
    except Exception as e:
        log(f"Failed to post regular tweet: {e}", verbose, is_error=True, status=status, log_caller_file="post_to_community.py")
        return False
