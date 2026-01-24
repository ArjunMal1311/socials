import os
import json
import glob

from typing import List

from services.support.logger_util import _log as log

def extract_linkedin_urls_from_data(profile_name: str, verbose: bool = False) -> List[str]:
    linkedin_urls = []

    ph_data_dir = f"tmp/product-hunt/{profile_name}"
    if os.path.exists(ph_data_dir):
        ph_files = glob.glob(os.path.join(ph_data_dir, "product_hunt_*.json"))
        if ph_files:
            log(f"Found {len(ph_files)} Product Hunt data files", verbose, log_caller_file="data_extractor.py")
            for file_path in ph_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        companies = json.load(f)

                    for company in companies:
                        founders = company.get("founders", [])
                        for founder in founders:
                            links = founder.get("links", [])
                            for link_url in links:
                                if isinstance(link_url, str) and "linkedin.com/in/" in link_url:
                                    linkedin_urls.append(link_url)

                except Exception as e:
                    log(f"Error reading PH file {file_path}: {e}", verbose, is_error=True, log_caller_file="data_extractor.py")

    yc_data_dir = f"tmp/ycombinator/{profile_name}"
    if os.path.exists(yc_data_dir):
        yc_files = glob.glob(os.path.join(yc_data_dir, "ycombinator_*.json"))
        if yc_files:
            log(f"Found {len(yc_files)} Y Combinator data files", verbose, log_caller_file="data_extractor.py")
            for file_path in yc_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        companies = json.load(f)

                    for company in companies:
                        founders = company.get("founders", [])
                        for founder in founders:
                            links = founder.get("links", [])
                            for link_url in links:
                                if isinstance(link_url, str) and "linkedin.com/in/" in link_url:
                                    linkedin_urls.append(link_url)

                except Exception as e:
                    log(f"Error reading YC file {file_path}: {e}", verbose, is_error=True, log_caller_file="data_extractor.py")

    if not linkedin_urls:
        log("No LinkedIn URLs found in Product Hunt or Y Combinator data", verbose, is_error=True, log_caller_file="data_extractor.py")
        return []

    unique_urls = []
    seen = set()
    for url in linkedin_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    log(f"Extracted {len(unique_urls)} unique LinkedIn URLs from all data sources", verbose, log_caller_file="data_extractor.py")
    return unique_urls

def extract_usernames_from_linkedin_urls(urls: List[str]) -> List[str]:
    usernames = []

    for url in urls:
        try:
            if "linkedin.com/in/" in url:
                username_part = url.split("linkedin.com/in/")[1]
                username = username_part.split('/')[0].split('?')[0]
                if username and username not in usernames:
                    usernames.append(username)
        except Exception as e:
            log(f"Error extracting username from {url}: {e}", False, is_error=True, log_caller_file="data_extractor.py")

    return usernames
