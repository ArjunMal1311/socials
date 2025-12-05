import os
import json
import time
import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from datetime import datetime
from rich.status import Status
from rich.console import Console
from selenium.webdriver.common.by import By
from typing import Optional, List, Dict, Any
from selenium.webdriver.common.keys import Keys
from services.support.logger_util import _log as log
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from services.support.path_config import get_product_hunt_profile_dir, ensure_dir_exists, BASE_TMP_DIR
from services.support.web_driver_handler import cleanup_chrome_locks, kill_chrome_processes_by_user_data_dir

console = Console()

def scrape_product_hunt_products(profile_name: str, verbose: bool = False, status: Optional[Status] = None, limit: Optional[int] = None, profile_x: str = "Default", profile_linkedin: str = "Default") -> List[Dict[str, Any]]:
    log(f"Starting detailed Product Hunt product scraping for profile '{profile_name}'...", verbose, status=status, log_caller_file="ph_scraper.py")

    today = datetime.now()
    target_url = f"https://www.producthunt.com/leaderboard/daily/{today.year}/{today.month}/{today.day}"
    
    browser_user_data_dir = os.path.join(BASE_TMP_DIR, "browser-data", "Default")
    ensure_dir_exists(browser_user_data_dir)

    product_hunt_data_dir = get_product_hunt_profile_dir(profile_name)
    ensure_dir_exists(product_hunt_data_dir)

    driver = None
    all_scraped_products_detailed = []

    try:
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)
        
        log("Initializing undetected_chromedriver for detailed scraping...", verbose, status=status, log_caller_file="ph_scraper.py")
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={browser_user_data_dir}")
        options.add_argument(f"--profile-directory=Default")

        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium-browser", version_main=142)
        
        log("Navigating to Google and searching for Product Hunt...", verbose, status=status, log_caller_file="ph_scraper.py")
        driver.get("https://www.google.com")

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_query = f"Product Hunt daily leaderboard {today.year}/{today.month}/{today.day}"
        search_box.send_keys(search_query)
        search_box.send_keys(Keys.RETURN)

        log("Waiting for Product Hunt link in Google search results...", verbose, status=status, log_caller_file="ph_scraper.py")
        product_hunt_link_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, f"//a[contains(@href, '{target_url}')]" ))
        )
        product_hunt_link_element.click()

        log("Waiting for product items on Product Hunt daily leaderboard...", verbose, status=status, log_caller_file="ph_scraper.py")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-test^='post-item-']"))
        )

        soup_leaderboard = BeautifulSoup(driver.page_source, 'html.parser')
        leaderboard_products = []
        for section in soup_leaderboard.find_all('section', attrs={'data-test': lambda x: x and x.startswith('post-item-')}):
            try:
                name_div = section.find('div', attrs={'data-test': lambda x: x and x.startswith('post-name-')})
                name_tag = name_div.find('a') if name_div else None
                product_name = name_tag.text.strip() if name_tag else "N/A"
                product_link = f"https://www.producthunt.com{name_tag['href']}" if name_tag and 'href' in name_tag.attrs else "N/A"
                tagline_div = section.find('div', class_='text-16 font-normal text-dark-gray text-secondary')
                tagline = tagline_div.text.strip() if tagline_div else "N/A"
                upvote_button = section.find('button', attrs={'data-test': 'vote-button'})
                upvotes = int(upvote_button.find('p').text.strip()) if upvote_button and upvote_button.find('p') else 0

                leaderboard_products.append({
                    "product_name": product_name,
                    "product_link": product_link,
                    "tagline": tagline,
                    "upvotes": upvotes,
                    "scraped_date": today.isoformat()
                })
            except Exception as e:
                log(f"Error parsing leaderboard product item: {e}", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
                continue
        
        if not leaderboard_products:
            log("No products found on the daily leaderboard. Cannot scrape detailed product information.", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
            return []

        products_to_scrape = leaderboard_products[:limit] if limit is not None else leaderboard_products

        for product_item in products_to_scrape:
            time.sleep(35)
            detailed_product_data = scrape_product_details(driver, product_item, verbose, status)
            if detailed_product_data:
                formatted_data = {
                    "Name": detailed_product_data.get("product_name", "N/A"),
                    "Links (Socials)": detailed_product_data.get("Links (Socials)", "N/A"),
                    "Status": "Pending", 
                    "Link (PH)": detailed_product_data.get("product_link", "N/A"),
                    "Link (Website)": detailed_product_data.get("website_link", "N/A"),
                    "Company Information": detailed_product_data.get("product_description", "N/A"), 
                    "Response": "N/A", 
                    "Output": "N/A", 
                    "Last Updated": detailed_product_data.get("scraped_date", datetime.now().isoformat()),
                    "Activity": "N/A", 
                    "Next Action": "N/A", 
                    "Improvements": "N/A",
                    "socials": json.dumps(detailed_product_data.get("socials", {}))
                }
                all_scraped_products_detailed.append(formatted_data)
                log(f"Successfully scraped detailed product information for {formatted_data.get("Name")}.", verbose, status=status, log_caller_file="ph_scraper.py", data=formatted_data)

        output_file_path = os.path.join(product_hunt_data_dir, f"product_hunt_detailed_{today.strftime('%Y%m%d')}.json")
        ensure_dir_exists(product_hunt_data_dir)
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_scraped_products_detailed, f, indent=2, ensure_ascii=False)
        
        log(f"Scraped {len(all_scraped_products_detailed)} detailed products and saved to {output_file_path}", verbose, status=status, log_caller_file="ph_scraper.py")
        
        return all_scraped_products_detailed

    except Exception as e:
        log(f"An error occurred during detailed Product Hunt scraping: {e}", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
        return []
    finally:
        if driver:
            driver.quit()
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)
        log(f"Detailed Product Hunt scraping completed for profile '{profile_name}'.", verbose, status=status, log_caller_file="ph_scraper.py")


def scrape_product_details(driver: uc.Chrome, product_data: Dict[str, Any], verbose: bool = False, status: Optional[Status] = None) -> Dict[str, Any]:
    product_link = product_data.get("product_link")
    if not product_link:
        log(f"No product link provided for details scraping. Skipping. ", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
        return product_data

    log(f"Scraping details for product: {product_data.get('product_name')} from {product_link}", verbose, status=status, log_caller_file="ph_scraper.py")

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
                log(f"Error hovering or scraping social links for a maker: {e}", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
                continue
        
        formatted_social_links = []
        for socials in all_maker_socials:
            if socials["x"] != "N/A":
                formatted_social_links.append(socials["x"])
            if socials["linkedin"] != "N/A":
                formatted_social_links.append(socials["linkedin"])
        
        product_data["Links (Socials)"] = ", ".join(formatted_social_links) if formatted_social_links else "N/A"

        product_data.pop("maker_profile_links", None)
        product_data.pop("makers_socials", None)


        log(f"Successfully scraped details for {product_data.get('product_name')}.", verbose, status, log_caller_file="ph_scraper.py")

        return product_data

    except Exception as e:
        log(f"Error scraping details for {product_data.get('product_name')}: {e}", verbose, is_error=True, status=status, log_caller_file="ph_scraper.py")
        return product_data
