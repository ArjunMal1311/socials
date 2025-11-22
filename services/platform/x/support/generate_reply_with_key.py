import re
import os
import base64
import mimetypes
import google.generativeai as genai

from datetime import datetime
from rich.console import Console
from typing import Optional, Dict, Any
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
        console.print(f"[generate_reply_with_key.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[generate_reply_with_key.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def generate_reply_with_key(args, status=None, verbose: bool = False):
    tweet_text, media_urls, profile_name, api_key, rate_limiter, custom_prompt, tweet_id, all_replies = args
    
    model_name = 'gemini-2.5-flash-lite'

    try:
        rate_limiter.wait_if_needed(api_key)
        
        api_key_suffix = api_key[-4:] if api_key else None
        can_call, reason = api_call_tracker.can_make_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix)
        if not can_call:
            _log(f"[RATE LIMIT] Cannot call Gemini API: {reason}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
            return f"Error generating reply: {reason}"

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)        
        replies = all_replies
        sample_section = ''
        if replies:
            approved_examples = []
            for r in replies:
                if r.get('approved') and r.get('reply') and r.get('tweet_text'):
                    approved_examples.append(f"Original Tweet: {r['tweet_text']}\nApproved Reply: {r['reply']}")

            if approved_examples:
                sample_section = 'Sample approved tweet-reply pairs:\n' + '\n---\n'.join(approved_examples) + '\n\n'

        prompt_parts = []
        prompt_parts.append(custom_prompt)
        prompt_parts.append("This is sample section of approved replies to similar tweets:\n")
        prompt_parts.append(sample_section)

        prompt_parts.append(f"Tweet Text: {tweet_text}\n")

        if prompt_parts and isinstance(prompt_parts[-1], str) and prompt_parts[-1].strip() == "":
            prompt_parts.pop()

        if media_urls:
            status.update("Preparing media for tweet...")
            for medi_item in media_urls:
                local_file_path = medi_item
                try:
                    mime_type = mimetypes.guess_type(local_file_path)[0] or "application/octet-stream"
                    if not mime_type.startswith(('image/', 'video/')):
                        _log(f"Skipping unsupported media type {mime_type} for {local_file_path}", verbose, status, is_error=False)
                        continue
                    with open(local_file_path, 'rb') as f:
                        data_b64 = base64.b64encode(f.read()).decode('utf-8')
                    prompt_parts.append({
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": data_b64
                        }
                    })
                    prompt_parts.append("\n")
                    _log(f"Inlined media {os.path.basename(local_file_path)} (MIME: {mime_type}) for tweet {tweet_id} using API key ending in {api_key[-4:]}", verbose, status, is_error=False)
                except Exception as e:
                    _log(f"Could not process media item {medi_item}: {e}", verbose, status, is_error=False)

        prompt_parts.append("Important: Generate exactly ONE reply. Do not provide multiple options or explanations take inspiration from sample_section to my writing style.\n")
        prompt_parts.append("Just write a single direct reply that matches the prompt requirements.\n")
        prompt_parts.append("Reply:\n")

        status.update("Generating reply for tweet...")
        _log(f"[HITTING API] Calling Gemini API for tweet {tweet_id} using API key ending in {api_key[-4:]}", verbose, status, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
        response = model.generate_content(prompt_parts)
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=True, response=response.text[:100])
        return response.text.strip()
    except Exception as e:
        api_call_tracker.record_call("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix, success=False, response=e)
        _log(f"Error generating reply: {str(e)} for tweet {tweet_id} using API key ending in {api_key[-4:]}", verbose, status, is_error=True, api_info=api_call_tracker.get_quot_info("gemini", "generate_content", model=model_name, api_key_suffix=api_key_suffix))
        return f"Error generating reply: {str(e)}"