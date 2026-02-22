"""
Main FastAPI application for NeuroInsight.

This module initializes and configures the FastAPI application,
including middleware, routes, and lifecycle events.
"""

import asyncio
import threading
import time
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, APIRouter, Request, HTTPException, Query, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.api import cleanup_router, jobs_router, metrics_router, placeholder_router, reports_router, upload_router, visualizations_router
from pathlib import Path
from backend.core import get_settings, init_db, setup_logging
from backend.core.logging import get_logger
from backend.core.database import get_db

# Clear any cached settings and initialize fresh
from backend.core.config import get_settings
get_settings.cache_clear()  # Clear LRU cache

# Initialize settings (will be reloaded at runtime for environment variables)
settings = get_settings()
setup_logging(settings.log_level, settings.environment)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    global settings, logger

    # Reload settings at runtime (environment variables should now be set)
    settings = get_settings()
    setup_logging(settings.log_level, settings.environment)
    logger = get_logger(__name__)

    # Startup
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    # Initialize database
    try:
        init_db()
        logger.info("database_initialized")

        # Note: Automatic job processing moved to startup event for better async handling

    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        logger.warning("continuing_without_database_initialization")

    # Clean up temporary files from previous runs
    try:
        import shutil
        import os
        from pathlib import Path

        # Clean up temp directories older than 1 hour
        temp_base = Path(settings.data_dir) / "temp"
        if temp_base.exists():
            import time
            current_time = time.time()
            for temp_dir in temp_base.iterdir():
                if temp_dir.is_dir():
                    try:
                        # Check if directory is older than 1 hour
                        dir_mtime = temp_dir.stat().st_mtime
                        if current_time - dir_mtime > 3600:  # 1 hour
                            shutil.rmtree(temp_dir)
                            logger.info("cleanup_temp_directory", path=str(temp_dir))
                    except Exception as e:
                        logger.warning("temp_directory_cleanup_failed", path=str(temp_dir), error=str(e))

        logger.info("temp_file_cleanup_completed")
    except Exception as e:
        logger.warning("temp_file_cleanup_failed", error=str(e))
        # Don't raise - let the app start even if DB init fails


    # Special route for working version
    @app.get("/working")
    async def working_page():
        frontend_dir = Path(__file__).parent.parent / "frontend"
        working_file = frontend_dir / "index.dev.html"
        if not working_file.exists():
            working_file = frontend_dir / "index.html"
        if working_file.exists():
            return FileResponse(str(working_file), media_type="text/html")
        return JSONResponse({"error": "Working file not found"}, status_code=404)

    # Static files are now handled by custom route with caching headers
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        logger.info("static_files_enabled_with_caching", path=str(static_dir))

    # Mount static files for web frontend from dist directory
    # Mount outputs directory FIRST (before frontend to take precedence)
    outputs_dir = Path(settings.output_dir)
    if outputs_dir.exists():
        app.mount("/outputs", StaticFiles(directory=str(outputs_dir)), name="outputs")
        logger.info("outputs_static_files_enabled", path=str(outputs_dir))
    else:
        logger.warning("outputs_directory_not_found", path=str(outputs_dir))

    # Mount frontend static files (after outputs so /outputs takes precedence)
    if settings.environment == "production":
        # Serve from dist directory (contains index.dev.html for identical UI/UX)
        frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
        if frontend_dir.exists():
            index_file = frontend_dir / "index.html"
            if index_file.exists():
                logger.info("serving_production_frontend_from", path=str(index_file))
            app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
            logger.info("frontend_static_files_enabled", path=str(frontend_dir))
        else:
            logger.warning("frontend_directory_not_found", path=str(frontend_dir))

    yield


    logger.info("application_shutting_down")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Neuroimaging pipeline for hippocampal asymmetry analysis",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Automatic job processing is handled by the trigger_queue.py script
# Users should run: python3 trigger_queue.py
# after starting the application to begin processing pending jobs

# Direct API endpoints (must be defined immediately after app creation)
@app.get("/api/test-endpoint")
def test_endpoint():
    return {"message": "Test endpoint works"}

