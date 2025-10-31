import re
import google.generativeai as genai

from datetime import datetime
from rich.console import Console
from typing import Optional, Dict, Any, List
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path

console = Console()
api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if status and (is_error or verbose):
        status.stop()

    if is_error:
        log_message = message
        if not verbose:
            match = re.search(r'(\d{3}\s+.*?)(?:\.|\n|$)', message)
            if match:
                log_message = f"Error: {match.group(1).strip()}"
            else:
                log_message = message.split('\n')[0].strip()
        
        quota_str = ""
        if api_info and "error" not in api_info:
            rpm_current = api_info.get('rpm_current', 'N/A')
            rpm_limit = api_info.get('rpm_limit', 'N/A')
            rpd_current = api_info.get('rpd_current', 'N/A')
            rpd_limit = api_info.get('rpd_limit', -1)
            quota_str = (
                f" (RPM: {rpm_current}/{rpm_limit}, "
                f"RPD: {rpd_current}/{rpd_limit if rpd_limit != -1 else 'N/A'})")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "bold red"
        console.print(f"[message_generator.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[message_generator.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def generate_linkedin_message(
    profile_data: Dict[str, Any],
    user_input_prompt: str,
    api_key: str,
    profile_name: str,
    rate_limiter: Any,
    verbose: bool = False,
    status=None,
    approved_messages: List[Dict[str, str]] = None
) -> str:
    model_name = 'gemini-2.0-flash-lite'

    try:
        rate_limiter.wait_if_needed(api_key)
        
        api_key_suffix = api_key[-4:] if api_key else None
        can_call, reason = api_call_tracker.can_make_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix)
        if not can_call:
            _log(f"[RATE LIMIT] Cannot call Gemini API: {reason}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
            return f"Error generating message: {reason}"

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        prompt_parts = []
        prompt_parts.append(f"You are an AI assistant tasked with crafting personalized LinkedIn direct messages. "
                            f"Your goal is to create an engaging and relevant message based on the recipient's LinkedIn profile information and a specific user prompt. "
                            f"The message should be professional, concise, and encourage a meaningful conversation or connection.\n\n")

        if approved_messages:
            prompt_parts.append(f"Here are some examples of previously approved LinkedIn direct messages that you can learn from for tone, style, and content. "
                                f"Do NOT directly copy these messages, but use them as inspiration to generate a new, unique message.\n\n")
            for i, msg in enumerate(approved_messages):
                prompt_parts.append(f"-- Approved Message Example {i+1} --\n")
                prompt_parts.append(f"Profile Name: {msg.get("profile_name", "N/A")}\n")
                prompt_parts.append(f"Job Title: {msg.get("profile_job_title", "N/A")}\n")
                prompt_parts.append(f"Message: {msg.get("generated_message", "")}\n\n")

        prompt_parts.append(f"-- Recipient's LinkedIn Profile Information --\n")
        prompt_parts.append(f"Name: {profile_data.get("name", "N/A")}\n")
        prompt_parts.append(f"Job Title: {profile_data.get("job_title", "N/A")}\n")
        prompt_parts.append(f"Profile Text: {profile_data.get("profile_text", "")}\n\n")

        prompt_parts.append(f"-- User's Specific Prompt --\n")
        prompt_parts.append(f"{user_input_prompt}\n\n")
        
        prompt_parts.append("Important: Generate exactly ONE direct message. Do not provide multiple options or explanations. Make it professional and concise. Start directly with the message content.\n")
        prompt_parts.append("LinkedIn Direct Message:\n")

        status.update("Generating personalized LinkedIn message...")
        _log(f"[HITTING API] Calling Gemini API for LinkedIn message for {profile_name}", verbose, status, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
        response = model.generate_content(prompt_parts)
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=True, response=response.text[:100])
        return response.text.strip()
    except Exception as e:
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=False, response=e)
        _log(f"Error generating message: {str(e)}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
        return f"Error generating message: {str(e)}"
