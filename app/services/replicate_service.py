import requests
import logging
import json
from app.core.config import settings

logger = logging.getLogger(__name__)

class ReplicateService:
    def __init__(self):
        self.api_token = settings.REPLICATE_API_TOKEN
        self.url = "https://api.replicate.com/v1/predictions"
        self.version = "61ae0fde81fa61a6461554ea6bd15505a0cb5d9c8d3da3fc3a2737a745ade88b"
        if not self.api_token:
            logger.warning("REPLICATE_API_TOKEN is not set in configuration")

    def generate_image(self, prompt: str, image_url: str):
        """
        Generates an image based on the prompt and input image url using Replicate.
        """
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN is not configured")

        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'Prefer': 'wait'
        }

        payload = {
            "version": self.version,
            "input": {
                "seed": 888,
                "prompt": prompt,
                "guidance": 1.05,
                "image_size": 1024,
                "speed_mode": "Lightly Juiced 🍊 (more consistent)",
                "aspect_ratio": "match_input_image",
                "img_cond_path": image_url,
                "output_format": "jpg",
                "output_quality": 80,
                "num_inference_steps": 40
            }
        }

        logger.info(f"Sending request to Replicate with prompt: {prompt[:50]}...")
        
        try:
            response = requests.post(
                self.url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # For 'Prefer: wait', Replicate returns the prediction object.
            # The output is usually in 'output' field.
            output = result.get("output")
            
            if not output:
                logger.error(f"No output in Replicate response: {result}")
                # Sometimes it might still be in progress if Wait didn't finish
                status = result.get("status")
                if status in ["starting", "processing"]:
                    logger.info("Replicate prediction still processing despite Prefer: wait")
                    # In a real scenario, we might want to poll here, 
                    # but for now we follow the user's provided snippet logic.
                    # If the user wants polling, we can add it similar to FalAI.
                    # However, usually Replicate's synchronous wait handles it.
                return None

            # Replicate output can be a list of strings or a single string
            if isinstance(output, list) and len(output) > 0:
                return output[0]
            elif isinstance(output, str):
                return output
            
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Replicate request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Replicate response content: {e.response.text}")
            raise e

replicate_service = ReplicateService()
