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

def generate_gemini(prompt_text: Optional[str] = None, media_path: Optional[str] = None, prompt_parts: Optional[List[Union[str, dict]]] = None, api_key_pool: APIKeyPool = None, api_call_tracker: APICallTracker = None, rate_limiter: RateLimiter = None, model_name: str = 'gemini-2.5-flash-lite', status=None, verbose: bool = False, max_retries: int = 3) -> tuple[Optional[str], Optional[int]]:
    if not (prompt_text or prompt_parts):
        log("Error: Either prompt_text or prompt_parts must be provided.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
        return None, None

    for attempt in range(max_retries):
        current_api_key = None
        uploaded_file = None
        token_count = None
        
        try:
            current_api_key = api_key_pool.get_key() if api_key_pool else None
            if not current_api_key:
                current_api_key = os.getenv('GEMINI_API', '').split(',')[0].strip()
            
            if not current_api_key:
                log("No API key available.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
                return None, None

            api_key_suffix = current_api_key[-4:]
            
            if api_call_tracker:
                can_call, reason = api_call_tracker.can_make_call("gemini", "generate", model_name, api_key_suffix)
                if not can_call:
                    api_info = api_call_tracker.get_quot_info("gemini", "generate", model_name, api_key_suffix)
                    log(f"API call blocked: {reason}", verbose, status, is_error=True, api_info=api_info, log_caller_file="gemini_util.py")
                    if api_key_pool: api_key_pool.report_failure(current_api_key, reason)
                    if attempt < max_retries - 1: continue
                    return None, None

            if rate_limiter:
                rate_limiter.wait_if_needed(current_api_key)

            genai.configure(api_key=current_api_key)
            model = genai.GenerativeModel(model_name)

            if media_path:
                mime_type = mimetypes.guess_type(media_path)[0] or ""
                if "video" in mime_type:
                    base_filename = os.path.basename(media_path)
                    sanitized_display_name = re.sub(r'\s*\(.*?\)|\s*\[.*?\]', '', base_filename).strip()

                    log(f"[Gemini] Uploading video: {media_path}", verbose, status, log_caller_file="gemini_util.py")
                    uploaded_file = genai.upload_file(path=media_path, display_name=sanitized_display_name)
                    
                    timeout_seconds = 600
                    start_time = time.time()
                    while time.time() - start_time < timeout_seconds:
                        file_status = genai.get_file(uploaded_file.name)
                        if file_status.state.name == "ACTIVE":
                            log(f"[Gemini] File {uploaded_file.display_name} is now ACTIVE.", verbose, status, log_caller_file="gemini_util.py")
                            break
                        elif file_status.state.name == "FAILED":
                            log(f"Gemini file upload failed for {uploaded_file.display_name}.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
                            if api_call_tracker: api_call_tracker.record_call("gemini", "upload", model_name, api_key_suffix, False, "Upload failed")
                            if uploaded_file: genai.delete_file(uploaded_file.name)
                            if attempt < max_retries - 1: break
                            return None, None
                        time.sleep(5)
                    else:
                        log(f"Gemini file upload timed out for {uploaded_file.display_name}.", verbose, status, is_error=True, log_caller_file="gemini_util.py")
                        if uploaded_file: genai.delete_file(uploaded_file.name)
                        if attempt < max_retries - 1: continue 
                        return None, None
                else:
                    inline_data = create_inline_media_data(media_path, verbose, status)
                    if inline_data:
                        if prompt_parts is None:
                            prompt_parts = [inline_data]
                        else:
                            prompt_parts.append(inline_data)

            content_to_send = []
            if prompt_parts:
                content_to_send.extend(prompt_parts)
            if prompt_text:
                content_to_send.append(prompt_text)
            if uploaded_file:
                content_to_send.append(uploaded_file)

            log(f"[Gemini] Generating content (Attempt {attempt+1}/{max_retries})", verbose, status, log_caller_file="gemini_util.py")
            response = model.generate_content(content_to_send)
            
            try:
                result_text = response.text.strip().replace('\n', ' ')
                if api_call_tracker:
                    api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, True, response.text[:100])
                if uploaded_file:
                    genai.delete_file(uploaded_file.name)
                return result_text, token_count
            except ValueError:
                message = "Gemini generation failed: No text in response."
                if response.candidates:
                    candidate = response.candidates[0]
                    if candidate.finish_reason:
                        message = f"Gemini generation failed: Finish reason - {candidate.finish_reason.name}."
                
                log(message, verbose, status, is_error=True, log_caller_file="gemini_util.py")
                if api_call_tracker: api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, False, message)
                if api_key_pool: api_key_pool.report_failure(current_api_key, message)
                if uploaded_file: genai.delete_file(uploaded_file.name)
                if attempt < max_retries - 1: continue
                return None, None
        
        except Exception as e:
            error_message = str(e)
            is_rate_limit = any(x in error_message.lower() for x in ["429", "quota", "exhausted", "too many requests"])
            
            log(f"Error (Attempt {attempt+1}): {error_message}", verbose, status, is_error=True, log_caller_file="gemini_util.py")
            
            if current_api_key:
                if api_call_tracker: api_call_tracker.record_call("gemini", "generate", model_name, api_key_suffix, False, error_message)
                if api_key_pool: api_key_pool.report_failure(current_api_key, error_message)

            if uploaded_file:
                try: genai.delete_file(uploaded_file.name)
                except: pass

            if is_rate_limit and attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None, None

    return None, None
