from bs4 import BeautifulSoup
from datetime import datetime
from rich.console import Console
from services.support.logger_util import _log as log

console = Console()

def process_container(container, verbose: bool = False):
    try:
        soup = BeautifulSoup(container['html'], 'html.parser')
    
        replying_to_divs = soup.find_all('div', {'dir': 'ltr'})
        for div in replying_to_divs:
            if div.get_text().strip().startswith('Replying to'):
                log(f"Skipping reply tweet (contains 'Replying to')", verbose, is_error=False, log_caller_file="process_container.py")
                return None
        
        tweet_text_elem = soup.select_one('[data-testid="tweetText"]')
        tweet_text = tweet_text_elem.text if tweet_text_elem else ""
        
        time_el = soup.find('time')
        tweet_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if time_el and time_el.get('datetime'):
            tweet_date = datetime.fromisoformat(time_el['datetime'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        
        media_urls = []
        if 'data-testid="videoComponent"' in container['html']:
            media_urls = ['video']
        else:
            images = soup.select('img[src*="media"]')
            if images:
                media_urls = [img['src'] for img in images]
        
        metrics = {'likes': 0, 'retweets': 0, 'replies': 0, 'views': 0, 'bookmarks': 0}
        groups = soup.find_all(attrs={'role': 'group'})
        for group in groups:
            try:
                aria_label = group.get('aria-label', '').lower()
                if not aria_label:
                    continue
                    
                parts = aria_label.split(',')
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                        
                    numeric_part = ''.join(filter(str.isdigit, part))
                    if not numeric_part:
                        continue
                        
                    value = float(numeric_part)
                    
                    if 'k' in part:
                        value *= 1000
                    elif 'm' in part:
                        value *= 1000000
                    elif 'b' in part:
                        value *= 1000000000
                        
                    if 'repl' in part:
                        metrics['replies'] = int(value)
                    elif 'repost' in part or 'retweet' in part:
                        metrics['retweets'] = int(value)
                    elif 'like' in part:
                        metrics['likes'] = int(value)
                    elif 'view' in part:
                        metrics['views'] = int(value)
                    elif 'bookmark' in part:
                        metrics['bookmarks'] = int(value)
            except Exception as e:
                log(f"Error processing metrics: {str(e)}", verbose, is_error=True, log_caller_file="process_container.py")
                continue
        
        tweet_data = {
            'text': tweet_text,
            'tweet_text': tweet_text,
            'date': tweet_date,
            'likes': metrics['likes'] / 1000,
            'retweets': metrics['retweets'],
            'replies': metrics['replies'],
            'views': metrics['views'],
            'bookmarks': metrics['bookmarks'],
            'media_urls': media_urls,
            'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'tweet_date': tweet_date,
            'tweet_url': container['url'],
            'tweet_id': container['tweet_id'],
            'profile_image_url': container.get('profile_image_url', '')
        }
        
        return tweet_data
        
    except Exception as e:
        log(f"Error processing container: {str(e)}", verbose, is_error=True, log_caller_file="process_container.py")
        return None
