import subprocess
from typing import Dict, Any, List, Optional
from rich.console import Console
import shlex

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, end: str = '\n'):
    if is_error:
        if status:
            status.stop()
        log_message = message
        color = "bold red"
        console.print(f"[atg.py] [{color}]{log_message}[/{color}]", end=end)
    elif verbose:
        color = "white"
        console.print(f"[atg.py] [{color}]{message}[/{color}]", end=end)
        if status:
            status.start()
    elif status:
        status.update(message)
    else:
        color = "white"
        console.print(f"[atg.py] [{color}]{message}[/{color}]", end=end)

COMMAND_SCHEMAS = {
    "replies_action_review": {
        "script": "services/platform/x/replies.py",
        "main_action": "--action-review",
        "description": "Action Mode",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "online": {"type": "bool", "required": False, "default": False, "description": "Use online mode (with Google Sheets)."},
            "run_number": {"type": "int", "required": False, "description": "Run number for online mode."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "reply_max_tweets": {"type": "int", "required": False, "description": "Maximum tweets for reply action."},
            "action_port": {"type": "int", "required": False, "description": "Port for action mode."},
            "community_name": {"type": "str", "required": False, "description": "Name of the community."}
        }
    },
    "replies_action_generate": {
        "script": "services/platform/x/replies.py",
        "main_action": "--action-generate",
        "description": "Action Mode Generate",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "reply_max_tweets": {"type": "int", "required": False, "description": "Maximum tweets for reply action."},
            "action_port": {"type": "int", "required": False, "description": "Port for action mode."},
            "community_name": {"type": "str", "required": False, "description": "Name of the community."}
        }
    },
    "replies_post_action_approved": {
        "script": "services/platform/x/replies.py",
        "main_action": "--post-action-approved",
        "description": "Action Mode Post Replies",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "reply_max_tweets": {"type": "int", "required": False, "description": "Maximum tweets for reply action."},
            "action_port": {"type": "int", "required": False, "description": "Port for action mode."},
            "community_name": {"type": "str", "required": False, "description": "Name of the community."}
        }
    },
    "replies_eternity_review": {
        "script": "services/platform/x/replies.py",
        "main_action": "--eternity-review",
        "description": "Eternity Mode",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "eternity_browser": {"type": "str", "required": False, "description": "Browser profile for eternity mode."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "reply_max_tweets": {"type": "int", "required": False, "description": "Maximum tweets for reply action."},
            "port": {"type": "int", "required": False, "description": "Port for eternity mode."}
        }
    },
    "replies_clear_eternity": {
        "script": "services/platform/x/replies.py",
        "main_action": "--clear-eternity",
        "description": "Clears eternity mode data",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "port": {"type": "int", "required": False, "description": "Port for eternity mode."}
        }
    },
    "replies_post_approved_eternity": {
        "script": "services/platform/x/replies.py",
        "main_action": "--post-approved",
        "description": "Posts approved tweets in eternity mode",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "limit": {"type": "int", "required": False, "description": "Limit for approved posts."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "reply_max_tweets": {"type": "int", "required": False, "description": "Maximum tweets for reply action."},
            "port": {"type": "int", "required": False, "description": "Port for eternity mode."}
        }
    },
    "replies_community_scrape": {
        "script": "services/platform/x/replies.py",
        "main_action": "--community-scrape",
        "description": "Scrapes tweets from a specified X community.",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "community_name": {"type": "str", "required": True, "description": "Name of the X community to scrape from."},
            "browser_profile": {"type": "str", "required": False, "description": "Browser profile to use."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."}
        }
    },
    "replies_suggest_engaging_tweets": {
        "script": "services/platform/x/replies.py",
        "main_action": "--suggest-engaging-tweets",
        "description": "Analyzes community tweets to suggest engaging content.",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "community_name": {"type": "str", "required": True, "description": "Name of the X community to analyze."},
            "api_key": {"type": "str", "required": False, "description": "Gemini API key for analysis."},
            "ignore_video_tweets": {"type": "bool", "required": False, "default": False, "description": "Ignore tweets with videos."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."}
        }
    },
    "scheduler_process_tweets": {
        "script": "services/platform/x/scheduler.py",
        "main_action": "--process-tweets",
        "description": "Processes and schedules tweets.",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "sched_tom": {"type": "bool", "required": False, "default": False, "description": "Move tomorrow's tweets and schedule."},
            "no_headless": {"type": "bool", "required": False, "default": False, "description": "Disable headless browser mode."},
            "verbose": {"type": "bool", "required": False, "default": False, "description": "Enable detailed logging."}
        }
    },
    "scheduler_generate_sample": {
        "script": "services/platform/x/scheduler.py",
        "main_action": "--generate-sample",
        "description": "Generates sample tweets.",
        "parameters": {
            "profile": {"type": "str", "required": True, "description": "Profile name to use."},
            "min_gap_hours": {"type": "int", "required": False, "description": "Minimum gap in hours."},
            "min_gap_minutes": {"type": "int", "required": False, "description": "Minimum gap in minutes."},
            "max_gap_hours": {"type": "int", "required": False, "description": "Maximum gap in hours."},
            "max_gap_minutes": {"type": "int", "required": False, "description": "Maximum gap in minutes."},
            "fixed_gap_hours": {"type": "int", "required": False, "description": "Fixed gap in hours."},
            "fixed_gap_minutes": {"type": "int", "required": False, "description": "Fixed gap in minutes."},
            "tweet_text": {"type": "str", "required": False, "description": "Text for the tweet."},
            "start_image_number": {"type": "int", "required": False, "description": "Starting image number."},
            "num_days": {"type": "int", "required": False, "description": "Number of days to generate."},
            "start_date": {"type": "str", "required": False, "description": "Start date for generation (YYYY-MM-DD)."}
        }
    }
}

