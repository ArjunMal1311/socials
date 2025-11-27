import os
import json
import argparse

from datetime import datetime
from rich.status import Status
from dotenv import load_dotenv
from rich.console import Console
from services.support.logger_util import _log as log
from services.utils.ideas.support.aggregator import aggregate_platform_data
from services.utils.ideas.support.composite_scorer import add_composite_scores
from services.utils.ideas.support.clean import clean_reddit_data, clean_x_data
from services.platform.reddit.support.file_manager import get_latest_dated_json_file
from services.utils.ideas.support.idea_utils import generate_content_titles, generate_video_scripts
from services.utils.ideas.support.token_counter import calculate_reddit_tokens, calculate_x_tokens, calculate_aggregated_tokens
from services.support.path_config import get_titles_output_dir, get_scripts_output_dir, get_reddit_profile_dir, get_community_dir, get_ideas_aggregated_dir

console = Console()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Multi-platform Content Idea Generator")
    
    # profile
    parser.add_argument("--profile", type=str, default="Default", help="Profile name to use from profiles.py")

    # platforms (currently reddit, x only)
    parser.add_argument("--platforms", nargs='+', default=[], choices=["reddit", "x"], help="Specify platforms to pull data from (e.g., --platforms reddit x).")

    # clean
    parser.add_argument("--clean", action="store_true", help="Clean Reddit data by removing items with score 1 and 0 replies.")

    # generate titles
    parser.add_argument("--generate-titles", action="store_true", help="Generate content titles based on scraped data.")

    # generate scripts
    parser.add_argument("--generate-scripts", action="store_true", help="Generate video scripts for selected ideas.")

    # additional
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logging output.")
    parser.add_argument("--tokens", action="store_true", help="Print the number of tokens in the latest Reddit JSON file.")
    parser.add_argument("--api-key", type=str, default=None, help="Specify a Gemini API key to use for the session, overriding environment variables.")
    parser.add_argument("--clear", action="store_true", help="Delete all files under the Reddit and X community folders for the specified profile.")
    parser.add_argument("--composite", action="store_true", help="Calculate and add composite scores to Reddit and X data.")
    parser.add_argument("--aggregate", action="store_true", help="Aggregate data from specified platforms into a single JSON file.")

    args = parser.parse_args()

    if args.clear:
        profile_name = args.profile
        reddit_dir = get_reddit_profile_dir(profile_name)
        x_community_dir = get_community_dir(profile_name)

        log(f"Clearing data for profile '{profile_name}'", args.verbose, log_caller_file="idea.py")

        for directory in [reddit_dir, x_community_dir]:
            if os.path.exists(directory):
                with Status(f"[white]Deleting files in {directory}...[/white]", spinner="dots", console=console) as status:
                    for filename in os.listdir(directory):
                        file_path = os.path.join(directory, filename)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            log(f"Deleted {filename}", args.verbose, status=status, log_caller_file="idea.py")
                log(f"Cleared directory: {directory}", args.verbose, log_caller_file="idea.py")
            else:
                log(f"Directory does not exist, skipping: {directory}", args.verbose, log_caller_file="idea.py")
        log("Clearing completed.", args.verbose, log_caller_file="idea.py")
        return

    if args.composite:
        with Status(f"[white]Calculating composite scores for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            add_composite_scores(args.profile, args.verbose, status)
            status.stop()
        log("Composite score calculation completed.", args.verbose, log_caller_file="idea.py")
        return

    if args.aggregate:
        with Status(f"[white]Aggregating data for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            aggregate_platform_data(args.profile, args.verbose, status)
            status.stop()
        log("Data aggregation completed.", args.verbose, log_caller_file="idea.py")
        return

    if not args.platforms:
        log("Please specify at least one platform to pull data from using --platforms.", is_error=True, log_caller_file="idea.py")
        parser.print_help()
        return

    if args.tokens:
        token_count_output = False
        with Status(f"[white]Calculating tokens for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            if "reddit" in args.platforms:
                reddit_token_count = calculate_reddit_tokens(args.profile, args.verbose, status)
                if reddit_token_count is not None:
                    log(f"Total tokens in latest Reddit JSON file: {reddit_token_count}", args.verbose, log_caller_file="idea.py")
                    token_count_output = True
                else:
                    log("Failed to calculate Reddit tokens.", args.verbose, is_error=True, log_caller_file="idea.py")
            
            if "x" in args.platforms:
                x_token_count = calculate_x_tokens(args.profile, args.verbose, status)
                if x_token_count is not None:
                    log(f"Total tokens in latest X JSON file: {x_token_count}", args.verbose, log_caller_file="idea.py")
                    token_count_output = True
                else:
                    log("Failed to calculate X tokens.", args.verbose, is_error=True, log_caller_file="idea.py")

            aggregated_dir = get_ideas_aggregated_dir(args.profile)
            aggregated_file = os.path.join(aggregated_dir, "aggregate.json")
            if os.path.exists(aggregated_file):
                aggregated_token_count = calculate_aggregated_tokens(args.profile, args.verbose, status)
                if aggregated_token_count is not None:
                    log(f"Total tokens in aggregated JSON file: {aggregated_token_count}", args.verbose, log_caller_file="idea.py")
                    token_count_output = True
                else:
                    log("Failed to calculate aggregated tokens.", args.verbose, is_error=True, log_caller_file="idea.py")
            elif token_count_output:
                log("No aggregated data found to calculate tokens.", args.verbose, is_error=False, log_caller_file="idea.py")

            status.stop()
        return

    if args.clean:
        with Status(f"[white]Cleaning data for profile '{args.profile}'[/white]", spinner="dots", console=console) as status:
            if "reddit" in args.platforms:
                log("Cleaning Reddit data...", args.verbose, status=status, log_caller_file="idea.py")
                clean_reddit_data(args.profile, args.verbose, status)
            if "x" in args.platforms:
                log("Cleaning X data...", args.verbose, status=status, log_caller_file="idea.py")
                clean_x_data(args.profile, args.verbose, status)
            status.stop()
        log("Cleaning completed.", args.verbose, log_caller_file="idea.py")
        
        if not (args.generate_titles or args.generate_scripts or args.tokens):
            return

    if args.generate_titles:
        with Status(f"[white]Generating content titles for profile '{args.profile}' from {', '.join(args.platforms).upper()} ...[/white]", spinner="dots", console=console) as status:
            titles = generate_content_titles(
                profile_name=args.profile,
                status=status,
                verbose=args.verbose,
            )
            status.stop()

            if titles:
                console.print("\n[bold green]--- Generated Content Titles ---[/bold green]")
                console.print(titles)
                console.print("[bold green]----------------------------------[/bold green]")

                titles_output_dir = get_titles_output_dir(args.profile)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(titles_output_dir, f"generated_titles_{timestamp}.json")
                try:
                    cleaned_titles_string = titles.replace("```json", "").replace("```", "").strip()
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(json.loads(cleaned_titles_string), f, indent=2, ensure_ascii=False)
                    log(f"Generated titles saved to {output_file}", args.verbose, log_caller_file="idea.py")
                except Exception as e:
                    log(f"Error saving generated titles to {output_file}: {e}", args.verbose, is_error=True, log_caller_file="idea.py")
            else:
                log("No content titles generated.", args.verbose, is_error=True, log_caller_file="idea.py")
                
    elif args.generate_scripts:
        titles_output_dir = get_titles_output_dir(args.profile)
        latest_titles_file = get_latest_dated_json_file(directory=titles_output_dir, prefix="generated_titles_")

        if not latest_titles_file or not os.path.exists(latest_titles_file):
            log(f"Error: No latest generated titles file found for profile '{args.profile}' in {titles_output_dir}. Please generate titles first.", is_error=True, log_caller_file="idea.py")
            return

        log(f"Loading latest generated titles from {latest_titles_file}", args.verbose, log_caller_file="idea.py")
        try:
            with open(latest_titles_file, 'r', encoding='utf-8') as f:
                generated_titles_data = json.load(f)
            all_ideas = generated_titles_data.get("ideas", [])
        except json.JSONDecodeError:
            log(f"Error: Invalid JSON in generated titles file at '{latest_titles_file}'.", is_error=True, log_caller_file="idea.py")
            return
        
        selected_ideas = [idea for idea in all_ideas if idea.get("approved") == True]

        if not selected_ideas:
            log(f"No approved ideas found in {latest_titles_file}. Please set \"approved\": true for ideas you want to generate scripts for.", is_error=True, log_caller_file="idea.py")
            return

        with Status(f"[white]Generating scripts for {len(selected_ideas)} selected ideas for profile '{args.profile}' ...[/white]", spinner="dots", console=console) as status:
            scripts = generate_video_scripts(profile_name=args.profile, selected_ideas=selected_ideas, api_key=args.api_key, status=status, verbose=args.verbose)
            status.stop()

            if scripts:
                console.print("\n[bold green]--- Generated Video Scripts ---[/bold green]")
                for script_item in scripts:
                    console.print(json.dumps(script_item, indent=2, ensure_ascii=False))
                console.print("[bold green]----------------------------------[/bold green]")
                
                scripts_output_dir = get_scripts_output_dir(args.profile)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(scripts_output_dir, f"generated_scripts_{timestamp}.json")
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(scripts, f, indent=2, ensure_ascii=False)
                    log(f"Generated scripts saved to {output_file}", args.verbose, log_caller_file="idea.py")
                except Exception as e:
                    log(f"Error saving generated scripts to {output_file}: {e}", args.verbose, is_error=True, log_caller_file="idea.py")
            else:
                log("No video scripts generated.", args.verbose, is_error=True, log_caller_file="idea.py")
    elif not args.tokens:
        log("No action specified. Use --generate-titles to generate titles, --generate-scripts to generate scripts, or --tokens to calculate tokens.", is_error=True, log_caller_file="idea.py")
        parser.print_help()

if __name__ == "__main__":
    main()
