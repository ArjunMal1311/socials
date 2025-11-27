import os
import sys
import httplib2

from rich.console import Console
from oauth2client.file import Storage
from oauth2client.tools import run_flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from services.support.logger_util import _log as log
from oauth2client.client import flow_from_clientsecrets
from services.support.path_config import get_youtube_schedule_videos_dir

console = Console()

CLIENT_SECRETS_FILE = "client_secret.json"
CREDENTIALS_FILE = "youtube-oauth2.json"
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

def get_authenticated_service(profile_name="Default", verbose: bool = False):
    profile_dir = get_youtube_schedule_videos_dir(profile_name)
    
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)
        log(f"Created profile directory for YouTube API: {profile_dir}", verbose)

    client_secrets_path = os.path.join(profile_dir, CLIENT_SECRETS_FILE)
    credentials_path = os.path.join(profile_dir, CREDENTIALS_FILE)

    if not os.path.exists(client_secrets_path):
        log(f"Error: 'client_secret.json' not found in {profile_dir}", verbose, is_error=True, log_caller_file="schedule_youtube_api.py")
        log("Please download your OAuth 2.0 client secrets file from the Google API Console and place it in the specified profile directory.", verbose, is_error=True, log_caller_file="schedule_youtube_api.py")
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
                log(f"Uploading... {progress}%", verbose, log_caller_file="schedule_youtube_api.py")

    if status:
        status.update(f"[white]Video uploaded successfully: https://www.youtube.com/watch?v={response['id']}[/white]")
    else:
        log(f"✅ Video uploaded successfully: https://www.youtube.com/watch?v={response['id']}", verbose, log_caller_file="schedule_youtube_api.py")
    return True
