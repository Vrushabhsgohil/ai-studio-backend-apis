
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Studio Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_VIDEO_MODEL: str = "sora-2"  
    OPENAI_VIDEO_SECONDS: int = 12
    OPENAI_VIDEO_SIZE: str = "720x1280"
    
    # Poll Settings
    POLL_MAX_MIN: int = 10
    POLL_INTERVAL_SEC: int = 5
    REQ_TIMEOUT: int = 60

    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY")
    
    FAL_KEY: str = os.getenv("FAL_KEY")
    REPLICATE_API_TOKEN: str = os.getenv("REPLICATE_API_TOKEN")
    SERVICE_TYPE: str = os.getenv("SERVICE_TYPE")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
