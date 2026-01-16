import requests
import logging
import json
import time
from app.core.config import settings

logger = logging.getLogger(__name__)

class FalAIService:
    def __init__(self):
        self.api_key = settings.FAL_KEY
        self.base_url = "https://queue.fal.run/fal-ai/z-image/turbo/controlnet/lora"
        if not self.api_key:
            logger.warning("FAL_KEY is not set in configuration")

    def generate_image(self, prompt: str, image_url: str):
        """
        Generates an image based on the prompt and input image url using fal.ai z-image.
        """
        if not self.api_key:
            raise ValueError("FAL_KEY is not configured")

        headers = {
            "Authorization": f"Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # We append a strong instruction to the prompt to help the intent
        enhanced_prompt = f"{prompt} . Ensure product text is perfectly clear and unchanged."

        payload = {
            "prompt": enhanced_prompt,
            "image_url": image_url,
            "num_inference_steps": 12,
            "control_strength": 0.85, # Slightly lowered to allow scene transition
            "preprocessing_type": "canny",
            "image_size": "auto",
            "num_images": 1,
            "enable_safety_checker": True,
            "output_format": "png",
            "strength": 0.35, # Low strength = strict text preservation
            "guidance_scale": 0.0,
            "seed": 42
        }

        logger.info(f"Sending request to FalAI with prompt: {prompt[:50]}...")
        
        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            initial_response = response.json()
            
            status_url = initial_response.get("status_url")
            
            if not status_url:
                logger.error(f"No status_url in response: {initial_response}")
                return initial_response
            
            # Poll for completion
            max_retries = 30
            for i in range(max_retries):
                logger.info(f"Polling FalAI status... Attempt {i+1}/{max_retries}")
                status_res = requests.get(status_url, headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                status = status_data.get("status")
                if status == "COMPLETED":
                    response_url = initial_response.get("response_url")

                    final_res = requests.get(response_url, headers=headers)
                    final_res.raise_for_status()
                    final_data = final_res.json()
                    
                    images = final_data.get("images", [])
                    if images and len(images) > 0:
                        return images[0].get("url")
                    
                    logger.error("Completed but no images found")
                    return None
                    
                elif status == "IN_QUEUE" or status == "IN_PROGRESS":
                    time.sleep(1) # Wait 1 second before next poll
                    continue
                else:
                    logger.error(f"FalAI generation failed with status: {status}")
                    raise Exception(f"FalAI generation failed: {status}")
            
            raise TimeoutError("FalAI generation timed out")

        except requests.exceptions.RequestException as e:
            logger.error(f"FalAI request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"FalAI response content: {e.response.text}")
            raise e

fal_ai_service = FalAIService()