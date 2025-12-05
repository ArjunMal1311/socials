from rich.status import Status
from typing import Optional, Dict, Any
from services.support.logger_util import _log as log
from services.platform.x.support.x_dm_utils import check_dm_button
from services.platform.linkedin.support.connection_utils import send_connection_request

def process_product_socials(linkedin_driver, x_driver, product_data: Dict[str, Any], verbose: bool = False, status: Optional[Status] = None, profile_linkedin: str = "Default", profile_x: str = "Default") -> Dict[str, Any]:
    log(f"Processing social links for product: {product_data.get('Name', 'N/A')}", verbose, status, log_caller_file="ph_social_processor.py")
    
    socials_output = {"linkedin": {"profiles": []}, "x": {"profiles": []}}
    social_links_str = product_data.get("Links (Socials)", "N/A")
    if social_links_str == "N/A":
        product_data["socials"] = socials_output
        return product_data

    social_links = [link.strip() for link in social_links_str.split(',') if link.strip()]

    for link in social_links:
        if "linkedin.com/in/" in link:
            username = link.split("linkedin.com/in/")[-1].strip('/')
            connection_sent = send_connection_request(linkedin_driver, link, verbose, status)
            socials_output["linkedin"]["profiles"].append({"url": link, "connection_sent": connection_sent, "dm": False})
        elif "x.com/" in link or "twitter.com/" in link:
            username = link.split("x.com/")[-1].split("twitter.com/")[-1].strip('/')
            dm_available = check_dm_button(x_driver, username, verbose, status)
            socials_output["x"]["profiles"].append({"url": link, "dm_available": dm_available, "dm": False})
    
    product_data["socials"] = socials_output
    log(f"Finished processing social links for product: {product_data.get('Name', 'N/A')}", verbose, status, log_caller_file="ph_social_processor.py", data=socials_output)
    return product_data
