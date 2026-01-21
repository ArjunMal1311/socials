import os
import json
import time
import uuid
import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict, Any

from rich.status import Status
from rich.console import Console

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import cleanup_chrome_locks, kill_chrome_processes_by_user_data_dir
from services.support.path_config import get_yc_scrape_output_file_path, get_browser_data_dir, ensure_dir_exists

console = Console()

def _format_yc_data(company_data: Dict[str, Any]) -> Dict[str, Any]:
    scraped_at = datetime.now().isoformat()

    founders = []
    for founder in company_data.get("founders", []):
        founder_obj = {
            "name": founder.get("name", ""),
            "img": founder.get("avatar_url", ""),
            "links": []
        }

        social_links = founder.get("social_links", {})
        if social_links.get("x"):
            founder_obj["links"].append(social_links["x"])
        if social_links.get("linkedin"):
            founder_obj["links"].append(social_links["linkedin"])

        if founder_obj["name"]:  # Only add if we have a name
            founders.append(founder_obj)

    return {
        "id": str(uuid.uuid4()),
        "source": "ycombinator",
        "scraped_at": scraped_at,
        "core": {
            "name": company_data.get("company_name", "N/A"),
            "description": company_data.get("description", "N/A"),
            "website": company_data.get("website", "N/A"),
            "source_url": company_data.get("company_url", "N/A"),
            "logo": company_data.get("logo_url", "")
        },
        "founders": founders,
        "data": {
            "location": company_data.get("location", "N/A"),
            "batch": company_data.get("batch", "N/A"),
            "industries": company_data.get("industries", [])
        }
    }

def scrape_yc_companies(profile_name: str, verbose: bool = False, status: Optional[Status] = None, limit: Optional[int] = None, headless: bool = True) -> List[Dict[str, Any]]:
    log(f"Starting Y Combinator companies scraping for profile '{profile_name}'...", verbose, status=status, log_caller_file="scraper_utils.py")

    target_url = "https://www.ycombinator.com/companies"

    browser_user_data_dir = get_browser_data_dir("Default")
    ensure_dir_exists(browser_user_data_dir)

    driver = None
    all_formatted_companies = []

    try:
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)

        log("Initializing undetected_chromedriver for YC scraping...", verbose, status=status, log_caller_file="scraper_utils.py")
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={browser_user_data_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if headless:
            options.add_argument("--headless")

        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium-browser", version_main=142)

        log("Navigating to Y Combinator companies page...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get(target_url)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/companies/']"))
        )

        try:
            log("Sorting companies by launch date...", verbose, status=status, log_caller_file="scraper_utils.py")
            sort_dropdown = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "select"))
            )

            select = Select(sort_dropdown)
            select.select_by_value("YCCompany_By_Launch_Date_production")

            time.sleep(30)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/companies/']"))
            )
            log("Successfully sorted by launch date", verbose, status=status, log_caller_file="scraper_utils.py")

        except Exception as e:
            log(f"Could not sort by launch date, continuing with default sorting: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")

        # scroll attempts is 5 based on this number of companies will be scraped (to be fixed next time)
        scroll_attempts = 5
        for i in range(scroll_attempts):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            log(f"Scrolled to bottom (attempt {i+1}/{scroll_attempts})", verbose, status=status, log_caller_file="scraper_utils.py")
            time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        company_links = soup.find_all('a', href=lambda x: x and x.startswith('/companies/'))

        log(f"Found {len(company_links)} company links on the page after scrolling.", verbose, status=status, log_caller_file="scraper_utils.py")

        companies_to_process = company_links[:limit] if limit is not None else company_links

        for i, company_link in enumerate(companies_to_process):
            company_url = f"https://www.ycombinator.com{company_link['href']}"
            company_name = company_link.get('href', '').replace('/companies/', '')

            log(f"Processing company {i+1}/{len(companies_to_process)}: {company_name}", verbose, status=status, log_caller_file="scraper_utils.py")

            if i > 0 and i % 10 == 0:
                try:
                    log("Refreshing browser driver to maintain stability...", verbose, status=status, log_caller_file="scraper_utils.py")
                    driver.refresh()
                    time.sleep(3)
                except Exception as refresh_error:
                    log(f"Driver refresh failed: {refresh_error}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")

            try:
                basic_data = extract_company_from_main_page(company_link, company_name, company_url, verbose, status)

                if basic_data:
                    detailed_data = scrape_company_details(driver, company_url, company_name, verbose, status)

                    if detailed_data:
                        basic_data.update(detailed_data)

                    formatted_data = _format_yc_data(basic_data)
                    all_formatted_companies.append(formatted_data)

                    log(f"Successfully scraped {company_name} with {len(formatted_data['founders'])} founders", verbose, status=status, log_caller_file="scraper_utils.py")

                delay = 2 + (time.time() % 3)
                time.sleep(delay)

            except Exception as e:
                log(f"Error processing company {company_name}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                continue

        today = datetime.now()
        output_file_path = get_yc_scrape_output_file_path(profile_name, today.strftime("%Y%m%d"))
        ensure_dir_exists(os.path.dirname(output_file_path))
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_formatted_companies, f, indent=2, ensure_ascii=False)

        log(f"Scraped and saved {len(all_formatted_companies)} companies to {output_file_path}", verbose, status=status, log_caller_file="scraper_utils.py")
        return all_formatted_companies

    except Exception as e:
        log(f"An error occurred during YC scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []
    finally:
        if driver:
            driver.quit()
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)
        log(f"Y Combinator scraping completed for profile '{profile_name}'.", verbose, status=status, log_caller_file="scraper_utils.py")

