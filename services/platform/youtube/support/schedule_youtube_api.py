import os
import re
import sys
import httplib2

from datetime import datetime
from rich.console import Console
from oauth2client.file import Storage
from typing import Optional, Dict, Any
from oauth2client.tools import run_flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from services.support.path_config import get_youtube_schedule_videos_dir

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if status and (is_error or verbose):
        status.stop()

    log_message = message
    if is_error:
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[schedule_youtube_api.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[schedule_youtube_api.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

CLIENT_SECRETS_FILE = "client_secret.json"
CREDENTIALS_FILE = "youtube-oauth2.json"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def get_authenticated_service(profile_name="Default", verbose: bool = False):
    profile_dir = get_youtube_schedule_videos_dir(profile_name)
    
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        _log(f"Created profile directory for YouTube API: {profile_dir}", verbose)

    client_secrets_path = os.path.join(profile_dir, CLIENT_SECRETS_FILE)
    credentials_path = os.path.join(profile_dir, CREDENTIALS_FILE)

    if not os.path.exists(client_secrets_path):
        _log(f"Error: 'client_secret.json' not found in {profile_dir}", verbose, is_error=True)
        _log("Please download your OAuth 2.0 client secrets file from the Google API Console and place it in the specified profile directory.", verbose, is_error=True)
        sys.exit(1)

    flow = flow_from_clientsecrets(client_secrets_path, scope=YOUTUBE_UPLOAD_SCOPE)
    storage = Storage(credentials_path)
    credentials = storage.get()

    if credentials is None or credentials.invalid:
        from oauth2client import tools
        flags = tools.argparser.parse_args(args=[])
        credentials = run_flow(flow, storage, flags=flags)

    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def initialize_upload(youtube, options, status=None, verbose: bool = False):
    body = {
        "snippet": {
            "title": options.title,
            "description": options.description,
            "tags": options.tags.split(",") if options.tags else [],
        },
        "status": {
            "privacyStatus": "private" if options.publishAt else options.privacyStatus,
        }
    }

    if options.publishAt:
        body["status"]["publishAt"] = options.publishAt

    media_body = MediaFileUpload(options.file, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media_body
    )

    response = None
    while response is None:
        status_obj, response = request.next_chunk()
        if status_obj:
            progress = int(status_obj.progress() * 100)
            if status:
                status.update(f"[white]Uploading... {progress}%[/white]")
            else:
                _log(f"Uploading... {progress}%", verbose)

    if status:
        status.update(f"[white]Video uploaded successfully: https://www.youtube.com/watch?v={response['id']}[/white]")
    else:
        _log(f"✅ Video uploaded successfully: https://www.youtube.com/watch?v={response['id']}", verbose)
    return True
