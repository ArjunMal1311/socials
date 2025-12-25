import os
import psycopg2
from psycopg2 import sql
import json
import re
from rich.console import Console
from services.support.logger_util import _log as log
from services.support.api_call_tracker import APICallTracker
from typing import List, Dict, Any, Optional
from datetime import datetime

console = Console()
api_call_tracker = APICallTracker()

def sanitize_table_name(name):
    sanitized = re.sub(r'[^a-zA-Z0-9_]+', '', name)
    sanitized = sanitized[:63]
    return sanitized.lower()

POSTGRES_SCHEMAS = {
    "replied_tweets": {
        "tweet_id": "VARCHAR(255) PRIMARY KEY",
        "tweet_date": "VARCHAR(255)",
        "tweet_url": "TEXT",
        "tweet_text": "TEXT",
        "media_urls": "TEXT", # Storing as JSON string
        "generated_reply": "TEXT",
        "posted_date": "VARCHAR(255)",
        "approved": "BOOLEAN",
        "likes": "INTEGER",
        "retweets": "INTEGER",
        "replies": "INTEGER",
        "views": "INTEGER",
        "bookmarks": "INTEGER"
    },
    "online_replies": {
        "tweet_id": "VARCHAR(255) PRIMARY KEY",
        "tweet_date": "VARCHAR(255)",
        "tweet_url": "TEXT",
        "tweet_text": "TEXT",
        "media_files": "TEXT", # Storing as JSON string
        "generated_reply": "TEXT",
        "status": "VARCHAR(255)",
        "posted_date": "VARCHAR(255)",
        "scraped_date": "VARCHAR(255)",
        "run_number": "INTEGER",
        "profile_image_url": "TEXT",
        "likes": "INTEGER",
        "retweets": "INTEGER",
        "replies": "INTEGER",
        "views": "INTEGER",
        "bookmarks": "INTEGER",
        "profile": "VARCHAR(255)"
    },
    "linkedin_messages": {
        "timestamp": "VARCHAR(255) PRIMARY KEY", # Not a primary key, new entries append
        "profile_name": "VARCHAR(255)",
        "profile_job_title": "TEXT",
        "profile_url": "TEXT",
        "generated_message": "TEXT",
        "status": "VARCHAR(255)"
    },
    "posted_reply": {
        "tweet_id": "VARCHAR(255) PRIMARY KEY", # Added tweet_id for consistent structure, not primary key for append-only
        "tweet_date": "VARCHAR(255)",
        "tweet_url": "TEXT",
        "tweet_text": "TEXT",
        "media_files": "TEXT", # Storing as JSON string
        "generated_reply": "TEXT",
        "posted_date": "VARCHAR(255)",
        "approved": "BOOLEAN",
        "likes": "INTEGER",
        "retweets": "INTEGER",
        "replies": "INTEGER",
        "views": "INTEGER",
        "bookmarks": "INTEGER"
    },
    "gemini_generations": {
        "generation_id": "VARCHAR(255) PRIMARY KEY", # Unique ID for each generation
        "timestamp": "VARCHAR(255)",
        "profile_name": "VARCHAR(255)",
        "model_name": "VARCHAR(255)",
        "prompt_text": "TEXT",
        "media_path": "TEXT",
        "generated_content": "TEXT",
        "token_count": "INTEGER",
        "api_key_suffix": "VARCHAR(10)",
        "success": "BOOLEAN"
    }
}