class CommandExecutor:
    def __init__(self, command_schemas: Dict[str, Any]):
        self.command_schemas = command_schemas

    def construct_command(self, parsed_intent: Dict[str, Any]) -> Optional[List[str]]:
        cmd_name = parsed_intent.get("command")
        params = parsed_intent.get("parameters", {})

        if cmd_name not in self.command_schemas:
            _log(f"Error: Unknown command '{cmd_name}'.", verbose=False, is_error=True)
            return None

        schema = self.command_schemas[cmd_name]
        script = schema["script"]
        main_action = schema["main_action"]

        python_args = [main_action]

        for param_name, param_info in schema["parameters"].items():
            if param_name in params:
                value = params[param_name]
                arg_name = f"--{param_name.replace('_', '-')}"
                if param_info["type"] == "bool":
                    if value:
                        python_args.append(arg_name)
                else:
                    python_args.append(arg_name)
                    value_str = str(value)
                    quoted_value = shlex.quote(value_str)
                    python_args.append(quoted_value)
            elif param_info["required"]:
                _log(f"Error: Required parameter '{param_name}' for command '{cmd_name}' is missing.", verbose=False, is_error=True)
                return None
        
        # Construct the full Python command string with proper quoting
        python_command_str = f"PYTHONPATH=. python {script} {' '.join(python_args)}"
        
        # Embed the Python command string into the bash -c command
        return [f"source venv/bin/activate && {python_command_str}"]

    def execute_command(self, command: List[str]):
        _log(f"Simulating execution: {' '.join(command)}", verbose=False)
        # For actual execution, uncomment the subprocess.run line below
        # try:
        #     subprocess.run(command, shell=True, check=True)
        #     _log("Command executed successfully! (Simulated)", verbose=False)
        # except subprocess.CalledProcessError as e:
        #     _log(f"Command failed with error: {e} (Simulated)", verbose=False, is_error=True)
        # except Exception as e:
        #     _log(f"An unexpected error occurred: {e} (Simulated)", verbose=False, is_error=True)
        _log("Command would have been executed above. User needs to copy and run it manually.", verbose=False)

