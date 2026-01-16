from fastapi import APIRouter
from app.api.v1.endpoints import general, image, video

api_router = APIRouter()

# General routes (e.g. welcome)
api_router.include_router(general.router, tags=["General"])

# Image/Refinement routes
api_router.include_router(image.router, prefix="/generation", tags=["Image"])

# Video Orchestration routes
api_router.include_router(video.router, prefix="/video", tags=["Video"])
