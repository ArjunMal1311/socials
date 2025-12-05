import os
import json
import glob

from rich.status import Status
from typing import Optional, List, Dict, Any
from services.support.logger_util import _log as log
from services.support.sheets_util import get_google_sheets_service, append_to_sheet
from services.support.path_config import get_product_hunt_profile_dir, ensure_dir_exists, BASE_TMP_DIR
from services.support.web_driver_handler import cleanup_chrome_locks, kill_chrome_processes_by_user_data_dir, setup_driver

def _append_data_to_google_sheet(sheets_service, all_scraped_products_detailed: List[Dict[str, Any]], verbose: bool, status: Optional[Status], sheet_name: str = "Networking"):
    if not sheets_service:
        log("Google Sheets service not available. Skipping Google Sheets integration.", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
        return

    if not all_scraped_products_detailed:
        log("No data to append to Google Sheet.", verbose, status=status, log_caller_file="ph_sheets_integration.py")
        return

    base_headers = [
        "Name", "Links (Socials)", "Status", "Link (PH)", "Link (Website)",
        "Company Information", "Response", "Output", "Last Updated",
        "Activity", "Next Action", "Improvements", "Socials"
    ]

    all_dynamic_social_keys = set()
    for product_item in all_scraped_products_detailed:
        socials_data = json.loads(product_item.get("socials", "{}"))
        
        linkedin_profiles = socials_data.get("linkedin", {}).get("profiles", [])
        for i, profile in enumerate(linkedin_profiles):
            for key in profile.keys():
                all_dynamic_social_keys.add(f"LinkedIn_Profile_{i+1}_{key}")
        
        x_profiles = socials_data.get("x", {}).get("profiles", [])
        for i, profile in enumerate(x_profiles):
            for key in profile.keys():
                all_dynamic_social_keys.add(f"X_Profile_{i+1}_{key}")
    
    updated_headers = list(base_headers)
    updated_headers.extend(sorted(list(all_dynamic_social_keys)))
    
    final_data_rows = []
    for product_item in all_scraped_products_detailed:
        flattened_product_row_data = {}

        for header in base_headers:
            if header == "Socials":
                flattened_product_row_data[header] = json.dumps(product_item.get("socials", {}))
            else:
                flattened_product_row_data[header] = product_item.get(header, "N/A")

        socials_data = product_item.get("socials", {})
        
        linkedin_profiles = socials_data.get("linkedin", {}).get("profiles", [])
        for i, profile in enumerate(linkedin_profiles):
            for key, value in profile.items():
                flattened_product_row_data[f"LinkedIn_Profile_{i+1}_{key}"] = value
        
        x_profiles = socials_data.get("x", {}).get("profiles", [])
        for i, profile in enumerate(x_profiles):
            for key, value in profile.items():
                flattened_product_row_data[f"X_Profile_{i+1}_{key}"] = value

        row = [flattened_product_row_data.get(header, "N/A") for header in updated_headers]
        final_data_rows.append(row)

    append_to_sheet(sheets_service, sheet_name, updated_headers, final_data_rows, verbose, status)
    log(f"Successfully appended {len(final_data_rows)} products to Google Sheet '{sheet_name}'.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

def load_and_process_existing_socials(profile_name: str, verbose: bool = False, status: Optional[Status] = None, profile_x: str = "Default", profile_linkedin: str = "Default"):
    log(f"Loading existing Product Hunt data to process social links for profile '{profile_name}'...", verbose, status=status, log_caller_file="ph_sheets_integration.py")
    product_hunt_data_dir = get_product_hunt_profile_dir(profile_name)
    ensure_dir_exists(product_hunt_data_dir)

    list_of_files = glob.glob(os.path.join(product_hunt_data_dir, "product_hunt_detailed_*.json"))
    if not list_of_files:
        log(f"No existing detailed Product Hunt data found for profile '{profile_name}'. Please run --scrape-producthunt first.", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
        return
    latest_file = max(list_of_files, key=os.path.getctime)
    output_file_path = latest_file

    if not os.path.exists(output_file_path):
        log(f"No existing detailed Product Hunt data found for profile '{profile_name}'. Please run --scrape-producthunt first.", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
        return

    with open(output_file_path, 'r', encoding='utf-8') as f:
        all_scraped_products_detailed = json.load(f)
    
    log(f"Loaded {len(all_scraped_products_detailed)} products from {output_file_path}.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

    linkedin_driver = None
    x_driver = None
    try:
        log(f"Setting up LinkedIn WebDriver for profile '{profile_linkedin}'...", verbose, status=status, log_caller_file="ph_sheets_integration.py")
        linkedin_user_data_dir = os.path.join(BASE_TMP_DIR, "browser-data", profile_linkedin)
        ensure_dir_exists(linkedin_user_data_dir)
        cleanup_chrome_locks(linkedin_user_data_dir, verbose=verbose, status=status)
        kill_chrome_processes_by_user_data_dir(linkedin_user_data_dir, verbose=verbose, status=status)
        linkedin_driver, _ = setup_driver(linkedin_user_data_dir, profile=profile_linkedin, headless=not verbose)
        log("LinkedIn WebDriver setup complete.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

        log(f"Setting up X WebDriver for profile '{profile_x}'...", verbose, status=status, log_caller_file="ph_sheets_integration.py")
        x_user_data_dir = os.path.join(BASE_TMP_DIR, "browser-data", profile_x)
        ensure_dir_exists(x_user_data_dir)
        cleanup_chrome_locks(x_user_data_dir, verbose=verbose, status=status)
        kill_chrome_processes_by_user_data_dir(x_user_data_dir, verbose=verbose, status=status)
        x_driver, _ = setup_driver(x_user_data_dir, profile=profile_x, headless=not verbose)
        log("X WebDriver setup complete.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

        # Use the imported process_product_socials
        from services.utils.networking.support.ph_social_processor import process_product_socials
        processed_products = []
        for product in all_scraped_products_detailed:
            processed_product = process_product_socials(linkedin_driver, x_driver, product, verbose, status, profile_linkedin=profile_linkedin, profile_x=profile_x)
            processed_products.append(processed_product)
        all_scraped_products_detailed = processed_products
        log(f"Social links processed for {len(all_scraped_products_detailed)} products.", verbose, status=status, log_caller_file="ph_sheets_integration.py")
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_scraped_products_detailed, f, indent=2, ensure_ascii=False)
        log(f"Updated {output_file_path} with processed social data.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

        sheets_service = get_google_sheets_service(verbose, status)
        _append_data_to_google_sheet(sheets_service, all_scraped_products_detailed, verbose, status)

    except Exception as e:
        log(f"An error occurred during social link processing: {e}", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
    finally:
        if linkedin_driver:
            linkedin_driver.quit()
        if x_driver:
            x_driver.quit()
        kill_chrome_processes_by_user_data_dir(linkedin_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(linkedin_user_data_dir, verbose=verbose, status=status)
        kill_chrome_processes_by_user_data_dir(x_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(x_user_data_dir, verbose=verbose, status=status)
        log(f"Social link processing completed for profile '{profile_name}'.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

def store_latest_data_to_sheets(profile_name: str, verbose: bool = False, status: Optional[Status] = None):
    log(f"Loading latest Product Hunt data for profile '{profile_name}' to store in Google Sheet...", verbose, status=status, log_caller_file="ph_sheets_integration.py")
    product_hunt_data_dir = get_product_hunt_profile_dir(profile_name)
    ensure_dir_exists(product_hunt_data_dir)

    list_of_files = glob.glob(os.path.join(product_hunt_data_dir, "product_hunt_detailed_*.json"))
    if not list_of_files:
        log(f"No existing detailed Product Hunt data found for profile '{profile_name}'. Please run --scrape-producthunt first.", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
        return
    latest_file = max(list_of_files, key=os.path.getctime)
    output_file_path = latest_file

    if not os.path.exists(output_file_path):
        log(f"No existing detailed Product Hunt data found for profile '{profile_name}'. Please run --scrape-producthunt first.", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
        return

    with open(output_file_path, 'r', encoding='utf-8') as f:
        all_scraped_products_detailed = json.load(f)
    
    log(f"Loaded {len(all_scraped_products_detailed)} products from {output_file_path}.", verbose, status=status, log_caller_file="ph_sheets_integration.py")

    try:
        sheets_service = get_google_sheets_service(verbose, status)
        _append_data_to_google_sheet(sheets_service, all_scraped_products_detailed, verbose, status)

    except Exception as e:
        log(f"An error occurred during storing data to Google Sheet: {e}", verbose, is_error=True, status=status, log_caller_file="ph_sheets_integration.py")
