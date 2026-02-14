import uuid

from typing import Dict, Any
from datetime import datetime

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

        if founder_obj["name"]:
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
