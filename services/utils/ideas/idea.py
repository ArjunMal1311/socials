import argparse

from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from services.utils.ideas.support.clean import clean_reddit_data
from services.utils.ideas.support.token_counter import calculate_reddit_tokens
from services.utils.ideas.support.idea_utils import _log, aggregate_and_suggest_ideas


console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Multi-platform Content Idea Generator")
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use from profiles.py")
    parser.add_argument("--platforms", nargs='+', default=[], choices=["reddit"], help="Specify platforms to pull data from (e.g., --platforms reddit).")
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")
    parser.add_argument("--clean", action="store_true", help="Clean Reddit data by removing items with score 1 and 0 replies.")
    parser.add_argument("--generate-content", action="store_true", help="Generate content ideas")
    parser.add_argument("--tokens", action="store_true", help="Print the number of tokens in the latest Reddit JSON file.")

    args = parser.parse_args()

    if not args.platforms:
        _log("Please specify at least one platform to pull data from using --platforms.", is_error=True)
        parser.print_help()
        return

    if args.tokens:
        with Status(f"[white]Calculating tokens for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            token_count = calculate_reddit_tokens(args.profile, args.verbose, status)
            status.stop()
        
        if token_count is not None:
            _log(f"Total tokens in latest Reddit JSON file: {token_count}", args.verbose)
        else:
            _log("Failed to calculate Reddit tokens.", args.verbose, is_error=True)
        return

    if args.clean:
        with Status(f"[white]Cleaning Reddit data for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            clean_reddit_data(args.profile, args.verbose, status)
            status.stop()
        if not args.generate_content:
            _log("Cleaning completed. Content generation skipped as --generate-content was not specified.", args.verbose)
            return

    if args.generate_content:
        with Status(f"[white]Generating content ideas for profile '{args.profile}' from {', '.join(args.platforms).upper()} ...[/white]", spinner="dots", console=console) as status:
            suggestions = aggregate_and_suggest_ideas(
                profile_name=args.profile,
                platforms=args.platforms,
                api_key=args.api_key,
                status=status,
                verbose=args.verbose
            )
            status.stop()

            if suggestions:
                console.print("\n[bold green]--- Generated Content Ideas ---[/bold green]")
                console.print(suggestions)
                console.print("[bold green]-------------------------------[/bold green]")
            else:
                _log("No content ideas generated.", args.verbose, is_error=True)
    else:
        _log("No action specified. Use --clean to clean data or --generate-content to generate ideas.", is_error=True)

if __name__ == "__main__":
    main()
