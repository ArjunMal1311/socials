import os
import re
import time
import base64
import mimetypes
import google.generativeai as genai

from rich.console import Console
from typing import Optional, List, Union

from services.support.api_key_pool import APIKeyPool
from services.support.rate_limiter import RateLimiter
from services.support.logger_util import _log as log
from services.support.api_call_tracker import APICallTracker

console = Console()

def create_inline_media_data(media_path: str, verbose: bool = False, status=None) -> Optional[dict]:
    """
    Create inline media data structure for Gemini API calls.
    Compatible with content_generator.py media handling.
    """
    try:
        mime_type = mimetypes.guess_type(media_path)[0] or "application/octet-stream"
        if not mime_type.startswith('image/'):
            log(f"Skipping non-image media: {media_path} (mime_type: {mime_type})", verbose, status, log_caller_file="gemini_util.py")
            return None

        with open(media_path, 'rb') as f:
            data_b64 = base64.b64encode(f.read()).decode('utf-8')

        return {
            "inline_data": {
                "mime_type": mime_type,
                "data": data_b64
            }
        }
    except Exception as e:
        log(f"Could not process media {media_path}: {e}", verbose, is_error=True, status=status, log_caller_file="gemini_util.py")
        return None

def generate_gemini_with_inline_media(
    prompt_parts: List[Union[str, dict]],
    api_key_pool: APIKeyPool,
    api_call_tracker: APICallTracker,
    rate_limiter: RateLimiter,
    model_name: str = 'gemini-2.5-flash-lite',
    status=None,
    verbose: bool = False
) -> tuple[Optional[str], Optional[int]]:
    """
    Universal Gemini generation function that supports inline media and complex prompt structures.
    Compatible with content_generator.py usage.
    """
    current_api_key = None
    token_count = None

    try:
        current_api_key = api_key_pool.get_key()
        if not current_api_key:
            log("No API key available in the pool.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
            return None, None

        api_key_suffix = current_api_key[-4:]

        can_call, reason = api_call_tracker.can_make_call("gemini", "generate_content", model_name, api_key_suffix)
        if not can_call:
            api_info = api_call_tracker.get_quot_info("gemini", "generate_content", model_name, api_key_suffix)
            log(f"API call blocked: {reason}", verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
            api_key_pool.report_failure(current_api_key, reason)
            return None, None

        rate_limiter.wait_if_needed(current_api_key)
        genai.configure(api_key=current_api_key)
        model = genai.GenerativeModel(model_name)

        message = f"[Gemini] Generating content with inline media using prompt parts"
        log(message, verbose, status, log_caller_file="gemini_util.py")

        response = model.generate_content(prompt_parts)

        try:
            result = response.text.strip()
            api_call_tracker.record_call("gemini", "generate_content", model_name, api_key_suffix, True, result[:100])
            return result, token_count
        except ValueError:
            api_info = api_call_tracker.get_quot_info("gemini", "generate_content", model_name, api_key_suffix)
            log(f"Gemini Response (no text): {response}", verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
            api_call_tracker.record_call("gemini", "generate_content", model_name, api_key_suffix, False, str(response))

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

            log(message, verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
            api_key_pool.report_failure(current_api_key, message)
            return None, None

    except Exception as e:
        error_message = f"An unexpected error occurred during Gemini generation: {e}"
        api_info = api_call_tracker.get_quot_info("gemini", "generate_content", model_name, api_key_suffix)
        log(error_message, verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
        api_call_tracker.record_call("gemini", "generate_content", model_name, api_key_suffix, False, error_message)
        api_key_pool.report_failure(current_api_key, error_message)
        return None, None


def generate_gemini(media_path: Optional[str], api_key_pool: APIKeyPool, api_call_tracker: APICallTracker, rate_limiter: RateLimiter, prompt_text: str, model_name: str = 'gemini-2.5-flash-lite', status=None, verbose: bool = False):
    current_api_key = None
    uploaded_file = None
    token_count = None
    try:
        current_api_key = api_key_pool.get_key()
        if not current_api_key:
            log("No API key available in the pool.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
            return None, None
        
        api_key_suffix = current_api_key[-4:]
        
        can_call, reason = api_call_tracker.can_make_call("gemini", "generate", model_name, api_key_suffix)
        if not can_call:
            api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
            log(f"API call blocked: {reason}", verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
            api_key_pool.report_failure(current_api_key, reason)
            return None, None

        rate_limiter.wait_if_needed(current_api_key)
        genai.configure(api_key=current_api_key)
        model = genai.GenerativeModel(model_name)

        if media_path:
            base_filename = os.path.basename(media_path)
            sanitized_display_name = re.sub(r'\s*\(.*?\)|\s*\[.*?\]', '', base_filename).strip()

            message = f"[Gemini] Uploading media: {media_path}"
            log(message, verbose, status, log_caller_file="gemini_util.py")
            uploaded_file = genai.upload_file(path=media_path, display_name=sanitized_display_name)
            
            timeout_seconds = 600
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                file_status = genai.get_file(uploaded_file.name)
                if file_status.state.name == "ACTIVE":
                    message = f"[Gemini] File {uploaded_file.display_name} ({file_status.name}) is now ACTIVE."
                    log(message, verbose, status, log_caller_file="gemini_util.py")
                    break
                elif file_status.state == "FAILED":
                    message = f"Gemini file upload failed for {uploaded_file.display_name} ({file_status.name})."
                    log(message, verbose, status, is_error=True, log_caller_file="gemini_util.py")
                    api_call_tracker.record_call("gemini", "upload", model_name, api_key_suffix, False, message)
                    return None, None
                message = f"[Gemini] Waiting for file {uploaded_file.display_name} ({file_status.state.name}) to become ACTIVE (current state: {file_status.state})... This can take several minutes for large videos."
                log(message, verbose, status, log_caller_file="gemini_util.py")
                time.sleep(5)
            else:
                message = f"Gemini file {uploaded_file.display_name} ({uploaded_file.name}) did not become ACTIVE within {timeout_seconds} seconds. Aborting content generation."
                log(message, verbose, status, is_error=True, log_caller_file="gemini_util.py")
                api_call_tracker.record_call("gemini", "upload", model_name, api_key_suffix, False, message)
                return None, None

        content = [prompt_text]
        if uploaded_file:
            content.append(uploaded_file)

        message = f"[Gemini] Generating content for {uploaded_file.display_name if uploaded_file else 'text-only'}"
        log(message, verbose, status, log_caller_file="gemini_util.py")
        response = model.generate_content(content)
        
        try:
            caption = response.text.strip().replace('\n', ' ')
            api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, True, response.text)
        except ValueError:
            api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
            log(f"Gemini Response (no text): {response}", verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
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
            
            log(message, verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
            api_key_pool.report_failure(current_api_key, message)
            return None, None

        message = f"[Gemini] Generated content for {uploaded_file.display_name if uploaded_file else 'text-only'}"
        log(message, verbose, status, log_caller_file="gemini_util.py")

        return caption, token_count
    except Exception as e:
        error_message = f"An unexpected error occurred during Gemini generation: {e}"
        api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
        log(error_message, verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
        api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, False, error_message)
        api_key_pool.report_failure(current_api_key, error_message)
        return None, None
    finally:
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
                message = f"[Gemini] Deleted uploaded file: {uploaded_file.display_name}"
                log(message, verbose, status, log_caller_file="gemini_util.py")
                    
            except Exception as e:
                if "PermissionDenied" in str(type(e)):
                    message = f"PermissionDenied error when deleting uploaded file {uploaded_file.display_name}: {e}. Skipping deletion."
                    log(message, verbose, status, is_error=True, log_caller_file="gemini_util.py")
                else:
                    message = f"An unexpected error occurred when deleting uploaded file {uploaded_file.display_name}: {e}. Skipping deletion."
                    log(message, verbose, status, is_error=True, log_caller_file="gemini_util.py")
