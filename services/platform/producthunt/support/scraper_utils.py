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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import cleanup_chrome_locks, kill_chrome_processes_by_user_data_dir
from services.support.path_config import get_product_hunt_scrape_output_file_path, get_browser_data_dir, ensure_dir_exists

console = Console()

def _format_product_data(product_data: Dict[str, Any]) -> Dict[str, Any]:
    scraped_at = datetime.now().isoformat()

    social_links_str = product_data.get("Links (Socials)", "")
    social_links = social_links_str.split(", ") if social_links_str else []

    founders = []
    for link in social_links:
        if link and link != "N/A":
            founders.append(link)

    return {
        "id": str(uuid.uuid4()),
        "source": "product_hunt",
        "scraped_at": scraped_at,
        "core": {
            "name": product_data.get("product_name", "N/A"),
            "description": product_data.get("product_description", "N/A"),
            "website": product_data.get("website_link", "N/A"),
            "source_url": product_data.get("product_link", "N/A")
        },
        "founders": founders,
        "data": {
            "upvotes_count": product_data.get("upvotes", 0),
            "tagline": product_data.get("tagline", "N/A")
        }
    }

def scrape_product_details(driver: uc.Chrome, product_data: Dict[str, Any], verbose: bool = False, status: Optional[Status] = None) -> Dict[str, Any]:
    product_link = product_data.get("product_link")
    if not product_link or product_link == "N/A":
        log(f"Invalid or missing product link provided for details scraping. Skipping. Product: {product_data.get('product_name')}.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return product_data

    log(f"Scraping details for product: {product_data.get('product_name')} from {product_link}", verbose, status=status, log_caller_file="scraper_utils.py")

    try:
        driver.get(product_link)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test='header']"))
        )
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        description_div = soup.find('div', class_='relative text-16 font-normal text-gray-700')
        product_description = description_div.text.strip() if description_div else "N/A"

        website_button = soup.find('a', attrs={'data-test': 'visit-website-button'})
        website_link = website_button['href'] if website_button and 'href' in website_button.attrs else "N/A"

        product_data["product_description"] = product_description
        product_data["website_link"] = website_link

        maker_elements = driver.find_elements(By.CSS_SELECTOR, "div.ml-auto.hidden.flex-row.items-center.gap-4.sm\\:flex a[href^='/@']")

        all_maker_socials = []
        for maker_element in maker_elements:
            try:
                ActionChains(driver).move_to_element(maker_element).perform()

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test^='user-hover-card-'] a[href*='x.com'], div[data-test^='user-hover-card-'] a[href*='twitter.com'], div[data-test^='user-hover-card-'] a[href*='linkedin.com']"))
                )
                time.sleep(1)

                hover_card_soup = BeautifulSoup(driver.page_source, 'html.parser')

                hover_card = hover_card_soup.find('div', attrs={'data-test': lambda x: x and 'user-hover-card-' in x})

                social_links = {"x": "N/A", "linkedin": "N/A"}
                if hover_card:
                    x_link_tag = hover_card.find('a', href=lambda href: href and ('x.com/' in href or 'twitter.com/' in href))
                    if x_link_tag:
                        social_links["x"] = x_link_tag['href']

                    linkedin_link_tag = hover_card.find('a', href=lambda href: href and 'linkedin.com/in/' in href)
                    if linkedin_link_tag:
                        social_links["linkedin"] = linkedin_link_tag['href']

                if social_links["x"] != "N/A" or social_links["linkedin"] != "N/A":
                    all_maker_socials.append(social_links)

            except Exception as e:
                log(f"Error hovering or scraping social links for a maker: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                continue

        formatted_social_links = []
        for socials in all_maker_socials:
            if socials["x"] != "N/A":
                formatted_social_links.append(socials["x"])
            if socials["linkedin"] != "N/A":
                formatted_social_links.append(socials["linkedin"])

        product_data["Links (Socials)"] = ", ".join(formatted_social_links) if formatted_social_links else "N/A"

        log(f"Successfully scraped details for {product_data.get('product_name')}.", verbose, status=status, log_caller_file="scraper_utils.py")

        return product_data

    except Exception as e:
        log(f"Error scraping details for {product_data.get('product_name')}: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return product_data

def scrape_product_hunt_products(profile_name: str, verbose: bool = False, status: Optional[Status] = None, limit: Optional[int] = None, headless: bool = True) -> List[Dict[str, Any]]:
    log(f"Starting Product Hunt previous day leaderboard scraping for profile '{profile_name}'...", verbose, status=status, log_caller_file="scraper_utils.py")

    from datetime import timedelta
    yesterday = datetime.now() - timedelta(days=1)
    target_url = f"https://www.producthunt.com/leaderboard/daily/{yesterday.year}/{yesterday.month}/{yesterday.day}"

    browser_user_data_dir = get_browser_data_dir("Default")
    ensure_dir_exists(browser_user_data_dir)

    driver = None
    all_formatted_products = []

    try:
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)

        log("Initializing undetected_chromedriver for Product Hunt scraping...", verbose, status=status, log_caller_file="scraper_utils.py")

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={browser_user_data_dir}")
        options.add_argument(f"--profile-directory=Default")
        if headless:
            options.add_argument("--headless")

        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium-browser", version_main=142)

        log("Navigating to Google and searching for Product Hunt...", verbose, status=status, log_caller_file="scraper_utils.py")
        driver.get("https://www.google.com")

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_query = f"Product Hunt daily leaderboard {yesterday.year}/{yesterday.month}/{yesterday.day}"
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.RETURN)

        log("Waiting for Product Hunt link in Google search results...", verbose, status=status, log_caller_file="scraper_utils.py")
        product_hunt_link_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, f"//a[contains(@href, '{target_url}')]"))
        )
        product_hunt_link_element.click()

        log("Waiting for product items on Product Hunt daily leaderboard...", verbose, status=status, log_caller_file="scraper_utils.py")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-test^='post-item-']"))
        )

        soup_leaderboard = BeautifulSoup(driver.page_source, 'html.parser')
        leaderboard_products = []
        for section in soup_leaderboard.find_all('section', attrs={'data-test': lambda x: x and x.startswith('post-item-')}):
            try:
                name_span = section.find('span', attrs={'data-test': lambda x: x and x.startswith('post-name-')})
                name_tag = name_span.find('a') if name_span else None
                product_name = name_tag.text.strip() if name_tag else "N/A"
                product_link = f"https://www.producthunt.com{name_tag['href']}" if name_tag and 'href' in name_tag.attrs else "N/A"
                tagline_span = section.find('span', class_='text-16 text-secondary')
                tagline = tagline_span.text.strip() if tagline_span else "N/A"
                upvote_button = section.find('button', attrs={'data-test': 'vote-button'})
                upvotes = int(upvote_button.find('p').text.strip()) if upvote_button and upvote_button.find('p') else 0

                leaderboard_products.append({
                    "product_name": product_name,
                    "product_link": product_link,
                    "tagline": tagline,
                    "upvotes": upvotes,
                    "scraped_date": yesterday.isoformat()
                })
            except Exception as e:
                log(f"Error parsing leaderboard product item: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
                continue

        if not leaderboard_products:
            log("No products found on the daily leaderboard. Cannot scrape detailed product information.", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
            return []

        products_to_scrape = leaderboard_products[:limit] if limit is not None else leaderboard_products

        for product_item in products_to_scrape:
            time.sleep(20)
            detailed_product_data = scrape_product_details(driver, product_item, verbose, status)
            if detailed_product_data:
                formatted_data = _format_product_data(detailed_product_data)
                all_formatted_products.append(formatted_data)
                log(f"Successfully scraped and formatted product information for {formatted_data['core']['name']}.", verbose, status=status, log_caller_file="scraper_utils.py")

        output_file_path = get_product_hunt_scrape_output_file_path(profile_name, yesterday.strftime("%Y%m%d"))
        ensure_dir_exists(os.path.dirname(output_file_path))
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_formatted_products, f, indent=2, ensure_ascii=False)

        log(f"Scraped and saved {len(all_formatted_products)} products to {output_file_path}", verbose, status=status, log_caller_file="scraper_utils.py")

        return all_formatted_products

    except Exception as e:
        log(f"An error occurred during Product Hunt scraping: {e}", verbose, is_error=True, status=status, log_caller_file="scraper_utils.py")
        return []
    finally:
        if driver:
            driver.quit()
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)
        log(f"Product Hunt scraping completed for profile '{profile_name}'.", verbose, status=status, log_caller_file="scraper_utils.py")
