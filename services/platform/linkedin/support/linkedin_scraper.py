import re
import os
import json
import time

from datetime import datetime
from bs4 import BeautifulSoup
from rich.console import Console
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC

console = Console()

def _log(message: str, verbose: bool, is_error: bool = False, status=None):
    if status and (is_error or verbose):
        status.stop()

    log_message = message
    if is_error:
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[linkedin_scraper.py] {timestamp}|[{color}]{log_message}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[linkedin_scraper.py] {timestamp}|[{color}]{message}[/{color}]")
    elif status:
        status.update(message)

def scrape_linkedin_profile(driver, profile_url: str, verbose: bool = False, status=None) -> str:
    try:
        _log(f"Navigating to LinkedIn profile: {profile_url}", verbose, status)
        driver.get(profile_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        time.sleep(5)

        page_source = driver.page_source

        _log(f"Successfully scraped raw HTML from {profile_url}", verbose=verbose, status=status)
        return page_source
    except Exception as e:
        _log(f"Error scraping LinkedIn profile {profile_url}: {e}", verbose=verbose, is_error=True, status=status)
        return ""

def parse_linkedin_html(raw_html: str, profile_name: str, verbose: bool = False, status=None) -> dict:
    try:
        soup = BeautifulSoup(raw_html, "html.parser")
        
        for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
            script_or_style.extract()
            
        main_content_text = []
        profile_name_extracted = "N/A"
        profile_job_title = "N/A"

        # Extract Profile Name (usually in a prominent h1 tag or similar)
        name_tag = soup.find("h1")
        if name_tag:
            profile_name_extracted = name_tag.get_text(strip=True)
            _log(f"Extracted Profile Name: {profile_name_extracted}", verbose, status)

        # Extract Job Title (often a p tag in the intro section)
        job_title_tag = soup.find("div", class_=lambda x: x and "text-body-medium" in x and "break-words" in x)
        if job_title_tag:
            profile_job_title = job_title_tag.get_text(strip=True)
            _log(f"Extracted Job Title: {profile_job_title}", verbose, status)

        # Common section headings on LinkedIn profiles
        relevant_headings = ["About", "Experience", "Education", "Skills", "Licenses & certifications", "Honors & awards"]

        for section in soup.find_all("section"):
            h2_tag = section.find("h2")
            if h2_tag and any(heading in h2_tag.get_text(strip=True) for heading in relevant_headings):
                section_text = section.get_text(separator=" ", strip=True)
                main_content_text.append(section_text)
            
        if not main_content_text and soup.body:
            main_content_text.append(soup.body.get_text(separator=" ", strip=True))

        combined_text = " ".join(main_content_text).strip()

        _log("Successfully extracted relevant text from LinkedIn HTML content.", verbose=verbose, status=status)
        
        return {
            "name": profile_name_extracted,
            "job_title": profile_job_title,
            "profile_text": combined_text
        }
    except Exception as e:
        _log(f"Error parsing LinkedIn HTML content: {e}", verbose=verbose, is_error=True, status=status)
        return {"name": "N/A", "job_title": "N/A", "profile_text": ""}
