import logging
from app.services.orchestration_service import orchestrator
from app.services.ugc_orchestration_service import ugc_orchestrator

logger = logging.getLogger(__name__)

def process_video_task(
    video_type: str,
    video_db_id: str,
    user_content: str,
    reference_image_b64: str,
    voice_over: bool,
    promo_vibe: str,
    dimensions: str = None,
    language: str = None
):
    """
    Background task to trigger the full orchestration flow.
    Defined as 'def' for thread-pool execution to avoid blocking the event loop on Windows.
    """
    logger.info(f"Starting background {video_type} task for {video_db_id}")
    
    try:
        if video_type == "fashion":
            orchestrator.run_fashion_orchestration_flow(
                video_db_id=video_db_id,
                user_content=user_content,
                reference_image_b64=reference_image_b64,
                voice_over=voice_over,
                promo_vibe=promo_vibe
            )
        elif video_type == "ugc":
             ugc_orchestrator.run_ugc_orchestration_flow(
                video_db_id=video_db_id,
                user_content=user_content,
                reference_image_b64=reference_image_b64,
                voice_over=voice_over,
                promo_vibe=promo_vibe
            )
        elif video_type == "general":
            orchestrator.run_general_orchestration_flow(
                video_db_id=video_db_id,
                user_content=user_content,
                reference_image_b64=reference_image_b64,
                dimensions=dimensions,
                language=language
            )
        else:
            orchestrator.run_promo_orchestration_flow(
                video_db_id=video_db_id,
                user_content=user_content,
                reference_image_b64=reference_image_b64,
                voice_over=voice_over,
                promo_vibe=promo_vibe
            )
            
    except Exception as e:
        logger.error(f"Error in background task for {video_db_id}: {str(e)}")
        from app.services.database_service import db_service
        db_service.update_record("video_assets", video_db_id, {"status": "failed","error_message": str(e)})

def process_image_task(
    image_db_id: str,
    content: str,
    image_link: str
):
    """
    Background task to trigger the full image orchestration flow.
    Defined as 'def' for thread-pool execution to avoid blocking the event loop on Windows.
    """
    logger.info(f"Starting background image task for {image_db_id}")
    try:
        orchestrator.run_image_orchestration_flow(
            image_db_id=image_db_id,
            content=content,
            image_link=image_link
        )
    except Exception as e:
        logger.error(f"Error in background image task for {image_db_id}: {str(e)}")
        from app.services.database_service import db_service
        db_service.update_record("image_assets", image_db_id, {"status": "failed", "error_message": str(e)})

def process_remix_task(
    video_db_id: str,
    original_job_id: str,
    prompt: str
):
    """
    Background task to trigger the video remix orchestration flow.
    """
    logger.info(f"Starting background remix task for {video_db_id}")
    try:
        orchestrator.run_remix_orchestration_flow(
            video_db_id=video_db_id,
            original_job_id=original_job_id,
            prompt=prompt
        )
    except Exception as e:
        logger.error(f"Error in background remix task for {video_db_id}: {str(e)}")
        from app.services.database_service import db_service
        db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})
