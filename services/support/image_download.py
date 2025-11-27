import os
import requests

from rich.console import Console
from urllib.parse import urlparse
from services.support.path_config import get_downloads_dir
from services.support.logger_util import _log as log

console = Console()

def download_images(image_urls, profile_name="Default", verbose: bool = False):
    download_dir = os.path.abspath(os.path.join(get_downloads_dir(), 'images', profile_name))
    os.makedirs(download_dir, exist_ok=True)
    
    local_image_paths = []
    for url in image_urls:
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            query_params = parsed_url.query.split('&')
            format_param = next((p for p in query_params if p.startswith('format=')), None)
            if format_param:
                ext = format_param.split('=')[1]
                if not filename.endswith(f'.{ext}'):
                    filename = f"{filename.split('.')[0]}.{ext}"
            
            file_path = os.path.join(download_dir, filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            local_image_paths.append(file_path)
            log(f"Downloaded image: {filename}", verbose, log_caller_file="image_download.py")
        except Exception as e:
            log(f"Error downloading image {url}: {str(e)}", verbose, is_error=True, log_caller_file="image_download.py")
    return local_image_paths 