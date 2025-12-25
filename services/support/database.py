from typing import Any, Dict, List, Optional

from services.support.sheets_util import (
    get_google_sheets_service,
    get_data_from_sheets,
    save_data_to_sheets,
)
from services.support.postgres_util import (
    get_postgres_connection,
    get_data_from_postgres,
    save_data_to_postgres,
)
from services.support.logger_util import _log as log

def save_data_to_service(
    data: Any,
    service_preference: str = "google_sheets",
    operation_type: str = "default",
    profile_name: Optional[str] = None,
    run_number: Optional[int] = None,
    updates_to_sheet: Optional[List[Dict[str, Any]]] = None,
    verbose: bool = False,
    status: Any = None,
    **kwargs,
) -> None:
    if service_preference == "google_sheets":
        service = get_google_sheets_service(verbose=verbose, status=status)
        if not service:
            log("Google Sheets service not available for saving.", verbose, status, is_error=True, log_caller_file="database.py")
            return
        
        save_data_to_sheets(service, operation_type, profile_name, data, verbose, status, updates_to_sheet=updates_to_sheet, **kwargs)
    elif service_preference == "postgres":
        conn = get_postgres_connection(verbose=verbose, status=status)
        if not conn:
            log("PostgreSQL connection not available for saving.", verbose, status, is_error=True, log_caller_file="database.py")
            return
        save_data_to_postgres(conn, operation_type, profile_name, data, verbose, status, **kwargs)
        conn.close()
    else:
        log(f"Unsupported service preference for saving: {service_preference}", verbose, status, is_error=True, log_caller_file="database.py")

def get_data_from_service(
    service_preference: str = "google_sheets",
    operation_type: str = "default",
    profile_name: Optional[str] = None,
    target_date: Optional[str] = None,
    run_number: Optional[int] = None,
    verbose: bool = False,
    status: Any = None,
    **kwargs,
) -> Any:
    if service_preference == "google_sheets":
        service = get_google_sheets_service(verbose=verbose, status=status)
        if not service:
            log("Google Sheets service not available for getting data.", verbose, status, is_error=True, log_caller_file="database.py")
            return []

        return get_data_from_sheets(
            service=service,
            operation_type=operation_type,
            profile_name=profile_name,
            verbose=verbose,
            status=status,
            target_date=target_date,
            run_number=run_number,
            **kwargs
        )
    elif service_preference == "postgres":
        conn = get_postgres_connection(verbose=verbose, status=status)
        if not conn:
            log("PostgreSQL connection not available for getting data.", verbose, status, is_error=True, log_caller_file="database.py")
            return []
        data = get_data_from_postgres(
            conn=conn,
            operation_type=operation_type,
            profile_name=profile_name,
            verbose=verbose,
            status=status,
            target_date=target_date,
            run_number=run_number,
            **kwargs
        )
        conn.close()
        return data
    else:
        log(f"Unsupported service preference for getting data: {service_preference}", verbose, status, is_error=True, log_caller_file="database.py")
        return []
