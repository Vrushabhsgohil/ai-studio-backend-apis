import asyncio
import io
from typing import Optional

import httpx
from app.schemas.generation import VideoGenerationRequest, VideoGenerationResponse, VideoRemixRequest
from app.services.freeflow_agents import AgentSystem
from app.services.orchestration_service import orchestrator
from app.services.ugc_orchestration_service import ugc_orchestrator
from app.services.video_tasks import process_video_task, process_remix_task
from app.core.exceptions import AIStudioError
from fastapi import BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi import APIRouter
import logging
from PIL import Image
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

OPENAI_API_KEY = settings.OPENAI_API_KEY
OPENAI_BASE_URL = "https://api.openai.com/v1"
HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
}

async def poll_video_job(video_id: str, timeout: int = 300):
    status_url = f"{OPENAI_BASE_URL}/videos/{video_id}"
    start_time = asyncio.get_event_loop().time()

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                resp = await client.get(status_url, headers=HEADERS)
                resp.raise_for_status()
            except httpx.ReadTimeout:
                logger.warning(f"[POLL WARNING] Request timed out, retrying...")
                await asyncio.sleep(2)
                continue
            except httpx.RequestError as e:
                logger.error(f"[POLL ERROR] Request failed: {e}")
                await asyncio.sleep(2)
                continue

            job = resp.json()
            status = job.get("status")

            logger.info(f"[VIDEO STATUS] {status}")

            if status == "completed":
                return
            if status == "failed":
                error_data = job.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                code = error_data.get("code", "N/A")
                print(f"[VIDEO FAILURE] Code: {code}, Message: {error_msg}")
                
                if code == "moderation_blocked":
                    raise Exception(f"Moderation BLocked : {error_msg}")
                
                raise Exception(f"Video generation failed: {error_msg}")

            if asyncio.get_event_loop().time() - start_time > timeout:
                raise Exception("Video generation timed out")

            await asyncio.sleep(5)

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

@router.post("/remix-video", response_model=VideoGenerationResponse)
async def remix_video(request: VideoRemixRequest, background_tasks: BackgroundTasks):
    """
    Triggers video remixing using an existing video (OpenAI Job ID).
    """
    logger.info(f"Received request for video remix for {request.video_id}")
    try:
        # Initiate DB record
        video_id = orchestrator.initiate_video_remix(
            video_id=request.video_id,
            prompt=request.prompt,
            user_id=request.user_id
        )
        
        # Add background task for the remix orchestration
        background_tasks.add_task(
            process_remix_task,
            video_db_id=video_id,
            original_job_id=request.video_id,
            prompt=request.prompt
        )
        
        return VideoGenerationResponse(job_id=video_id, status="pending")

    except AIStudioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in video remix: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/generate_video", response_model=VideoGenerationResponse)
async def generate_video(
    user_input: str = Form(...),
    dimensions: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    background_tasks: BackgroundTasks = BackgroundTasks()   
):
    try:
        logger.info("[REQUEST] Video generation request received")
        
        pil_image = None
        image_bytes = None
        image_b64 = None
        
        if image:
            logger.info(f"[IMAGE] Processing {image.filename}")
            raw_bytes = await image.read()
            pil_image = Image.open(io.BytesIO(raw_bytes))
            

            target_size = (720, 1280)
            if pil_image.size != target_size:
                logger.info(f"[IMAGE] Resizing from {pil_image.size} to {target_size}")
                pil_image = pil_image.resize(target_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            if pil_image.mode in ("RGBA", "P"):
                pil_image = pil_image.convert("RGB")
            pil_image.save(buffer, format="JPEG", quality=95)
            image_bytes = buffer.getvalue()
            
            # Convert to base64 string for orchestrator
            import base64
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        video_id, final_image_b64 = orchestrator.initiate_video_generation(
            video_type="general",
            user_content=user_input,
            reference_image_b64=image_b64,
            reference_image_url=None,
            user_id=user_id, 
            voice_over=False,
            promo_vibe="standard"
        )

        background_tasks.add_task(
            process_video_task,
            video_type="general",
            video_db_id=video_id,
            user_content=user_input,
            reference_image_b64=final_image_b64,
            voice_over=False,
            promo_vibe="standard",
            dimensions=dimensions,
            language=language
        )
        
        logger.info(f"[BACKGROUND] Added general video task for {video_id}")

        # 4. Return Pending Response
        return VideoGenerationResponse(
            job_id=video_id, 
            status="pending",
            final_prompt="Processing...",
            video_url="",
            local_path=""
        )

    except Exception as e:
        logger.exception("[SYSTEM ERROR]")


