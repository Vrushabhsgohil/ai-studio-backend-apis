from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.logging import setup_logging
import logging

# Setup logging configuration
setup_logging()
logger = logging.getLogger(__name__)

def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION
    )

    allow_origins = ["*"] 
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    from app.core.exceptions import AIStudioError
    from fastapi.responses import JSONResponse
    from fastapi import Request

    @application.exception_handler(AIStudioError)
    async def ai_studio_exception_handler(request: Request, exc: AIStudioError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "error_code": exc.__class__.__name__},
        )
    
    return application

app = create_application()

@app.get("/", tags=["Root"])
async def root():
    """
    Default welcome message to AI Studio.
    """
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to AI Studio"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
