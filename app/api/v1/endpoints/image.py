from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.generation import GenerationRequest, GenerationResponse
from app.services.orchestration_service import orchestrator
from app.services.video_tasks import process_image_task
from app.core.exceptions import AIStudioError
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/refine", response_model=GenerationResponse)
async def refine_user_content(request: GenerationRequest, background_tasks: BackgroundTasks):
    """
    Initiate image generation and refinement asynchronously.
    """
    logger.info("Received request for image generation initiation")
    try:
        # 1. Initiate generation (create pending entry)
        job_id = orchestrator.initiate_image_generation(
            user_content=request.content,
            reference_image_url=str(request.image_link),
            user_id=request.user_id
        )
        
        # 2. Trigger background task
        background_tasks.add_task(
            process_image_task,
            image_db_id=job_id,
            content=request.content,
            image_link=str(request.image_link)
        )
        
        return GenerationResponse(job_id=job_id, status="pending")

    except AIStudioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in image initiation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error processing request")
