import argparse
from rich.console import Console
from rich.status import Status

from services.support.logger_util import _log as log
from services.utils.networking.support.product_hunt import scrape_product_hunt_daily_leaderboard, scrape_product_hunt_products

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Networking Utilities")
    
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use.")
    
    # scrape only products
    parser.add_argument("--scrape-producthunt", action="store_true", help="Scrape Product Hunt daily leaderboard.")
    
    # scrape products and profiles
    parser.add_argument("--scrape-producthunt-products", action="store_true", help="Scrape detailed product information and maker social links.")

    # limit for scraping products
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of products to scrape.")
    
    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")

    args = parser.parse_args()

    if args.scrape_producthunt:
        with Status(f"[white]Scraping Product Hunt daily leaderboard for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            scrape_product_hunt_daily_leaderboard(args.profile, args.verbose, status)
            status.stop()
        log("Product Hunt daily leaderboard scraping completed.", args.verbose, log_caller_file="networking.py")
    elif args.scrape_producthunt_products:
        with Status(f"[white]Scraping detailed Product Hunt products for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            scrape_product_hunt_products(args.profile, args.verbose, status, args.limit)
            status.stop()
        log("Detailed Product Hunt product scraping completed.", args.verbose, log_caller_file="networking.py")
    else:
        log("No action specified. Use --scrape-producthunt to scrape Product Hunt daily leaderboard, or --scrape-producthunt-products for detailed product scraping.", is_error=True, log_caller_file="networking.py")
        parser.print_help()

if __name__ == "__main__":
    main()
