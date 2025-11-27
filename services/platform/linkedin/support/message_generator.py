import google.generativeai as genai

from rich.console import Console
from typing import Dict, Any, List
from services.support.logger_util import _log as log
from services.support.api_call_tracker import APICallTracker
from services.support.path_config import get_gemini_log_file_path

console = Console()
api_call_tracker = APICallTracker(log_file=get_gemini_log_file_path())


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
            log(f"[RATE LIMIT] Cannot call Gemini API: {reason}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="message_generator.py")
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
        log(f"[HITTING API] Calling Gemini API for LinkedIn message for {profile_name}", verbose, status, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="message_generator.py")
        response = model.generate_content(prompt_parts)
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=True, response=response.text[:100])
        return response.text.strip()
    except Exception as e:
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=False, response=e)
        log(f"Error generating message: {str(e)}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix), log_caller_file="message_generator.py")
        return f"Error generating message: {str(e)}"
