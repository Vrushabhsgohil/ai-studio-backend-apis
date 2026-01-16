from fastapi import APIRouter
from typing import Dict
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_model=Dict[str, str])
def welcome():
    """
    Default welcome message to AI Studio.
    """
    logger.info("General welcome endpoint accessed")
    return {"message": "Welcome to AI Studio"}
