import json
import os
from typing import Dict, Any, List, Optional
from openai import OpenAI, OpenAIError
from app.services.base_service import BaseService
from app.core.exceptions import AIServiceError, ModerationError
from app.core.utils import request_with_retry

class OpenAIService(BaseService):
    """
    Service for interacting with OpenAI APIs (Chat, Video, Moderation).
    """
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=self.settings.OPENAI_API_KEY)
        self.api_key = self.settings.OPENAI_API_KEY

    def chat_completion(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: Optional[int] = None) -> str:
        """
        Simplified chat completion method.
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.log_error(f"OpenAI Chat Completion failed for model {model}", e)
            raise AIServiceError(f"OpenAI service error: {str(e)}")

    def vision_chat_completion(self, model: str, prompt: str, image_b64: Optional[str] = None, image_url: Optional[str] = None, max_tokens: int = 500) -> str:
        """
        Chat completion with vision support.
        """
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        if image_b64:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"}
            })
        elif image_url:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.log_error(f"OpenAI Vision Chat Completion failed for model {model}", e)
            raise AIServiceError(f"OpenAI vision service error: {str(e)}")

    def moderation_check(self, text: str) -> bool:
        """
        Checks if the text complies with OpenAI moderation policies.
        """
        url = "https://api.openai.com/v1/moderations"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"input": text}
        try:
            response = request_with_retry("POST", url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data["results"][0]["flagged"]
        except Exception as e:
            self.log_error("OpenAI Moderation check failed", e)
            return False

    def create_video_job(self, prompt: str, reference_image_bytes: Optional[bytes] = None, size: Optional[str] = None) -> str:
        """
        Creates a video generation job.
        """
        url = "https://api.openai.com/v1/videos"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        files = {
            "prompt": (None, prompt),
            "model": (None, self.settings.OPENAI_VIDEO_MODEL),
            "seconds": (None, str(self.settings.OPENAI_VIDEO_SECONDS)),
            "size": (None, size if size else self.settings.OPENAI_VIDEO_SIZE),
        }
        
        if reference_image_bytes:
            files["input_reference"] = ("reference.png", reference_image_bytes, "image/png")
            
        try:
            response = request_with_retry("POST", url, headers=headers, files=files, timeout=self.settings.REQ_TIMEOUT)
            if response.status_code >= 300:
                raise AIServiceError(f"OpenAI video creation failed: {response.text}")
            return response.json()["id"]
        except Exception as e:
            self.log_error("OpenAI Video Job Creation failed", e)
            raise AIServiceError(f"OpenAI video service error: {str(e)}")

    def remix_video_job(self, previous_video_id: str, prompt: str) -> str:
        """
        Remixes an existing video with a new prompt.
        """
        url = f"https://api.openai.com/v1/videos/{previous_video_id}/remix"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"prompt": prompt}
        
        try:
            response = request_with_retry("POST", url, headers=headers, json=payload, timeout=self.settings.REQ_TIMEOUT)
            if response.status_code >= 300:
                raise AIServiceError(f"OpenAI video remix failed: {response.text}")
            return response.json()["id"]
        except Exception as e:
            self.log_error(f"OpenAI Video Remix failed for job {previous_video_id}", e)
            raise AIServiceError(f"OpenAI video remix service error: {str(e)}")

    def get_video_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Retrieves the status of a video job.
        """
        url = f"https://api.openai.com/v1/videos/{job_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = request_with_retry("GET", url, headers=headers, timeout=self.settings.REQ_TIMEOUT)
            if response.status_code >= 300:
                raise AIServiceError(f"OpenAI video status check failed: {response.text}")
            return response.json()
        except Exception as e:
            self.log_error(f"OpenAI Video Status check failed for job {job_id}", e)
            raise AIServiceError(f"OpenAI video status check failed: {str(e)}")

    def download_video_content(self, job_id: str) -> bytes:
        """
        Downloads the raw video content from OpenAI.
        """
        url = f"https://api.openai.com/v1/videos/{job_id}/content"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            self.log_info(f"Downloading video content for job {job_id}")
            response = request_with_retry("GET", url, headers=headers, timeout=self.settings.REQ_TIMEOUT)
            if response.status_code >= 300:
                raise AIServiceError(f"OpenAI video download failed: {response.text}")
            return response.content
        except Exception as e:
            self.log_error(f"OpenAI Video Download failed for job {job_id}", e)
            raise AIServiceError(f"OpenAI video download failed: {str(e)}")

openai_service = OpenAIService()
