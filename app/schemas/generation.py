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
            # Treat empty strings or literal "string" as None
            for field in ['reference_image_url', 'reference_image_b64', 'user_id']:
                val = data.get(field)
                if val == "" or (isinstance(val, str) and val.lower() == "string"):
                    data[field] = None
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
            # user_id is optional, so we can set it to None
            user_id = data.get('user_id')
            if user_id == "" or (isinstance(user_id, str) and user_id.lower() == "string"):
                data['user_id'] = None
                
            # video_id is required, so if it's "string", we leave it 
            # so the service layer or pydantic provides a better error than "None is not allowed"
            video_id = data.get('video_id')
            if video_id == "":
                data['video_id'] = None # This will still trigger pydantic error, but that's expected for empty
        return data

