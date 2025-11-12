import os
import re
import time
import google.generativeai as genai

from datetime import datetime
from rich.console import Console
from typing import Optional, Any, Dict

from services.support.api_call_tracker import APICallTracker
from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter

console = Console()

def _log(message: str, verbose: bool, status=None, is_error: bool = False, api_info: Optional[Dict[str, Any]] = None):
    if is_error:
        if status:
            status.stop()
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
        console.print(f"[gemini_util.py] {timestamp}|[{color}]{log_message}{quota_str}[/{color}]")
    elif verbose:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = "white"
        console.print(f"[gemini_util.py] {timestamp}|[{color}]{message}[/{color}]")
        if status:
            status.start()
    elif status:
        status.update(message)

def generate_gemini(media_path: Optional[str], api_key_pool: APIKeyPool, api_call_tracker: APICallTracker, rate_limiter: RateLimiter, prompt_text: str, model_name: str = 'gemini-2.5-flash-lite', status=None, verbose: bool = False):
    current_api_key = None
    uploaded_file = None
    token_count = None
    try:
        current_api_key = api_key_pool.get_key()
        if not current_api_key:
            _log("No API key available in the pool.", verbose, status, is_error=True)
            return None, None
        
        api_key_suffix = current_api_key[-4:]
        
        can_call, reason = api_call_tracker.can_make_call("gemini", "generate", model_name, api_key_suffix)
        if not can_call:
            api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
            _log(f"API call blocked: {reason}", verbose, status, is_error=True, api_info=api_info)
            api_key_pool.report_failure(current_api_key, reason)
            return None, None

        rate_limiter.wait_if_needed(current_api_key)
        genai.configure(api_key=current_api_key)
        model = genai.GenerativeModel(model_name)

        if media_path:
            base_filename = os.path.basename(media_path)
            sanitized_display_name = re.sub(r'\s*\(.*?\)|\s*\[.*?\]', '', base_filename).strip()

            message = f"[Gemini] Uploading media: {media_path}"
            _log(message, verbose, status)
            uploaded_file = genai.upload_file(path=media_path, display_name=sanitized_display_name)
            
            timeout_seconds = 600
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                file_status = genai.get_file(uploaded_file.name)
                if file_status.state.name == "ACTIVE":
                    message = f"[Gemini] File {uploaded_file.display_name} ({file_status.name}) is now ACTIVE."
                    _log(message, verbose, status)
                    break
                elif file_status.state == "FAILED":
                    message = f"Gemini file upload failed for {uploaded_file.display_name} ({file_status.name})."
                    _log(message, verbose, status, is_error=True)
                    api_call_tracker.record_call("gemini", "upload", model_name, api_key_suffix, False, message)
                    return None, None
                message = f"[Gemini] Waiting for file {uploaded_file.display_name} ({file_status.state.name}) to become ACTIVE (current state: {file_status.state})... This can take several minutes for large videos."
                _log(message, verbose, status)
                time.sleep(5)
            else:
                message = f"Gemini file {uploaded_file.display_name} ({uploaded_file.name}) did not become ACTIVE within {timeout_seconds} seconds. Aborting content generation."
                _log(message, verbose, status, is_error=True)
                api_call_tracker.record_call("gemini", "upload", model_name, api_key_suffix, False, message)
                return None, None

        content = [prompt_text]
        if uploaded_file:
            content.append(uploaded_file)

        message = f"[Gemini] Generating content for {uploaded_file.display_name if uploaded_file else 'text-only'}"
        _log(message, verbose, status)
        response = model.generate_content(content)
        
        try:
            caption = response.text.strip().replace('\n', ' ')
            api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, True, response.text)
        except ValueError:
            api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
            _log(f"Gemini Response (no text): {response}", verbose, status, is_error=True, api_info=api_info)
            api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, False, str(response))
            if response.candidates:
                candidate = response.candidates[0]
                if candidate.finish_reason:
                    message = f"Gemini generation failed: Finish reason - {candidate.finish_reason.name}."
                    if candidate.safety_ratings:
                        message += " Safety ratings: " + ", ".join([f"{s.category.name}: {s.probability.name}" for s in candidate.safety_ratings])
                elif response.prompt_feedback and response.prompt_feedback.block_reason:
                    message = f"Gemini generation blocked by prompt feedback: {response.prompt_feedback.block_reason.name}."
                else:
                    message = "Gemini generation failed: No text in response and no clear finish reason."
            else:
                message = "Gemini generation failed: No text in response and no further details."
            
            _log(message, verbose, status, is_error=True, api_info=api_info)
            api_key_pool.report_failure(current_api_key, message)
            return None, None

        message = f"[Gemini] Generated content for {uploaded_file.display_name if uploaded_file else 'text-only'}"
        _log(message, verbose, status)

        return caption, token_count
    except Exception as e:
        error_message = f"An unexpected error occurred during Gemini generation: {e}"
        api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
        _log(error_message, verbose, status, is_error=True, api_info=api_info)
        api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, False, error_message)
        api_key_pool.report_failure(current_api_key, error_message)
        return None, None
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                message = f"[Gemini] Deleted uploaded file: {uploaded_file.display_name}"
                _log(message, verbose, status)
                    
            except Exception as e:
                if "PermissionDenied" in str(type(e)):
                    message = f"PermissionDenied error when deleting uploaded file {uploaded_file.display_name}: {e}. Skipping deletion."
                    _log(message, verbose, status, is_error=True)
                else:
                    message = f"An unexpected error occurred when deleting uploaded file {uploaded_file.display_name}: {e}. Skipping deletion."
                    _log(message, verbose, status, is_error=True)
