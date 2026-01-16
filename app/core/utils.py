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
    Extracts a JSON object from a string, handling markdown fences and potential prefix/suffix.
    """
    try:
        # Try finding JSON within code blocks
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        
        # Try finding JSON without code blocks
        match = re.search(r'(\{.*?\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
            
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse JSON from text: {text[:200]}...")
        raise ValidationError(f"Invalid JSON response from AI service: {str(e)}")

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
