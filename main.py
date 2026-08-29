import uvicorn
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.constants import (
    DOCS_URL,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_HEALTHY,
    OPENAPI_URL,
    REDOC_URL,
)
from app.utils.logger import logger
from app.routes.agent import router as agent_router
from app.routes.ui import router as ui_router
from app.routes.portfolio import router as portfolio_router
from app.routes.crm import router as crm_router
from app.db.session import init_db, ping_db
from datetime import datetime
from pathlib import Path
import sys

def create_app() -> FastAPI:
    """
    Application factory for Wealth Management Assistant.
    Creates and configures the FastAPI application instance.
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        debug=settings.DEBUG,
        docs_url=DOCS_URL,
        redoc_url=REDOC_URL,
        openapi_url=OPENAPI_URL,
    )

    # Ensure the MySQL memory tables exist on startup (idempotent).
    # The app still starts if the DB is unreachable so non-memory endpoints
    # remain available; memory operations will log errors until it recovers.
    @app.on_event("startup")
    async def _init_memory_db() -> None:
        try:
            init_db()
            logger.info("Memory database initialised (PostgreSQL).")
        except Exception as e:
            logger.error(f"Memory database init failed: {e}")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", tags=["System"], status_code=status.HTTP_200_OK)
    async def health_check():
        """
        Comprehensive health check endpoint.
        Verifies all critical systems are operational.
        
        Returns:
            Detailed health status
        """
        db_ok = ping_db()
        health_status = {
            "status": HEALTH_STATUS_HEALTHY,
            "timestamp": datetime.now().isoformat(),
            "version": settings.VERSION,
            "checks": {
                "api": "ok",
                "llm_configured": "ok" if settings.UNIQUE_APP_KEY else "warning",
                "memory_system": "ok" if db_ok else "error - PostgreSQL unreachable",
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            }
        }
        
        if not settings.UNIQUE_APP_KEY:
            health_status["checks"]["llm_configured"] = "warning - UNIQUE_APP_KEY not set"
            health_status["status"] = HEALTH_STATUS_DEGRADED

        # Memory DB is critical — mark unhealthy if it cannot be reached.
        if not db_ok:
            health_status["status"] = HEALTH_STATUS_DEGRADED
        
        return health_status

    # Mount static assets
    static_dir = Path(__file__).resolve().parent / "app" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Include API routers
    app.include_router(agent_router, prefix=settings.API_V1_STR)
    app.include_router(portfolio_router, prefix=settings.API_V1_STR)
    app.include_router(crm_router, prefix=settings.API_V1_STR)
    app.include_router(ui_router)  # Serves the chat UI at "/"

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler for unhandled errors."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred. Please try again later."}
        )

    return app

# Create application instance
app = create_app()

def run_server():
    """
    Main entry point to run the FastAPI application.
    Host "0.0.0.0" allows access via IP address from other machines on the network.
    """
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    logger.info("Access the application via:")
    logger.info(f"  - http://localhost:{settings.PORT}")
    logger.info(f"  - http://{settings.HOST}:{settings.PORT}")
    logger.info(f"  - http://<your-ip-address>:{settings.PORT}")

    if not settings.UNIQUE_APP_KEY:
        logger.warning("UNIQUE_APP_KEY not set! LLM functionality will not work.")
    else:
        logger.info(f"Unique AI configured: {settings.UNIQUE_MODEL_NAME}")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )

if __name__ == "__main__":
    run_server()


