import re
import os
import warnings

from dotenv import load_dotenv
from datetime import datetime
from rich.console import Console
from google.oauth2 import service_account
from googleapiclient.discovery import build
from typing import List, Dict, Any, Optional
from services.support.logger_util import _log as log
from services.support.api_call_tracker import APICallTracker

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

console = Console()
api_call_tracker = APICallTracker(log_file="logs/sheets_api_calls_log.json")

def get_google_sheets_service(verbose: bool = False, status=None):
    try:
        if not os.path.exists('credentials/service_account.json'):
            log("service_account.json file not found", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return None
            
        try:
            credentials = service_account.Credentials.from_service_account_file(
                'credentials/service_account.json',
                scopes=SCOPES
            )
            log("Successfully loaded credentials", verbose, status=status, log_caller_file="sheets_util.py")
            api_key_suffix = credentials.service_account_email[-4:] if credentials.service_account_email else None
        except Exception as cred_err:
            log(f"Failed to load credentials: {cred_err}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return None
    
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
            log("Successfully built sheets service", verbose, status=status, log_caller_file="sheets_util.py")
            

            can_call, reason = api_call_tracker.can_make_call("sheets", "read", api_key_suffix=api_key_suffix)
            if not can_call:
                log(f"[RATE LIMIT] Cannot test connection to sheets API: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return None

            log("[HITTING API] Testing connection to sheets API.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read", api_key_suffix=api_key_suffix), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, fields='spreadsheetId').execute()
            api_call_tracker.record_call("sheets", "read", success=True, response=response)
            log("Successfully tested connection to sheets API", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read", api_key_suffix=api_key_suffix), status=status, log_caller_file="sheets_util.py")
            
            return service
        except Exception as build_err:
            api_call_tracker.record_call("sheets", "read", success=False, response={'error': str(build_err)})
            log(f"Failed to build or test service: {build_err}", verbose, is_error=True, api_info=api_call_tracker.get_quot_info("sheets", "read", api_key_suffix=api_key_suffix), status=status, log_caller_file="sheets_util.py")
            return None
            
    except Exception as e:
        log(f"Error creating Google Sheets service: {e}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        return None

def sanitize_sheet_name(name):
    sanitized = re.sub(r'[^a-zA-Z0-9_]+', '', name)
    sanitized = sanitized[:30]
    return sanitized.lower()

def create_sheet_if_not_exists(service, sheet_name: str, headers: List[List[str]], verbose: bool = False, status=None, target_range: str = 'A1') -> Optional[str]:
    try:
        sanitized_sheet_name = sanitize_sheet_name(sheet_name)

        can_call, reason = api_call_tracker.can_make_call("sheets", "read")
        if not can_call:
            log(f"[RATE LIMIT] Cannot get spreadsheet properties to check for existing sheets: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return None

        log("[HITTING API] Getting spreadsheet properties to check for existing sheets.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read"), status=status, log_caller_file="sheets_util.py")
        spreadsheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        api_call_tracker.record_call("sheets", "read", success=True, response=spreadsheet_metadata)
        existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet_metadata['sheets']]
        
        if sanitized_sheet_name not in existing_sheets:
            requests = [{
                'addSheet': {
                    'properties': {
                        'title': sanitized_sheet_name
                    }
                }
            }]
            body = {'requests': requests}

            can_call, reason = api_call_tracker.can_make_call("sheets", "write")
            if not can_call:
                log(f"[RATE LIMIT] Cannot add new sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return None
            
            log(f"[HITTING API] Adding new sheet: {sanitized_sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
            api_call_tracker.record_call("sheets", "write", success=True, response=response)

            can_call, reason = api_call_tracker.can_make_call("sheets", "write")
            if not can_call:
                log(f"[RATE LIMIT] Cannot update headers for new sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return None

            log(f"[HITTING API] Updating headers for new sheet: {sanitized_sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{sanitized_sheet_name}!{target_range}',
                valueInputOption='RAW',
                body={'values': headers}
            ).execute()
            api_call_tracker.record_call("sheets", "write", success=True, response=response)
            log(f"Created new Google Sheet: {sanitized_sheet_name}", verbose, status=status, log_caller_file="sheets_util.py")
        else:
            log(f"Sheet '{sanitized_sheet_name}' already exists.", verbose, status=status, log_caller_file="sheets_util.py")

        return sanitized_sheet_name

    except Exception as e:
        log(f"Error creating sheet: {str(e)}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        api_call_tracker.record_call("sheets", "write", success=False, response={'error': str(e)})
        return None

def append_to_sheet(service, sheet_name: str, headers: List[str], data_rows: List[List[Any]], verbose: bool = False, status=None) -> bool:
    try:
        sanitized_sheet_name = sanitize_sheet_name(sheet_name)

        can_call, reason = api_call_tracker.can_make_call("sheets", "read")
        if not can_call:
            log(f"[RATE LIMIT] Cannot read sheet to check for headers: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return False

        log(f"[HITTING API] Reading sheet '{sanitized_sheet_name}' to check for headers.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read"), status=status, log_caller_file="sheets_util.py")
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sanitized_sheet_name}!A1:Z1'
        ).execute()
        api_call_tracker.record_call("sheets", "read", success=True, response=result)

        existing_headers = result.get('values', [[]])[0]

        if not existing_headers:
            can_call, reason = api_call_tracker.can_make_call("sheets", "write")
            if not can_call:
                log(f"[RATE LIMIT] Cannot write headers to sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return False

            log(f"[HITTING API] Writing headers to sheet '{sanitized_sheet_name}'.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{sanitized_sheet_name}!A1',
                valueInputOption='RAW',
                body={'values': [headers]}
            ).execute()
            api_call_tracker.record_call("sheets", "write", success=True, response=response)

        if data_rows:
            can_call, reason = api_call_tracker.can_make_call("sheets", "write")
            if not can_call:
                log(f"[RATE LIMIT] Cannot append data to sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return False

            log(f"[HITTING API] Appending {len(data_rows)} rows to sheet '{sanitized_sheet_name}'.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{sanitized_sheet_name}!A:Z',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': data_rows}
            ).execute()
            api_call_tracker.record_call("sheets", "write", success=True, response=response)
            log(f"Successfully appended {len(data_rows)} rows to sheet '{sanitized_sheet_name}'.", verbose, status=status, log_caller_file="sheets_util.py")
        
        return True

    except Exception as e:
        log(f"Error appending to sheet: {str(e)}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        api_call_tracker.record_call("sheets", "write", success=False, response={'error': str(e)})
        return False

def batch_update_online_action_mode_replies(service, profile_name: str, updates: List[Dict[str, Any]], verbose: bool = False, status=None) -> bool:
    try:
        sheet_name = f"{sanitize_sheet_name(profile_name)}_online_replies"
        
        can_call, reason = api_call_tracker.can_make_call("sheets", "read")
        if not can_call:
            log(f"[RATE LIMIT] Cannot get spreadsheet properties to check for existing sheets: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return False

        log("[HITTING API] Getting spreadsheet properties to check for existing sheets.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read"), status=status, log_caller_file="sheets_util.py")
        spreadsheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        api_call_tracker.record_call("sheets", "read", success=True, response=spreadsheet_metadata)
        existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet_metadata['sheets']]
        
        if sheet_name not in existing_sheets:
            log(f"Sheet {sheet_name} not found. Cannot perform batch update.", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return False

        if not updates:
            log("No updates to perform for batch update.", verbose, status=status, log_caller_file="sheets_util.py")
            return True

        body = {
            'valueInputOption': 'RAW',
            'data': updates
        }

        can_call, reason = api_call_tracker.can_make_call("sheets", "write")
        if not can_call:
            log(f"[RATE LIMIT] Cannot perform batch update: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
            return False
            
        log(f"[HITTING API] Batch updating {len(updates)} replies in sheet {sheet_name}.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
        response = service.spreadsheets().values().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=body
            ).execute()
        api_call_tracker.record_call("sheets", "write", success=True, response=response)

        log(f"Successfully performed batch update for {len(updates)} replies in sheet {sheet_name}.", verbose, status=status, log_caller_file="sheets_util.py")
        return True

    except Exception as e:
        log(f"Error performing batch update for online action mode replies: {e}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        api_call_tracker.record_call("sheets", "write", success=False, response={'error': str(e)})
        return False

def get_data_from_sheets(service, operation_type: str, profile_name: str, verbose: bool = False, status=None, **kwargs) -> Any:
    sheet_name = ""
    target_range = ""
    column_mapping = {}
    filter_logic = None
    create_if_not_exists = False
    return_with_index = False
    result = None

    if operation_type == "generated_replies":
        sheet_name = f"{sanitize_sheet_name(profile_name)}_replied_tweets"
        target_range = "A2:L"
        column_mapping = {
            0: 'tweet_date', 1: 'tweet_url', 2: 'tweet_text', 3: 'media_urls',
            4: 'reply', 5: 'posted_date', 6: 'approved', 7: 'likes',
            8: 'retweets', 9: 'replies', 10: 'views', 11: 'bookmarks'
        }
        create_if_not_exists = True

        def parse_generated_reply_item(row):
            item = {col_idx: row[col_idx] if col_idx < len(row) else '' for col_idx in range(max(column_mapping.keys()) + 1)}
            structured_item = {v: item.get(k, '') for k, v in column_mapping.items()}
            structured_item['approved'] = (structured_item['approved'] == 'Yes')
            for key in ['likes', 'retweets', 'replies', 'views', 'bookmarks']:
                structured_item[key] = int(structured_item[key]) if str(structured_item[key]).isdigit() else 0
            return structured_item
        
        parse_item_func = parse_generated_reply_item

    elif operation_type == "online_action_mode_replies":
        sheet_name = f"{sanitize_sheet_name(profile_name)}_online_replies"
        target_range = "A2:Q"
        column_mapping = {
            0: 'tweet_id', 1: 'tweet_date', 2: 'tweet_url', 3: 'tweet_text',
            4: 'media_files', 5: 'generated_reply', 6: 'status', 7: 'posted_date',
            8: 'scraped_date', 9: 'run_number', 10: 'profile_image_url', 11: 'likes',
            12: 'retweets', 13: 'replies', 14: 'views', 15: 'bookmarks', 16: 'profile'
        }

        target_date = kwargs.get('target_date')
        run_number = kwargs.get('run_number')
        def online_filter(item_with_idx):
            item = item_with_idx[0]
            match = True
            if target_date:
                match = match and item.get('scraped_date', '').startswith(target_date)
            if run_number:
                item_run_number = int(item.get('run_number')) if str(item.get('run_number')).isdigit() else None
                match = match and (item_run_number == run_number)
            return match
        filter_logic = online_filter

        def parse_online_item(row):
            item = {col_idx: row[col_idx] if col_idx < len(row) else '' for col_idx in range(max(column_mapping.keys()) + 1)}
            structured_item = {v: item.get(k, '') for k, v in column_mapping.items()}
            structured_item['run_number'] = int(structured_item['run_number']) if str(structured_item['run_number']).isdigit() else None
            for key in ['likes', 'retweets', 'replies', 'views', 'bookmarks']:
                structured_item[key] = int(structured_item[key]) if str(structured_item[key]).isdigit() else 0
            return structured_item
        parse_item_func = parse_online_item
        return_with_index = True

    elif operation_type == "linkedin_messages":
        sheet_name = f"{sanitize_sheet_name(profile_name)}_linkedin_texts"
        target_range = "A2:F"
        column_mapping = {
            0: 'timestamp', 1: 'profile_name', 2: 'profile_job_title',
            3: 'profile_url', 4: 'generated_message', 5: 'status'
        }
        create_if_not_exists = True

        def linkedin_filter(item):
            return item.get('status', '').lower() == 'approved'
        filter_logic = linkedin_filter

        def parse_linkedin_item(row):
            item = {col_idx: row[col_idx] if col_idx < len(row) else '' for col_idx in range(max(column_mapping.keys()) + 1)}
            structured_item = {v: item.get(k, '') for k, v in column_mapping.items()}
            return structured_item
        parse_item_func = parse_linkedin_item

    else:
        log(f"Unsupported operation_type for getting data from Google Sheets: {operation_type}", verbose, status, is_error=True, log_caller_file="sheets_util.py")
        return []

    if create_if_not_exists:
        headers = []
        target_range_for_create = 'A1'
        if operation_type == "generated_replies":
            headers = [['Tweet Date', 'Tweet URL', 'Tweet Text', 'Media URLs', 'Generated Reply', 'Posted Date', 'Approved', 'Likes', 'Retweets', 'Replies', 'Views', 'Bookmarks']]
            target_range_for_create = 'A1:L1'
        elif operation_type == "linkedin_messages":
            headers = [['Timestamp', 'Profile_Name', 'Profile_Job_Title', 'Profile_URL', 'Generated_Message', 'Status']]
            target_range_for_create = 'A1:F1'
        
        if headers:
            created_sheet = create_sheet_if_not_exists(service, sheet_name, headers, verbose, status, target_range=target_range_for_create)
            if not created_sheet:
                log(f"Failed to create or verify sheet {sheet_name}. Aborting data retrieval.", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return []

    log(f"Fetching replies from sheet: {sheet_name}", verbose, status=status, log_caller_file="sheets_util.py")

    can_call, reason = api_call_tracker.can_make_call("sheets", "read")
    if not can_call:
        log(f"[RATE LIMIT] Cannot get spreadsheet properties to check for existing sheets: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        return []

    log("[HITTING API] Getting spreadsheet properties to check for existing sheets.", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read"), status=status, log_caller_file="sheets_util.py")
    spreadsheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    api_call_tracker.record_call("sheets", "read", success=True, response=spreadsheet_metadata)
    existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet_metadata['sheets']]

    if sheet_name not in existing_sheets:
        log(f"Sheet {sheet_name} not found. Returning empty list.", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        return []
    
    can_call, reason = api_call_tracker.can_make_call("sheets", "read")
    if not can_call:
        log(f"[RATE LIMIT] Cannot get values from sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        return []

    log(f"[HITTING API] Getting values from sheet: {sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "read"), status=status, log_caller_file="sheets_util.py")
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!{target_range}'
        ).execute()
        api_call_tracker.record_call("sheets", "read", success=True, response=result)
    except Exception as e:
        log(f"Error getting values from sheet {sheet_name}: {e}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        api_call_tracker.record_call("sheets", "read", success=False, response={'error': str(e)})
        return []

    if result is None:
        log(f"Failed to retrieve data from sheet {sheet_name}. Returning empty list.", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        return []
    
    values = result.get('values', [])
    parsed_data_with_indices = []

    for idx, row in enumerate(values):
        structured_item = parse_item_func(row)
        parsed_data_with_indices.append((structured_item, idx + 2))

    if filter_logic:
        if operation_type == "online_action_mode_replies":
            filtered_data = [item_with_idx for item_with_idx in parsed_data_with_indices if filter_logic(item_with_idx)]
        else:
            filtered_data = [item_with_idx for item_with_idx in parsed_data_with_indices if filter_logic(item_with_idx[0])]
        return [item_with_idx[0] for item_with_idx in filtered_data] if not return_with_index else filtered_data

    return [item_with_idx[0] for item_with_idx in parsed_data_with_indices] if not return_with_index else parsed_data_with_indices 

def save_data_to_sheets(service, operation_type: str, profile_name: str, data: Any, verbose: bool = False, status=None, **kwargs) -> bool:
    try:
        if operation_type == "linkedin_message":
            sheet_name = f"{sanitize_sheet_name(profile_name)}_linkedin_texts"
            headers = [['Timestamp', 'Profile_Name', 'Profile_Job_Title', 'Profile_URL', 'Generated_Message', 'Status']]
            created_sheet = create_sheet_if_not_exists(service, sheet_name, headers, verbose, status, target_range='A1:F1')
            if not created_sheet:
                return False

            current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data_row = [
                current_timestamp,
                profile_name,
                data.get('profile_job_title', ''),
                data.get('profile_url', ''),
                data.get('generated_message', ''),
                "approved"
            ]
            
            success = append_to_sheet(service, sheet_name, headers[0], [data_row], verbose, status)
            
            if success:
                log(f"Successfully saved approved message to Google Sheet '{sheet_name}'.", verbose, status=status, log_caller_file="sheets_util.py")
            return success
        
        elif operation_type == "initial_generated_replies":
            sheet_name = f"{sanitize_sheet_name(profile_name)}_online_replies"
            headers = [['Tweet ID', 'Tweet Date', 'Tweet URL', 'Tweet Text', 'Media URLs', 'Generated Reply', 'Status', 'Posted Date', 'Scraped Date', 'Run Number', 'Profile Image URL', 'Likes', 'Retweets', 'Replies', 'Views', 'Bookmarks', 'Profile']]
            created_sheet = create_sheet_if_not_exists(service, sheet_name, headers, verbose, status, target_range='A1:Q1')
            if not created_sheet:
                log(f"[ERROR] Sheet creation/verification failed for {sheet_name}. Aborting save.", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return False

            existing_replies = get_data_from_sheets(service, operation_type="online_action_mode_replies", profile_name=profile_name, verbose=verbose, status=status)
            log(f"[DEBUG] Fetched {len(existing_replies)} existing replies from sheet: {sheet_name}", verbose, status=status, log_caller_file="sheets_util.py")
            existing_tweet_ids = {reply_item['tweet_id']: idx for idx, (reply_item, _) in enumerate(existing_replies)}

            new_rows = []
            update_operations = []

            for reply_item in data:
                tweet_id = reply_item.get('tweet_id')
                if not tweet_id:
                    log(f"Skipping reply item with no tweet_id: {reply_item}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                    continue
                
                row = [
                    tweet_id,
                    reply_item.get('tweet_date', ''),
                    reply_item.get('tweet_url', ''),
                    reply_item.get('tweet_text', ''),
                    ';'.join(reply_item.get('media_files', [])) if isinstance(reply_item.get('media_files'), list) else reply_item.get('media_files', ''),
                    reply_item.get('generated_reply', ''),
                    reply_item.get('status', 'ready_for_approval'),
                    reply_item.get('posted_date', ''),
                    reply_item.get('scraped_date', ''),
                    reply_item.get('run_number', ''),
                    reply_item.get('profile_image_url', ''),
                    reply_item.get('likes', ''),
                    reply_item.get('retweets', ''),
                    reply_item.get('replies', ''),
                    reply_item.get('views', ''),
                    reply_item.get('bookmarks', ''),
                    reply_item.get('profile', '')
                ]

                if tweet_id in existing_tweet_ids:
                    row_idx = existing_tweet_ids[tweet_id] + 2
                    update_operations.append({
                        'range': f'{sheet_name}!A{row_idx}:Q{row_idx}',
                        'values': [row]
                    })
                else:
                    new_rows.append(row)
                
                log(f"[DEBUG] New rows to append: {len(new_rows)}", verbose, status=status, log_caller_file="sheets_util.py")
                log(f"[DEBUG] Update operations to perform: {len(update_operations)}", verbose, status=status, log_caller_file="sheets_util.py")
            
            if update_operations:
                body = {
                    'valueInputOption': 'RAW',
                    'data': update_operations
                }
                can_call, reason = api_call_tracker.can_make_call("sheets", "write")
                if not can_call:
                    log(f"[RATE LIMIT] Cannot batch update replies: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                    return False

                log(f"[HITTING API] Batch updating {len(update_operations)} replies in sheet: {sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
                response = service.spreadsheets().values().batchUpdate(
                    spreadsheetId=SPREADSHEET_ID,
                    body=body
                ).execute()
                api_call_tracker.record_call("sheets", "write", success=True, response=response)

            if new_rows:
                body = {
                    'values': new_rows
                }
                can_call, reason = api_call_tracker.can_make_call("sheets", "write")
                if not can_call:
                    log(f"[RATE LIMIT] Cannot append new replies: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                    return False

                log(f"[HITTING API] Appending {len(new_rows)} new replies to sheet: {sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
                response = service.spreadsheets().values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f'{sheet_name}!A2:Q',
                    valueInputOption='RAW',
                    body=body
                ).execute()
                api_call_tracker.record_call("sheets", "write", success=True, response=response)
            
                log(f"Successfully saved/updated {len(data)} replies to sheet: {sheet_name}", verbose, status=status, log_caller_file="sheets_util.py")
                return True
        
        elif operation_type == "posted_reply":
            sheet_name = f"{sanitize_sheet_name(profile_name)}_replied_tweets"
            headers = [['Tweet Date', 'Tweet URL', 'Tweet Text', 'Media URLs', 'Generated Reply', 'Posted Date', 'Approved', 'Likes', 'Retweets', 'Replies', 'Views', 'Bookmarks']]
            created_sheet = create_sheet_if_not_exists(service, sheet_name, headers, verbose, status, target_range='A1:L1')
            if not created_sheet:
                return False 

            row = [
                data.get('tweet_date', ''),
                data.get('tweet_url', ''),
                data.get('tweet_text', ''),
                ';'.join(data.get('media_files', [])) if isinstance(data.get('media_files'), list) else data.get('media_files', ''),
                data.get('generated_reply', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Yes',
                data.get('likes', ''),
                data.get('retweets', ''),
                data.get('replies', ''),
                data.get('views', ''),
                data.get('bookmarks', '')
            ]

            body = {
                'values': [row]
            }
            can_call, reason = api_call_tracker.can_make_call("sheets", "write")
            if not can_call:
                log(f"[RATE LIMIT] Cannot append posted reply to sheet: {reason}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
                return False

            log(f"[HITTING API] Appending posted reply to sheet: {sheet_name}", verbose, api_info=api_call_tracker.get_quot_info("sheets", "write"), status=status, log_caller_file="sheets_util.py")
            response = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f'{sheet_name}!A2:L',
                valueInputOption='RAW',
                body=body
            ).execute()
            api_call_tracker.record_call("sheets", "write", success=True, response=response)
            
            log(f"Successfully saved posted reply to sheet: {sheet_name}", verbose, status=status, log_caller_file="sheets_util.py")
            return True

    except Exception as e:
        log(f"Error saving data to sheets: {e}", verbose, is_error=True, status=status, log_caller_file="sheets_util.py")
        api_call_tracker.record_call("sheets", "write", success=False, response={'error': str(e)})
        return False 