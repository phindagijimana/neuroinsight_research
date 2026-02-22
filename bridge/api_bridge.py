"""
FreeSurfer API Bridge Service

This service provides HTTP APIs to manage FreeSurfer container operations,
enabling real MRI brain analysis while avoiding Docker-in-Docker complexity.

Endpoints:
- POST /freesurfer/process - Start FreeSurfer analysis
- GET /freesurfer/status/{job_id} - Check processing status
- GET /freesurfer/results/{job_id} - Get analysis results
"""

import os
import uuid
import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import docker
from docker.errors import DockerException, APIError, ContainerError

from .docker_manager import DockerManager
from .job_tracker import JobTracker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="FreeSurfer API Bridge",
    description="HTTP API for managing FreeSurfer container operations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components (lazy loading for Docker)
job_tracker = JobTracker()
docker_manager = None  # Global variable for lazy initialization

# Data models
class ProcessRequest(BaseModel):
    """Request model for FreeSurfer processing"""
    job_id: str = Field(..., description="Unique job identifier")
    input_file: str = Field(..., description="Path to input MRI file")
    output_dir: str = Field(..., description="Directory for output results")
    subject_id: Optional[str] = Field("subject", description="FreeSurfer subject identifier")

class ProcessResponse(BaseModel):
    """Response model for processing requests"""
    job_id: str
    status: str
    message: str
    container_id: Optional[str] = None

class StatusResponse(BaseModel):
    """Response model for status checks"""
    job_id: str
    status: str
    progress: float
    message: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    container_status: Optional[str] = None

class ResultsResponse(BaseModel):
    """Response model for results retrieval"""
    job_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "freesurfer-api-bridge"}

@app.post("/freesurfer/process", response_model=ProcessResponse)
async def start_freesurfer_processing(
    request: ProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    Start FreeSurfer processing for an MRI file

    This endpoint:
    1. Validates input parameters
    2. Starts a FreeSurfer container
    3. Returns job tracking information
    """
    try:
        logger.info(f"Starting FreeSurfer processing for job {request.job_id}")

        # Validate input file exists
        if not Path(request.input_file).exists():
            raise HTTPException(
                status_code=400,
                detail=f"Input file not found: {request.input_file}"
            )

        # Create output directory if it doesn't exist
        output_path = Path(request.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Start FreeSurfer processing in background
        background_tasks.add_task(
            process_freesurfer_job,
            request.job_id,
            request.input_file,
            request.output_dir,
            request.subject_id
        )

        return ProcessResponse(
            job_id=request.job_id,
            status="started",
            message="FreeSurfer processing initiated",
            container_id=None  # Will be set when container starts
        )

    except Exception as e:
        logger.error(f"Error starting FreeSurfer processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/freesurfer/status/{job_id}", response_model=StatusResponse)
async def get_processing_status(job_id: str):
    """Get the status of a FreeSurfer processing job"""
    try:
        status_info = job_tracker.get_job_status(job_id)
        if not status_info:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return StatusResponse(**status_info)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/freesurfer/results/{job_id}", response_model=ResultsResponse)
async def get_processing_results(job_id: str):
    """Get the results of a completed FreeSurfer processing job"""
    try:
        results = job_tracker.get_job_results(job_id)
        if not results:
            raise HTTPException(status_code=404, detail=f"Results for job {job_id} not found")

        return ResultsResponse(**results)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_freesurfer_job(
    job_id: str,
    input_file: str,
    output_dir: str,
    subject_id: str
):
    """
    Background task to process FreeSurfer job

    This function:
    1. Starts the FreeSurfer container
    2. Monitors progress
    3. Collects results
    4. Updates job status
    """
    try:
        logger.info(f"Processing FreeSurfer job {job_id}")

        # Update job status to processing
        job_tracker.update_job_status(job_id, "processing", 0.0, "Starting FreeSurfer container")

        # Start FreeSurfer container
        container_info = docker_manager.start_freesurfer_container(
            job_id=job_id,
            input_file=input_file,
            output_dir=output_dir,
            subject_id=subject_id
        )

        # Update with container info
        job_tracker.update_container_info(job_id, container_info)

        # Monitor progress
        await monitor_freesurfer_progress(job_id, container_info["container_id"])

        # Collect results
        results = docker_manager.collect_results(job_id, output_dir)

        # Update final status
        job_tracker.complete_job(job_id, results)

        logger.info(f"FreeSurfer job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"FreeSurfer job {job_id} failed: {e}")
        job_tracker.fail_job(job_id, str(e))

async def monitor_freesurfer_progress(job_id: str, container_id: str):
    """
    Monitor FreeSurfer processing progress

    FreeSurfer processing typically takes 10-30 minutes and goes through
    several stages. This function polls the container logs and updates progress.
    """
    try:
        stages = [
            ("Motion Correction", 0.1),
            ("Nu Intensity Correction", 0.2),
            ("Talairach Transform", 0.3),
            ("Intensity Normalization", 0.4),
            ("Skull Strip", 0.5),
            ("EM Registration", 0.6),
            ("Initial Surface", 0.7),
            ("Surface Refinement", 0.8),
            ("Final Topology Correction", 0.9),
            ("Surface Inflation", 1.0)
        ]

        # Simulate progress updates (in real implementation, parse actual logs)
        for stage_name, progress in stages:
            await asyncio.sleep(60)  # Wait 1 minute between updates
            job_tracker.update_job_status(
                job_id,
                "processing",
                progress,
                f"FreeSurfer: {stage_name}"
            )

            # Check if container is still running
            container_status = docker_manager.get_container_status(container_id)
            if container_status != "running":
                break

    except Exception as e:
        logger.error(f"Error monitoring progress for job {job_id}: {e}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