def get_postgres_connection(verbose: bool, status: Console) -> psycopg2.extensions.connection | None:
    conn = None
    try:
        db_url = os.getenv("POSTGRES_DB")
        if not db_url:
            log("[ERROR] POSTGRES_DB environment variable not set.", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
            return None

        log("[HITTING DATABASE] Attempting to connect to PostgreSQL database.", verbose, status=status, log_caller_file="postgres_util.py")
        conn = psycopg2.connect(db_url)
        log("Successfully connected to PostgreSQL database.", verbose, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "connect", success=True, response={"message": "Connected"})
        return conn
    except Exception as e:
        log(f"[ERROR] Failed to connect to PostgreSQL database: {e}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "connect", success=False, response={"error": str(e)})
        return None

def create_table_if_not_exists(
    conn: psycopg2.extensions.connection,
    table_name: str,
    columns: Dict[str, str],
    verbose: bool,
    status: Console
) -> bool:
    try:
        cursor = conn.cursor()
        column_definitions = []
        for col_name, col_type in columns.items():
            column_definitions.append(sql.SQL("{} {}").format(sql.Identifier(col_name), sql.SQL(col_type)))
        
        create_table_query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {} ({})"
        ).format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(column_definitions)
        )
        
        log(f"[HITTING DATABASE] Creating table if not exists: {table_name}", verbose, status=status, log_caller_file="postgres_util.py")
        cursor.execute(create_table_query)
        conn.commit()
        log(f"Table '{table_name}' checked/created successfully.", verbose, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "create_table", success=True, response={"table_name": table_name})
        return True
    except Exception as e:
        log(f"[ERROR] Failed to create or verify table '{table_name}': {e}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "create_table", success=False, response={"error": str(e)})
        return False

def get_data_from_postgres(
    conn: psycopg2.extensions.connection,
    operation_type: str,
    profile_name: str,
    verbose: bool,
    status: Console,
    **kwargs
) -> List[Dict[str, Any]]:
    if not conn:
        log("[ERROR] No database connection available.", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        return []

    actual_operation_type = operation_type
    if operation_type == "initial_generated_replies":
        actual_operation_type = "online_replies"
    elif operation_type == "online_action_mode_replies":
        actual_operation_type = "online_replies"
    elif operation_type == "posted_reply":
        actual_operation_type = "replied_tweets"

    table_prefix = f"{sanitize_table_name(profile_name)}_{sanitize_table_name(actual_operation_type)}"
    table_name = f"{table_prefix}"
    
    columns_schema = POSTGRES_SCHEMAS.get(actual_operation_type)
    if not columns_schema:
        log(f"[ERROR] Unsupported operation_type for getting data from PostgreSQL: {operation_type}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        return []

    if not create_table_if_not_exists(conn, table_name, columns_schema, verbose, status):
        return []

    # Initialize parsing and filtering functions
    filter_logic = None
    return_with_index = False

    # Define parsing and filtering logic based on operation_type, similar to sheets_util.py
    if operation_type == "online_replies" or operation_type == "online_action_mode_replies":
        target_date = kwargs.get('target_date')
        run_number = kwargs.get('run_number')

        def online_filter(item_with_idx):
            item = item_with_idx[0]
            match = True
            if target_date:
                scraped_date = item.get('scraped_date') or ''
                match = match and str(scraped_date).startswith(target_date)
            if run_number:
                # Convert to int for comparison if it's a number, otherwise None
                item_run_number = int(item.get('run_number')) if isinstance(item.get('run_number'), (int, float)) else None
                match = match and (item_run_number == run_number)
            match = match and item.get('status', '').lower() == 'approved'
        filter_logic = online_filter
        return_with_index = True # This is crucial for action.py's `post_approved_action_mode_replies_online`

    elif operation_type == "linkedin_messages":
        def linkedin_filter(item):
            return item.get('status', '').lower() == 'approved'
        filter_logic = linkedin_filter
        
    try:
        cursor = conn.cursor()
        select_query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))
        
        log(f"[HITTING DATABASE] Fetching data for operation type '{operation_type}' from table '{table_name}'.", verbose, status=status, log_caller_file="postgres_util.py")
        cursor.execute(select_query)
        
        col_names = [desc[0] for desc in cursor.description]
        
        rows = cursor.fetchall()
        
        raw_data = []
        for row in rows:
            item = dict(zip(col_names, row))
            # Convert JSON string back to list for media_files/media_urls
            if 'media_files' in item and item['media_files'] and isinstance(item['media_files'], str): # For online_replies, replied_tweets
                try:
                    item['media_files'] = json.loads(item['media_files'])
                except json.JSONDecodeError:
                    log(f"[WARNING] Could not decode media_files JSON for item {item.get('tweet_id')}: {item['media_files']}", verbose, is_warning=True, status=status, log_caller_file="postgres_util.py")
                    item['media_files'] = []
            if 'media_urls' in item and item['media_urls'] and isinstance(item['media_urls'], str): # For replied_tweets
                try:
                    item['media_urls'] = json.loads(item['media_urls'])
                except json.JSONDecodeError:
                    log(f"[WARNING] Could not decode media_urls JSON for item {item.get('tweet_id')}: {item['media_urls']}", verbose, is_warning=True, status=status, log_caller_file="postgres_util.py")
                    item['media_urls'] = []
            raw_data.append(item)

        parsed_data_with_indices = []
        for idx, item in enumerate(raw_data):
            structured_item = item 

            # Type conversions mirroring sheets_util.py
            if operation_type == "replied_tweets" or operation_type == "posted_reply":
                structured_item['approved'] = (structured_item.get('approved') == True) # Boolean from DB
                for key in ['likes', 'retweets', 'replies', 'views', 'bookmarks']:
                    structured_item[key] = int(structured_item.get(key)) if isinstance(structured_item.get(key), (int, float)) else 0
            elif operation_type == "online_replies" or operation_type == "online_action_mode_replies":
                structured_item['run_number'] = int(structured_item.get('run_number')) if isinstance(structured_item.get('run_number'), (int, float)) else None
                for key in ['likes', 'retweets', 'replies', 'views', 'bookmarks']:
                    structured_item[key] = int(structured_item.get(key)) if isinstance(structured_item.get(key), (int, float)) else 0

            parsed_data_with_indices.append((structured_item, idx + 2)) # +2 to simulate Google Sheets row index

        if filter_logic:
            # The filter_logic expects item_with_idx, which is (item, index)
            filtered_data = [item_with_idx for item_with_idx in parsed_data_with_indices if filter_logic(item_with_idx)]
            return [item_with_idx[0] for item_with_idx in filtered_data] if not return_with_index else filtered_data
        
        log(f"Fetched {len(raw_data)} rows from '{table_name}'.", verbose, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "read", success=True, response={"rows_fetched": len(raw_data)})
        
        return [item_with_idx[0] for item_with_idx in parsed_data_with_indices] if not return_with_index else parsed_data_with_indices
    except Exception as e:
        log(f"[ERROR] Error getting data for operation type '{operation_type}' from PostgreSQL: {e}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "read", success=False, response={"error": str(e)})
        return []

def save_data_to_postgres(
    conn: psycopg2.extensions.connection,
    operation_type: str,
    profile_name: str,
    data: List[Dict[str, Any]],
    verbose: bool,
    status: Console,
    **kwargs
) -> bool:
    if not conn:
        log("[ERROR] No database connection available.", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        return False
    if not data:
        log("[INFO] No data to save to PostgreSQL.", verbose, status=status, log_caller_file="postgres_util.py")
        return True

    actual_operation_type = operation_type
    if operation_type == "initial_generated_replies":
        actual_operation_type = "online_replies"
    elif operation_type == "online_action_mode_replies":
        actual_operation_type = "online_replies"
    elif operation_type == "posted_reply":
        actual_operation_type = "replied_tweets"

    table_prefix = f"{sanitize_table_name(profile_name)}_{sanitize_table_name(actual_operation_type)}"
    table_name = f"{table_prefix}"
    
    columns_schema = POSTGRES_SCHEMAS.get(actual_operation_type)
    if not columns_schema:
        log(f"[ERROR] Unsupported operation_type for saving data to PostgreSQL: {operation_type}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        return False

    if not create_table_if_not_exists(conn, table_name, columns_schema, verbose, status):
        return False

    try:
        cursor = conn.cursor()
        
        columns_to_insert = list(columns_schema.keys())
        
        insert_statements = []
        for item in data:
            values = []
            update_set_clauses = []
            pk_column = None

            for col in columns_to_insert:
                val = item.get(col)
                
                # Handle specific data transformations for PostgreSQL
                if col == "media_files" and isinstance(val, list): # For online_replies, replied_tweets
                    values.append(json.dumps(val))
                elif col == "media_urls" and isinstance(val, list): # For replied_tweets
                    values.append(json.dumps(val))
                elif col == "approved" and isinstance(val, bool): # For boolean type
                    values.append(val)
                elif col == "timestamp" and operation_type == "linkedin_messages":
                    values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                elif col == "posted_date" and operation_type == "posted_reply":
                    values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif col == "status" and operation_type == "initial_generated_replies": # Default for initial generation
                     values.append(item.get('status', 'ready_for_approval'))
                elif col == "status" and operation_type == "posted_reply": # Default for posted reply
                    values.append("Yes")
                elif col == "profile" and operation_type == "initial_generated_replies":
                    values.append(item.get('profile', profile_name)) # Use item's profile or default
                elif col == "run_number" and operation_type == "initial_generated_replies":
                    values.append(item.get('run_number', kwargs.get('run_number', 1))) # Use item's run_number or default
                else:
                    values.append(val)
                
                # Build update clauses for ON CONFLICT (exclude primary key and specific fields)
                if "PRIMARY KEY" not in columns_schema[col] and col not in ["tweet_id", "timestamp"]:
                    update_set_clauses.append(sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col)))
            
            # Determine the primary key column for ON CONFLICT clause
            if operation_type == "online_replies" or operation_type == "online_action_mode_replies":
                pk_column = "tweet_id"
            elif operation_type == "replied_tweets" or operation_type == "posted_reply":
                pk_column = "tweet_id"
            elif operation_type == "linkedin_messages":
                pk_column = "timestamp" # If we decide to use timestamp + profile_url as a composite primary key later.
                                          # For now, it's append-only, so no ON CONFLICT based on a single timestamp
                pk_column = None

            if pk_column and operation_type in ["online_replies", "online_action_mode_replies", "replied_tweets", "posted_reply"]:
                insert_query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}"
                ).format(
                    sql.Identifier(table_name),
                    sql.SQL(', ').join(map(sql.Identifier, columns_to_insert)),
                    sql.SQL(', ').join(sql.Placeholder() for _ in columns_to_insert),
                    sql.Identifier(pk_column),
                    sql.SQL(', ').join(update_set_clauses)
                )
            else: # Simple INSERT for other operation types (append-like behavior)
                insert_query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({})"
                ).format(
                    sql.Identifier(table_name),
                    sql.SQL(', ').join(map(sql.Identifier, columns_to_insert)),
                    sql.SQL(', ').join(sql.Placeholder() for _ in columns_to_insert)
                )
            insert_statements.append((insert_query, values))

        log(f"[HITTING DATABASE] Saving {len(data)} items for operation type '{operation_type}' to table '{table_name}'.", verbose, status=status, log_caller_file="postgres_util.py")
        for query, values in insert_statements:
            cursor.execute(query, values)
        
        conn.commit()
        log(f"Successfully saved {len(data)} items to '{table_name}'.", verbose, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "write", success=True, response={"items_saved": len(data)})
        return True
    except Exception as e:
        conn.rollback()
        log(f"[ERROR] Error saving data for operation type '{operation_type}' to PostgreSQL: {e}", verbose, is_error=True, status=status, log_caller_file="postgres_util.py")
        api_call_tracker.record_call("postgres", "write", success=False, response={"error": str(e)})
        return False