class CLI_Agent:
    def __init__(self):
        self.executor = CommandExecutor(COMMAND_SCHEMAS)
        self.current_context = {}
        self.browser_login_advised = False

    def _get_user_command_choice(self) -> Optional[str]:
        _log("\nWhat would you like to do? Please choose a number:", verbose=False)
        commands = list(COMMAND_SCHEMAS.keys())
        for i, cmd_name in enumerate(commands):
            _log(f"{i+1}. {COMMAND_SCHEMAS[cmd_name]['description']}", verbose=False)
        _log(f"{len(commands)+1}. Show Help (list commands again)", verbose=False)
        _log(f"{len(commands)+2}. Exit", verbose=False)
        
        while True:
            choice = input("Enter your choice (number): ").strip()
            if choice.isdigit():
                choice_num = int(choice)
                if 1 <= choice_num <= len(commands):
                    return commands[choice_num - 1]
                elif choice_num == len(commands) + 1:
                    _log("\nHere are the commands I can help you with:", verbose=False)
                    for cmd_name, cmd_info in COMMAND_SCHEMAS.items():
                        _log(f"- {cmd_name}: {cmd_info['description']}", verbose=False)
                    _log("\nPlease choose a command from the list above.", verbose=False)
                    for i, cmd_name in enumerate(commands):
                        _log(f"{i+1}. {COMMAND_SCHEMAS[cmd_name]['description']}", verbose=False)
                    _log(f"{len(commands)+1}. Show Help (list commands again)", verbose=False)
                    _log(f"{len(commands)+2}. Exit", verbose=False)
                elif choice_num == len(commands) + 2:
                    _log("Goodbye!", verbose=False)
                    exit()
                else:
                    _log("Invalid choice. Please enter a number from the list.", verbose=False, is_error=True)
            else:
                _log("Invalid input. Please enter a number.", verbose=False, is_error=True)
    
    def _gather_parameters_interactively(self, command_name: str) -> Dict[str, Any]:
        schema = COMMAND_SCHEMAS[command_name]
        params = self.current_context.copy()

        _log(f"Okay, let's configure '{command_name}'.", verbose=False)

        for param_name, param_info in schema["parameters"].items():
            if param_info["required"]:
                while True:
                    current_value = params.get(param_name)
                    if current_value is not None:
                        _log(f"  {param_info['description']} (current: {current_value}): ", verbose=False, end='')
                    else:
                        _log(f"  {param_info['description']}: ", verbose=False, end='')
                    
                    user_input = input().strip()

                    if user_input:
                        if param_info["type"] == "int":
                            try:
                                params[param_name] = int(user_input)
                                break
                            except ValueError:
                                _log(f"Invalid input for {param_name}. Please enter a number.", verbose=False, is_error=True)
                        else:
                            params[param_name] = user_input
                            break
                    elif current_value is not None:
                        params[param_name] = current_value
                        break
                    else:
                        _log(f"Required parameter '{param_name}' cannot be empty. Please provide a value.", verbose=False, is_error=True)

        for param_name, param_info in schema["parameters"].items():
            if param_info["type"] == "bool" and not param_info["required"]:
                default_value = param_info.get("default", False)
                current_value = params.get(param_name, default_value)
                
                while True:
                    question = f"Do you want to {param_info['description'].lower().replace('.', '')}? (yes/no) [current_default: {'yes' if current_value else 'no'}]"
                    response = input(f"{question}: ").strip().lower()
                    if response == 'yes':
                        params[param_name] = True
                        break
                    elif response == 'no':
                        params[param_name] = False
                        break
                    elif not response:
                        params[param_name] = current_value
                        break
                    else:
                        _log(f"Invalid input '{response}'. Please enter 'yes' or 'no'. Using current/default: {'yes' if current_value else 'no'}.", verbose=False, is_error=True)

        for param_name, param_info in schema["parameters"].items():
            if not param_info["required"] and param_info["type"] != "bool":
                while True:
                    current_value = params.get(param_name)
                    if current_value is not None:
                        question = f"Do you want to change {param_info['description'].lower().replace('.', '')} (current: {current_value})? (yes/no) [default: no]"
                    else:
                        question = f"Do you want to provide a value for {param_info['description'].lower().replace('.', '')}? (yes/no) [default: no]"
                    
                    response = input(f"{question}: ").strip().lower()
                    
                    if response == 'yes':
                        while True:
                            _log(f"  Please provide value for {param_info['description'].lower().replace('.', '')}: ", verbose=False, end='')
                            user_input = input().strip()
                            if user_input:
                                if param_info["type"] == "int":
                                    try:
                                        params[param_name] = int(user_input)
                                        break
                                    except ValueError:
                                        _log(f"Invalid input for {param_name}. Please enter a number.", verbose=False, is_error=True)
                                else:
                                    params[param_name] = user_input
                                    break
                            else:
                                _log(f"Value for {param_name} cannot be empty. Please provide a value.", verbose=False, is_error=True)
                        break
                    elif response == 'no':
                        if param_name in params:
                            del params[param_name]
                        break
                    elif not response:
                        break
                    else:
                        _log(f"Invalid input '{response}'. Please enter 'yes' or 'no'. Skipping {param_name}.", verbose=False, is_error=True)

        if not self.browser_login_advised and any(p in ["replies_community_scrape", "scheduler_process_tweets"] for p in [command_name]):
            _log("For commands involving browser interaction (like scraping or processing tweets), you might need to run with '--no-headless' once to log in or join communities.", verbose=False)
            _log("Have you already logged in and joined the relevant communities? (yes/no): ", verbose=False)
            login_status = input().strip().lower()
            if login_status != 'yes':
                _log("Please ensure you're logged in and have joined communities for smooth operation. You can run with '--no-headless' to do this manually.", verbose=False)
            self.browser_login_advised = True
        
        return params

    def run(self):
        _log("Hello! I'm your X automation assistant. How can I help you today?", verbose=False)
        
        while True:
            self.current_context = {k:v for k,v in self.current_context.items() if k in ["profile", "browser_login_advised"]}

            chosen_command_name = self._get_user_command_choice()
            
            if not chosen_command_name:
                continue

            self.current_context.update(self._gather_parameters_interactively(chosen_command_name))
            
            command_schema = COMMAND_SCHEMAS.get(chosen_command_name)

            if command_schema:
                pass
            
            final_parsed_intent = {"command": chosen_command_name, "parameters": self.current_context}
            cli_command = self.executor.construct_command(final_parsed_intent)
            if cli_command:
                _log("I understand. Here's what I plan to do:", verbose=False)
                _log(f"  Command: {chosen_command_name}", verbose=False)
                for param, value in self.current_context.items():
                    _log(f"  - {param.replace('_', '-').capitalize()}: {value}", verbose=False)
                
                _log(f"  Full CLI command: {' '.join(cli_command)}", verbose=False)
                
                confirmation = input("Does this look correct? (yes/no): ").strip().lower()
                if confirmation == 'yes':
                    self.executor.execute_command(cli_command)
                else:
                    _log("Okay, I've cancelled the command. What would you like to do instead?", verbose=False)
            else:
                _log("I couldn't construct the command. Please check your input.", verbose=False)

if __name__ == "__main__":
    agent = CLI_Agent()
    agent.run()