@app.delete("/api/jobs/delete/", status_code=204)
def delete_job(
    job_id: str = Query(..., description="Job ID"),
    db: Session = Depends(get_db),
):
    """
    Delete a job and its associated data.

    For RUNNING or PENDING jobs:
    - Cancels Celery task and terminates FreeSurfer processes
    - Marks job as CANCELLED before deletion
    - Waits briefly for graceful termination

    For COMPLETED or FAILED jobs:
    - Immediately deletes files and database records

    Args:
        job_id: Job identifier
        db: Database session dependency

    Raises:
        HTTPException: If job not found
    """
    from backend.services.job_service import JobService
    deleted = JobService.delete_job(db, job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

# Configure CORS
# If cors_origins_list contains "*", use allow_origin_regex to match all origins
cors_origins = settings.cors_origins_list
if cors_origins == ["*"]:
    # Allow all origins when "*" is specified
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",  # Match any origin
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Use specific origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Custom static file handler with caching headers
from starlette.responses import FileResponse

@app.api_route("/static/{path:path}", methods=["GET", "HEAD"])
async def serve_static_with_cache(path: str):
    """Serve static files with appropriate caching headers."""
    logger.info("serving_static_file_with_cache", path=path)
    static_dir = Path(__file__).parent.parent / "static"
    file_path = static_dir / path

    if not file_path.exists() or not file_path.is_file():
        logger.error("static_file_not_found", path=str(file_path))
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")

    # Static assets: cache for 1 year
    response = FileResponse(str(file_path))
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["Expires"] = "Thu, 31 Dec 2037 23:59:59 GMT"
    logger.info("static_file_served_with_cache", path=path, cache_control=response.headers.get("Cache-Control"))
    return response

# Add cache-control headers for HTML and API responses
@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    if not hasattr(response, "headers"):
        return response

    path = request.url.path

    # Never cache API responses so progress updates are always fresh.
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    # For the root HTML, prefer no-store unless explicitly set elsewhere.
    if path == "/" and "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Health check endpoint - supports both GET and HEAD methods for wait-on compatibility
@app.api_route("/health", methods=["GET", "HEAD"], tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Returns application status and version information.
    Supports both GET and HEAD methods for compatibility with health check libraries.
    """
    current_settings = get_settings()
    return {
        "status": "healthy",
        "app_name": current_settings.app_name,
        "version": current_settings.app_version,
        "environment": current_settings.environment,
    }


# Root endpoint - serves the React frontend
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - serves the React frontend for web deployment.
    """
    # Serve the React frontend directly based on environment
    from pathlib import Path
    if settings.environment == "production":
        frontend_path = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
    else:
        frontend_path = Path(__file__).parent.parent / "frontend" / "index.dev.html"

    if frontend_path.exists():
        with open(frontend_path, "r", encoding="utf-8") as f:
            content = f.read()
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            content=content,
            status_code=200,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"error": "Frontend not found", "path": str(frontend_path)}


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler.
    
    Catches unhandled exceptions and returns a standardized error response.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if settings.environment == "development" else None,
        },
    )


# Direct endpoint for serving visualization files
@app.get("/outputs/{job_id}/{file_path:path}")
async def serve_visualization(job_id: str, file_path: str):
    """Serve visualization files directly."""
    outputs_dir = Path(settings.output_dir)
    file_path_obj = (outputs_dir / job_id / file_path).resolve()

    # Security check: ensure the file is within the outputs directory
    try:
        file_path_obj.relative_to(outputs_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path_obj.exists() or not file_path_obj.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path_obj)

# Include routers
app.include_router(upload_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(metrics_router, prefix="/api")
app.include_router(placeholder_router, prefix="/api")  # Frontend compatibility endpoints
app.include_router(reports_router, prefix="/api")
app.include_router(visualizations_router, prefix="/api")
app.include_router(cleanup_router, prefix="/api")  # Admin cleanup endpoints

# System status endpoint
@app.get("/api/status", response_model=dict)
async def get_system_status(db: Session = Depends(get_db)):
    """
    Get comprehensive system status information.

    Includes service health, job statistics, and system metrics.
    This is the main status endpoint for monitoring the application.
    """
    from backend.services import JobService
    from backend.models.job import JobStatus
    import psutil
    import time

    try:
        # Job statistics
        total_jobs = JobService.count_jobs_by_status(db, [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        completed_jobs = JobService.count_jobs_by_status(db, [JobStatus.COMPLETED])
        running_jobs = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
        pending_jobs = JobService.count_jobs_by_status(db, [JobStatus.PENDING])
        failed_jobs = JobService.count_jobs_by_status(db, [JobStatus.FAILED])

        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Process information
        current_process = psutil.Process()
        process_memory = current_process.memory_info().rss / 1024 / 1024  # MB

        # Check service health
        services = {
            "database": "healthy",
            "api": "healthy",
            "celery": "unknown"  # Would need to check Celery heartbeat
        }

        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": settings.app_version,
            "environment": settings.environment,
            "services": services,
            "jobs": {
                "total": total_jobs,
                "completed": completed_jobs,
                "running": running_jobs,
                "pending": pending_jobs,
                "failed": failed_jobs
            },
            "system": {
                "memory_usage_percent": round(memory.percent, 1),
                "memory_used_gb": round(memory.used / (1024**3), 1),
                "memory_total_gb": round(memory.total / (1024**3), 1),
                "disk_usage_percent": round(disk.percent, 1),
                "disk_free_gb": round(disk.free / (1024**3), 1),
                "process_memory_mb": round(process_memory, 1)
            },
            "limits": {
                "max_concurrent_jobs": settings.max_concurrent_jobs,
                "max_upload_size_mb": round(settings.max_upload_size / (1024**2), 0)
            }
        }

    except Exception as e:
        logger.error("status_endpoint_error", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }


# WebSocket endpoint for real-time job updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Send periodic job status updates
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        pass

# Static file mounting will be done in lifespan after settings are initialized


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", settings.api_port))
    should_reload = settings.environment == "development"

    logger.info(
        "starting_uvicorn",
        host=settings.api_host,
        port=port,
        reload=should_reload
    )

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=port,
        reload=should_reload,
        log_level=settings.log_level.lower(),
    )

