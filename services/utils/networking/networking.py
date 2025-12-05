import argparse

from rich.status import Status
from rich.console import Console
from services.support.logger_util import _log as log
from services.utils.networking.support.ph_scraper import scrape_product_hunt_products
from services.utils.networking.support.ph_sheets_integration import load_and_process_existing_socials, store_latest_data_to_sheets

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Networking Utilities")
    
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use.")
    
    # scrape products and profiles
    parser.add_argument("--scrape-producthunt", action="store_true", help="Scrape detailed product information and maker social links.")

    # limit for scraping products
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of products to scrape.")
    
    # process socials
    parser.add_argument("--process-socials", action="store_true", help="Process social links for scraped Product Hunt products.")
    parser.add_argument("--profile-x", type=str, default="Default", help="Browser profile name to use for X (Twitter) social actions.")
    parser.add_argument("--profile-linkedin", type=str, default="Default", help="Browser profile name to use for LinkedIn social actions.")
    
    parser.add_argument("--store", action="store_true", help="Stores the latest scraped Product Hunt data to Google Sheet.")
    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")

    args = parser.parse_args()

    if args.scrape_producthunt:
        with Status(f"[white]Scraping detailed Product Hunt products for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            scrape_product_hunt_products(args.profile, args.verbose, status, args.limit, args.profile_x, args.profile_linkedin)
            status.stop()
        log("Detailed Product Hunt product scraping completed.", args.verbose, log_caller_file="networking.py")
    elif args.process_socials:
        with Status(f"[white]Processing social links for Product Hunt products for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            load_and_process_existing_socials(args.profile, args.verbose, status, args.profile_x, args.profile_linkedin)
            status.stop()
        log("Social link processing completed.", args.verbose, log_caller_file="networking.py")
    elif args.store:
        with Status(f"[white]Storing latest Product Hunt data for profile '{args.profile}' to Google Sheet[/white]", spinner="dots", console=console) as status:
            store_latest_data_to_sheets(args.profile, args.verbose, status)
            status.stop()
        log("Storing latest Product Hunt data to Google Sheet completed.", args.verbose, log_caller_file="networking.py")
    else:
        log("No action specified. Use --scrape-producthunt for detailed product scraping, --process-socials to process social links, or --store to store latest data to Google Sheet.", is_error=True, log_caller_file="networking.py")
        parser.print_help()

if __name__ == "__main__":
    main()