def extract_company_from_main_page(company_link_element, company_name: str, company_url: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[Dict[str, Any]]:
    try:
        company_data = {
            "company_name": company_name,
            "company_url": company_url,
            "scraped_date": datetime.now().isoformat()
        }

        company_card = company_link_element.find_parent('a') or company_link_element

        name_elem = company_card.find(class_=lambda x: x and '_coName_' in x)
        if name_elem:
            company_data["company_name"] = name_elem.get_text(strip=True)

        location_elem = company_card.find(class_=lambda x: x and '_coLocation_' in x)
        if location_elem:
            company_data["location"] = location_elem.get_text(strip=True)

        description_elem = company_card.find(class_=lambda x: x and 'text-sm' in x)
        if description_elem:
            company_data["description"] = description_elem.get_text(strip=True)

        batch_elem = company_card.find('span', class_=lambda x: x and 'pill' in x and 'flex' in x)
        if batch_elem and 'svg' in str(batch_elem):
            batch_text = batch_elem.get_text(strip=True)
            company_data["batch"] = batch_text

        industries = []
        industry_elems = company_card.find_all('span', class_=lambda x: x and 'pill' in x and 'flex' not in x)
        for industry_elem in industry_elems:
            industry_text = industry_elem.get_text(strip=True)
            if industry_text and industry_text != batch_text:
                industries.append(industry_text)

        if industries:
            company_data["industries"] = industries

        company_data["founders"] = []

        return company_data

    except Exception as e:
        log(f"Error extracting company from main page for {company_name}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return None

def scrape_company_details(driver: uc.Chrome, company_url: str, company_name: str, verbose: bool = False, status: Optional[Status] = None) -> Optional[Dict[str, Any]]:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            log(f"Attempting to load {company_name} (attempt {attempt + 1}/{max_retries})", verbose, status=status, log_caller_file="scraper_utils.py")

            driver.get(company_url)

            try:
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                time.sleep(1)

                WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h1")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ycdc-card-new")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='company']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
                    )
                )
            except Exception as wait_error:
                log(f"Page load timeout for {company_name}: {wait_error}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                else:
                    raise wait_error

            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            company_data = {}

            header = soup.find('h1')
            if header:
                company_data["company_name"] = header.get_text(strip=True)

            location_elem = soup.find(class_=lambda x: x and '_coLocation_' in x)
            if location_elem:
                company_data["location"] = location_elem.get_text(strip=True)

            description_elem = soup.find(class_=lambda x: x and 'text-sm' in x)
            if description_elem and description_elem.find_parent(class_=lambda x: x and '_company_' in x):
                company_data["description"] = description_elem.get_text(strip=True)

            batch_elem = soup.find('span', class_=lambda x: x and 'pill' in x and 'flex' in x)
            if batch_elem and 'svg' in str(batch_elem):
                batch_text = batch_elem.get_text(strip=True)
                company_data["batch"] = batch_text

            industries = []
            industry_elems = soup.find_all('span', class_=lambda x: x and 'pill' in x and 'flex' not in x)
            for industry_elem in industry_elems:
                industry_text = industry_elem.get_text(strip=True)
                if industry_text and industry_text != batch_text:
                    industries.append(industry_text)

            if industries:
                company_data["industries"] = industries

            website_links = soup.find_all('a', href=lambda x: x and x.startswith('http') and 'ycombinator.com' not in x and 'startupschool.org' not in x)
            if website_links:
                company_data["website"] = website_links[0]['href']

            logo_elem = soup.find('img', src=lambda x: x and ('logo' in x.lower() or 'company' in x.lower() or x.startswith('https://bookface-images.s3')))
            if logo_elem and 'src' in logo_elem.attrs:
                company_data["logo_url"] = logo_elem['src']

            founders = []
            founder_cards = soup.find_all('div', class_='ycdc-card-new')

            log(f"Found {len(founder_cards)} potential founder cards for {company_name}", verbose, status=status, log_caller_file="scraper_utils.py")

            for founder_card in founder_cards[:20]:
                try:
                    founder_data = extract_founder_info(founder_card, verbose, status)
                    if founder_data:
                        founders.append(founder_data)
                except Exception as e:
                    log(f"Error extracting founder info: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                    continue

            company_data["founders"] = founders

            return company_data

        except Exception as e:
            log(f"Error loading {company_name} (attempt {attempt + 1}): {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
            if attempt < max_retries - 1:
                log(f"Retrying {company_name} in 3 seconds...", verbose, status=status, log_caller_file="scraper_utils.py")
                time.sleep(3)
            else:
                log(f"Failed to load {company_name} after {max_retries} attempts", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                return None

def extract_founder_info(founder_element, verbose: bool = False, status: Optional[Status] = None) -> Optional[Dict[str, Any]]:
    try:
        founder_data = {}

        name_elem = founder_element.find('div', class_=lambda x: x and 'text-xl' in x and 'font-bold' in x)
        if name_elem:
            founder_data["name"] = name_elem.get_text(strip=True)

        title_elem = founder_element.find('div', class_=lambda x: x and 'text-gray-600' in x)
        if title_elem:
            founder_data["title"] = title_elem.get_text(strip=True)

        bio_elem = founder_element.find('div', class_=lambda x: x and 'prose' in x)
        if bio_elem:
            bio_text = bio_elem.get_text(strip=True)
            founder_data["bio"] = bio_text

        avatar_elem = founder_element.find('img', src=lambda x: x and 'bookface-images.s3' in x)
        if avatar_elem and 'src' in avatar_elem.attrs:
            founder_data["avatar_url"] = avatar_elem['src']

        social_links = {}

        x_link = founder_element.find('a', href=lambda x: x and ('x.com' in x or 'twitter.com' in x))
        if x_link and 'href' in x_link.attrs:
            social_links["x"] = x_link['href']

        linkedin_link = founder_element.find('a', href=lambda x: x and 'linkedin.com' in x)
        if linkedin_link and 'href' in linkedin_link.attrs:
            social_links["linkedin"] = linkedin_link['href']

        if social_links:
            founder_data["social_links"] = social_links

        if founder_data.get("name"):
            return founder_data

        return None

    except Exception as e:
        log(f"Error extracting founder info: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return None
