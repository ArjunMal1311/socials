import os
import psycopg2

from psycopg2 import sql
from rich.console import Console
from typing import List, Dict, Any
from services.support.logger_util import _log as log

console = Console()

def get_postgres_connection(verbose: bool = False) -> psycopg2.extensions.connection | None:
    try:
        db_url = os.getenv("POSTGRES_DB")
        if not db_url:
            log("[ERROR] POSTGRES_DB environment variable not set.", verbose, is_error=True, log_caller_file="postgres_util.py")
            return None

        log("[HITTING DATABASE] Connecting to PostgreSQL database.", verbose, log_caller_file="postgres_util.py")
        conn = psycopg2.connect(db_url)
        log("Successfully connected to PostgreSQL database.", verbose, log_caller_file="postgres_util.py")
        return conn
    except Exception as e:
        log(f"[ERROR] Failed to connect to PostgreSQL database: {e}", verbose, is_error=True, log_caller_file="postgres_util.py")
        return None

def create_table_if_not_exists(conn: psycopg2.extensions.connection, table_name: str, schema: Dict[str, str], verbose: bool = False) -> bool:
    try:
        cursor = conn.cursor()
        columns = [sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(col_type))
                  for col, col_type in schema.items()]

        create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(columns)
        )

        cursor.execute(create_query)
        conn.commit()
        log(f"Table '{table_name}' created/verified successfully.", verbose, log_caller_file="postgres_util.py")
        return True
    except Exception as e:
        log(f"[ERROR] Failed to create table '{table_name}': {e}", verbose, is_error=True, log_caller_file="postgres_util.py")
        return False

def select_data(conn: psycopg2.extensions.connection, table_name: str, where_clause: str = "", params: tuple = (), verbose: bool = False) -> List[Dict[str, Any]]:
    try:
        cursor = conn.cursor()

        if where_clause:
            query = sql.SQL("SELECT * FROM {} WHERE {}").format(
                sql.Identifier(table_name),
                sql.SQL(where_clause)
            )
        else:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        results = [dict(zip(columns, row)) for row in rows]
        log(f"Selected {len(results)} rows from '{table_name}'.", verbose, log_caller_file="postgres_util.py")
        return results
    except Exception as e:
        log(f"[ERROR] Failed to select from '{table_name}': {e}", verbose, is_error=True, log_caller_file="postgres_util.py")
        return []

def insert_data(conn: psycopg2.extensions.connection, table_name: str, data: Dict[str, Any], verbose: bool = False, conflict_column: str = "tweet_id") -> bool:
    try:
        cursor = conn.cursor()
        columns = list(data.keys())
        values = list(data.values())

        insert_query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT ({}) DO NOTHING").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() for _ in columns),
            sql.Identifier(conflict_column)
        )

        cursor.execute(insert_query, values)
        conn.commit()

        if cursor.rowcount > 0:
            log(f"Inserted record into '{table_name}'.", verbose, log_caller_file="postgres_util.py")
        else:
            log(f"Skipped duplicate record for '{table_name}' (tweet_id already exists).", verbose, log_caller_file="postgres_util.py")

        return True
    except Exception as e:
        log(f"[ERROR] Failed to insert into '{table_name}': {e}", verbose, is_error=True, log_caller_file="postgres_util.py")
        return False

def update_data(conn: psycopg2.extensions.connection, table_name: str, updates: Dict[str, Any], where_clause: str, params: tuple = (), verbose: bool = False) -> bool:
    try:
        cursor = conn.cursor()
        set_clause = sql.SQL(', ').join(
            sql.SQL("{} = {}").format(sql.Identifier(col), sql.Placeholder())
            for col in updates.keys()
        )

        update_query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
            sql.Identifier(table_name),
            set_clause,
            sql.SQL(where_clause)
        )

        cursor.execute(update_query, list(updates.values()) + list(params))
        conn.commit()
        log(f"Updated records in '{table_name}'.", verbose, log_caller_file="postgres_util.py")
        return True
    except Exception as e:
        log(f"[ERROR] Failed to update '{table_name}': {e}", verbose, is_error=True, log_caller_file="postgres_util.py")
        return False
