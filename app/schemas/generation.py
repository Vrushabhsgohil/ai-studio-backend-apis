from pydantic import BaseModel, HttpUrl, Field, model_validator
from typing import Optional, Any

class GenerationRequest(BaseModel):
    content: str = Field(..., description="The user content/prompt to be refined")
    image_link: HttpUrl = Field(..., description="URL of the reference image")
    user_id: Optional[str] = Field(None, description="ID of the user")

class GenerationResponse(BaseModel):
    job_id: str = Field(..., description="The ID of the generation job")
    status: str = Field("pending", description="The status of the generation job")

class VideoGenerationRequest(BaseModel):
    content: str = Field(..., description="The user content/prompt for the video")
    reference_image_url: Optional[HttpUrl] = Field(None, description="URL of the reference image")
    reference_image_b64: Optional[str] = Field(None, description="Base64 encoded reference image")
    voice_over: bool = Field(False, description="Whether to include voiceover in the video")
    user_id: Optional[str] = Field(None, description="ID of the user")
    
    @model_validator(mode='before')
    @classmethod
    def check_empty_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get('reference_image_url') == "":
                data['reference_image_url'] = None
            if data.get('reference_image_b64') == "":
                data['reference_image_b64'] = None
            if data.get('user_id') == "":
                data['user_id'] = None
        return data

class VideoGenerationResponse(BaseModel):
    job_id: str
    qa_score: Optional[float] = None
    qa_feedback: Optional[str] = None
    status: str = "queued"

class VideoRemixRequest(BaseModel):
    video_id: str = Field(..., description="The ID of the video to remix (OpenAI Job ID or DB ID)")
    prompt: str = Field(..., description="The new prompt to apply to the video")
    user_id: Optional[str] = Field(None, description="ID of the user")

    @model_validator(mode='before')
    @classmethod
    def check_empty_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get('user_id') == "":
                data['user_id'] = None
        return data

