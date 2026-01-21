import requests
import time
import logging
import base64
import io
import json
import re
from typing import Optional, Any, Dict
from PIL import Image
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def download_image(url: str, timeout: int = 30, retries: int = 3) -> bytes:
    """
    Downloads an image from a URL with robust error handling, retries, and headers.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    }
    
    logger.info(f"Attempting to download image from: {url}")
    
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download image from {url}: {str(e)}")
        raise e

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Extracts a JSON object from a string, handling markdown fences and balanced nested braces.
    """
    # 1. Try finding JSON within code blocks first, but use balanced brace matching
    code_block_match = re.search(r'```(?:json)?\s*', text, re.IGNORECASE)
    if code_block_match:
        start_from = code_block_match.end()
        # Find first '{' after the code block start
        start_index = text.find('{', start_from)
        if start_index != -1:
            json_str = _extract_balanced_json(text, start_index)
            if json_str:
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

    # 2. Try finding JSON anywhere in the text
    start_index = text.find('{')
    if start_index != -1:
        json_str = _extract_balanced_json(text, start_index)
        if json_str:
            try:
                return json.loads(json_str)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse JSON from text: {text[:500]}...")
                raise ValidationError(f"Invalid JSON response from AI service: {str(e)}")
    
    # 3. Last ditch: try loading the whole string
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse JSON from text: {text[:500]}...")
        raise ValidationError(f"No valid JSON found in response: {str(e)}")

def _extract_balanced_json(text: str, start_index: int) -> Optional[str]:
    """Helper to extract a balanced JSON string starting from start_index."""
    brace_count = 0
    in_string = False
    escape = False
    
    for i in range(start_index, len(text)):
        char = text[i]
        
        if char == '"' and not escape:
            in_string = not in_string
        
        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return text[start_index:i + 1]
        
        if char == '\\':
            escape = not escape
        else:
            escape = False
            
    return None

def process_and_resize_image(image_data: str, target_size: tuple = (720, 1280)) -> bytes:
    """
    Decodes base64 image, resizes it to target size, and returns PNG bytes.
    """
    try:
        if "base64," in image_data:
            image_data = image_data.split("base64,")[1]
            
        # Fix padding
        missing_padding = len(image_data) % 4
        if missing_padding:
            image_data += '=' * (4 - missing_padding)
            
        image_bytes = base64.b64decode(image_data)
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.size != target_size:
            logger.info(f"Resizing image from {img.size} to {target_size}")
            img = img.resize(target_size, resample=Image.BICUBIC)
            
        output = io.BytesIO()
        img.save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        logger.error(f"Image processing error: {str(e)}")
        raise ValidationError(f"Failed to process image: {str(e)}")

def request_with_retry(method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
    """Wrapper for requests with simple retry logic."""
    for i in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            if i == max_retries - 1:
                raise e
            time.sleep(2 ** i)
    raise Exception("Request failed after retries")
