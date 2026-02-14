import uuid

from typing import Dict, Any
from datetime import datetime

def _format_product_data(product_data: Dict[str, Any]) -> Dict[str, Any]:
    scraped_at = datetime.now().isoformat()

    founders_data = product_data.get("founders_data", [])

    founders = []
    for founder in founders_data:
        founder_obj = {
            "name": founder.get("name", ""),
            "img": founder.get("img", ""),
            "links": founder.get("links", [])
        }
        if founder_obj["name"]:
            founders.append(founder_obj)

    return {
        "id": str(uuid.uuid4()),
        "source": "product_hunt",
        "scraped_at": scraped_at,
        "core": {
            "name": product_data.get("product_name", "N/A"),
            "description": product_data.get("product_description", "N/A"),
            "website": product_data.get("website_link", "N/A"),
            "source_url": product_data.get("product_link", "N/A"),
            "logo": product_data.get("logo_url", "")
        },
        "founders": founders,
        "data": {
            "upvotes_count": product_data.get("upvotes", 0),
            "tagline": product_data.get("tagline", "N/A")
        }
    }
