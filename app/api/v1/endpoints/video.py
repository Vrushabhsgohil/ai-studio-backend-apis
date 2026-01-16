from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.generation import VideoGenerationRequest, VideoGenerationResponse
from app.services.orchestration_service import orchestrator
from app.services.ugc_orchestration_service import ugc_orchestrator
from app.services.video_tasks import process_video_task
from app.core.exceptions import AIStudioError
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/generate-promo-video", response_model=VideoGenerationResponse)
async def generate_promo_video(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    """
    Triggers promotional video generation.
    """
    logger.info("Received request for promo video generation")
    try:
        video_id, image_b64 = orchestrator.initiate_video_generation(
            video_type="promo",
            user_content=request.content,
            reference_image_b64=request.reference_image_b64,
            reference_image_url=str(request.reference_image_url) if request.reference_image_url else None,
            user_id=request.user_id,
            voice_over=request.voice_over,
            promo_vibe="luxurious"
        )
        
        # Add background task for the orchestration flow
        background_tasks.add_task(
            process_video_task,
            video_type="promo",
            video_db_id=video_id,
            user_content=request.content,
            reference_image_b64=image_b64,
            voice_over=request.voice_over,
            promo_vibe="luxurious"
        )
        
        return VideoGenerationResponse(job_id=video_id, status="pending")

    except AIStudioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in promo video generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/generate-fashion-video", response_model=VideoGenerationResponse)
async def generate_fashion_video(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    """
    Triggers fashion video generation.
    """
    logger.info("Received request for fashion video generation")
    try:
        video_id, image_b64 = orchestrator.initiate_video_generation(
            video_type="fashion",
            user_content=request.content,
            reference_image_b64=request.reference_image_b64,
            reference_image_url=str(request.reference_image_url) if request.reference_image_url else None,
            user_id=request.user_id,
            voice_over=request.voice_over,
            promo_vibe="stylish"
        )
        
        # Add background task for the orchestration flow
        background_tasks.add_task(
            process_video_task,
            video_type="fashion",
            video_db_id=video_id,
            user_content=request.content,
            reference_image_b64=image_b64,
            voice_over=request.voice_over,
            promo_vibe="stylish"
        )
        
        return VideoGenerationResponse(job_id=video_id, status="pending")

    except AIStudioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in fashion video generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/generate-ugc-video", response_model=VideoGenerationResponse)
async def generate_ugc_video(request: VideoGenerationRequest, background_tasks: BackgroundTasks):
    """
    Triggers high-accuracy UGC video generation using the new orchestration layer.
    """
    logger.info("Received request for UGC video generation")
    try:
        # Use ugc_orchestrator for initiation
        video_id, image_b64 = ugc_orchestrator.initiate_video_generation(
            video_type="ugc",
            user_content=request.content,
            reference_image_b64=request.reference_image_b64,
            reference_image_url=str(request.reference_image_url) if request.reference_image_url else None,
            user_id=request.user_id,
            voice_over=request.voice_over,
            promo_vibe="natural"
        )
        
        # Add background task for the UGC orchestration flow
        background_tasks.add_task(
            process_video_task,
            video_type="ugc",
            video_db_id=video_id,
            user_content=request.content,
            reference_image_b64=image_b64,
            voice_over=request.voice_over,
            promo_vibe="natural"
        )
        
        return VideoGenerationResponse(job_id=video_id, status="pending")

    except AIStudioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in UGC video generation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/status/{job_id}")
async def get_video_status(job_id: str):
    """
    Polls the status of a video generation job.
    """
    from app.services.database_service import db_service
    record = db_service.get_record_by_id("video_assets", job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return record

@router.get("/download/{job_id}")
async def download_video(job_id: str):
    """
    Returns the stored video file for a specific job ID.
    """
    import os
    from fastapi.responses import FileResponse
    
    file_path = os.path.join("outputs", "videos", f"{job_id}.mp4")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found locally")
    
    return FileResponse(file_path, media_type="video/mp4", filename=f"{job_id}.mp4")
