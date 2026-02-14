import os
import json
import time
import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict, Any

from rich.status import Status

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from services.support.logger_util import _log as log
from services.support.web_driver_handler import cleanup_chrome_locks, kill_chrome_processes_by_user_data_dir
from services.support.path_config import get_product_hunt_output_file_path, get_browser_data_dir, ensure_dir_exists

from services.platform.producthunt.support.format_product_data import _format_product_data

def scout_product_details(driver: uc.Chrome, product_data: Dict[str, Any], verbose: bool = False, status: Optional[Status] = None) -> Dict[str, Any]:
    product_link = product_data.get("product_link")
    if not product_link or product_link == "N/A":
        log(f"Invalid or missing product link provided for details scouting. Skipping. Product: {product_data.get('product_name')}.", verbose, is_error=True, status=status)
        return product_data

    log(f"Scouting details for product: {product_data.get('product_name')} from {product_link}", verbose, status=status)

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

        logo_elem = (soup.find('img', attrs={'data-test': 'post-thumbnail'}) or
                    soup.find('img', src=lambda x: x and ('ph-files' in x or 'thumbnail' in x.lower())) or
                    soup.find('img', class_=lambda x: x and ('thumbnail' in x.lower() or 'logo' in x.lower())))
        logo_url = logo_elem['src'] if logo_elem and 'src' in logo_elem.attrs else ""

        product_data["product_description"] = product_description
        product_data["website_link"] = website_link
        product_data["logo_url"] = logo_url

        maker_elements = driver.find_elements(By.CSS_SELECTOR, "div.ml-auto.hidden.flex-row.items-center.gap-4.sm\\:flex a[href^='/@']")

        founders_data = []
        for maker_element in maker_elements:
            try:
                ActionChains(driver).move_to_element(maker_element).perform()

                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-test^='user-hover-card-']"))
                )
                time.sleep(1)

                hover_card_soup = BeautifulSoup(driver.page_source, 'html.parser')
                hover_card = hover_card_soup.find('div', attrs={'data-test': lambda x: x and 'user-hover-card-' in x})

                founder_info = {
                    "name": "",
                    "img": "",
                    "links": []
                }

                if hover_card:
                    name_elem = (hover_card.find('a', class_='text-16 font-semibold') or
                               hover_card.find('a', class_=lambda x: x and 'font-semibold' in x) or
                               hover_card.find('div', class_=lambda x: x and 'font-semibold' in x))
                    if name_elem:
                        founder_info["name"] = name_elem.get_text(strip=True)

                    img_elem = (hover_card.find('img', class_='rounded-full') or
                              hover_card.find('img', src=lambda x: x and 'ph-avatars' in x) or
                              hover_card.find('img'))
                    if img_elem and 'src' in img_elem.attrs:
                        founder_info["img"] = img_elem['src']

                    x_link_tag = hover_card.find('a', href=lambda href: href and ('x.com/' in href or 'twitter.com/' in href))
                    if x_link_tag and 'href' in x_link_tag.attrs:
                        founder_info["links"].append(x_link_tag['href'])

                    linkedin_link_tag = hover_card.find('a', href=lambda href: href and 'linkedin.com/in/' in href)
                    if linkedin_link_tag and 'href' in linkedin_link_tag.attrs:
                        founder_info["links"].append(linkedin_link_tag['href'])

                if founder_info["name"]:
                    founders_data.append(founder_info)

            except Exception as e:
                log(f"Error hovering or scouting founder info for a maker: {e}", verbose, is_error=True, status=status)
                continue

        product_data["founders_data"] = founders_data

        log(f"Successfully scoutd details for {product_data.get('product_name')}.", verbose, status=status)

        return product_data

    except Exception as e:
        log(f"Error scouting details for {product_data.get('product_name')}: {e}", verbose, is_error=True, status=status)
        return product_data

def scout_product_hunt_products(profile_name: str, verbose: bool = False, status: Optional[Status] = None, limit: Optional[int] = None, headless: bool = True) -> List[Dict[str, Any]]:
    log(f"Starting Product Hunt today's leaderboard scouting for profile '{profile_name}'...", verbose, status=status)

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

        log("Initializing undetected_chromedriver for Product Hunt scouting...", verbose, status=status)

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={browser_user_data_dir}")
        options.add_argument(f"--profile-directory=Default")
        if headless:
            options.add_argument("--headless")

        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/chromium-browser", version_main=144)

        log(f"Directly navigating to Product Hunt leaderboard: {target_url}", verbose, status=status)
        driver.get(target_url)

        log("Waiting for product items on Product Hunt daily leaderboard...", verbose, status=status)
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
                    "scoutd_date": yesterday.isoformat()
                })
            except Exception as e:
                log(f"Error parsing leaderboard product item: {e}", verbose, is_error=True, status=status)
                continue

        if not leaderboard_products:
            log("No products found on the daily leaderboard. Cannot scout detailed product information.", verbose, is_error=True, status=status)
            return []

        products_to_scout = leaderboard_products[:limit] if limit is not None else leaderboard_products

        for product_item in products_to_scout:
            time.sleep(20)
            detailed_product_data = scout_product_details(driver, product_item, verbose, status)
            if detailed_product_data:
                formatted_data = _format_product_data(detailed_product_data)
                all_formatted_products.append(formatted_data)
                log(f"Successfully scoutd and formatted product information for {formatted_data['core']['name']}.", verbose, status=status)

        output_file_path = get_product_hunt_output_file_path(profile_name, yesterday.strftime("%Y%m%d"))
        ensure_dir_exists(os.path.dirname(output_file_path))
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(all_formatted_products, f, indent=2, ensure_ascii=False)

        log(f"scoutd and saved {len(all_formatted_products)} products to {output_file_path}", verbose, status=status)

        return all_formatted_products

    except Exception as e:
        log(f"An error occurred during Product Hunt scouting: {e}", verbose, is_error=True, status=status)
        return []
    finally:
        if driver:
            driver.quit()
        kill_chrome_processes_by_user_data_dir(browser_user_data_dir, verbose=verbose, status=status)
        cleanup_chrome_locks(browser_user_data_dir, verbose=verbose, status=status)
        log(f"Product Hunt scouting completed for profile '{profile_name}'.", verbose, status=status)
