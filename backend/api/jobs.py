"""
API routes for job management.

Provides endpoints for retrieving, updating, and deleting
MRI processing jobs.
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.schemas import JobResponse, JobStatus
from backend.models import Job
from backend.schemas.metric import MetricResponse
from backend.services import JobService, MetricService
from backend.core.config import get_settings

settings = get_settings()

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/")
def list_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[JobStatus] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a list of processing jobs.

    Supports pagination and filtering by status.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        status: Optional status filter
        db: Database session dependency

    Returns:
        List of job records
    """
    jobs = JobService.get_jobs(db, skip=skip, limit=limit, status=status)

    # Convert Job objects to dictionaries for simple response
    result = []
    for job in jobs:
        # Parse visualizations JSON if present
        visualizations = None
        if job.visualizations:
            try:
                import json
                visualizations = json.loads(job.visualizations)
            except:
                visualizations = None

        job_dict = {
            "id": str(job.id),
            "filename": job.filename,
            "file_path": job.file_path,
            "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result_path": job.result_path,
            "progress": job.progress,
            "current_step": job.current_step,
            "patient_name": job.patient_name,
            "patient_id": job.patient_id,
            "patient_age": job.patient_age,
            "patient_sex": job.patient_sex,
            "scanner_info": job.scanner_info,
            "sequence_info": job.sequence_info,
            "notes": job.notes,
            "visualizations": visualizations,
        }
        result.append(job_dict)

    return {"jobs": result, "total": len(result), "skip": skip, "limit": limit}



@router.get("/by-id")
def get_job_by_query(
    job_id: str = Query(..., min_length=8, max_length=8, description="Job ID (8 characters)"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific job by ID using query parameter.

    This endpoint provides an alternative to the path parameter version
    for compatibility with certain frontend implementations.

    Args:
        job_id: Job identifier (8 characters)
        db: Database session dependency

    Returns:
        Job record with associated metrics

    Raises:
        HTTPException: If job not found
    """
    job_response = JobService.get_job_response(db, job_id)

    if not job_response:
        logger.warning("job_not_found_by_query", job_id=job_id)
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found")

    # Convert to dictionary response
    return {
        "id": str(job_response.id),
        "filename": job_response.filename,
        "file_path": job_response.file_path,
        "status": job_response.status.value,  # Convert enum to string
        "error_message": job_response.error_message,
        "created_at": job_response.created_at.isoformat(),
        "started_at": job_response.started_at.isoformat() if job_response.started_at else None,
        "completed_at": job_response.completed_at.isoformat() if job_response.completed_at else None,
        "result_path": job_response.result_path,
        "progress": job_response.progress,
        "current_step": job_response.current_step,
        "patient_name": job_response.patient_name,
        "patient_id": job_response.patient_id,
        "patient_age": job_response.patient_age,
        "patient_sex": job_response.patient_sex,
        "scanner_info": job_response.scanner_info,
        "sequence_info": job_response.sequence_info,
        "notes": job_response.notes,
        "metrics": [metric.dict() for metric in job_response.metrics]
    }


@router.get("/{job_id}")
def get_job(
    job_id: str = Path(..., description="Job ID"),
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific job by ID using path parameter.

    Args:
        job_id: Job identifier
        db: Database session dependency

    Returns:
        Job record with associated metrics

    Raises:
        HTTPException: If job not found
    """
    job_response = JobService.get_job_response(db, job_id)

    if not job_response:
        logger.warning("job_not_found_by_path", job_id=job_id)
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found")

    # Get visualizations (already parsed by JobService)
    visualizations = getattr(job_response, 'visualizations', None)

    # Convert to dictionary response
    return {
        "id": str(job_response.id),
        "filename": job_response.filename,
        "file_path": job_response.file_path,
        "status": job_response.status.value,  # Convert enum to string
        "error_message": job_response.error_message,
        "created_at": job_response.created_at.isoformat(),
        "started_at": job_response.started_at.isoformat() if job_response.started_at else None,
        "completed_at": job_response.completed_at.isoformat() if job_response.completed_at else None,
        "result_path": job_response.result_path,
        "progress": job_response.progress,
        "current_step": job_response.current_step,
        "patient_name": job_response.patient_name,
        "patient_id": job_response.patient_id,
        "patient_age": job_response.patient_age,
        "patient_sex": job_response.patient_sex,
        "scanner_info": job_response.scanner_info,
        "sequence_info": job_response.sequence_info,
        "notes": job_response.notes,
        "metrics": [metric.dict() for metric in job_response.metrics],
        "visualizations": visualizations
    }




@router.get("/stats", response_model=dict)
def get_system_stats(db: Session = Depends(get_db)):
    """
    Get comprehensive system statistics for dashboard.

    Includes job counts, performance metrics, and system status.

    Args:
        db: Database session dependency

    Returns:
        Dictionary with system statistics
    """
    from backend.services.task_service import TaskService
    from backend.services.metric_service import MetricService
    import os

    # Job statistics
    total_jobs = JobService.count_jobs_by_status(db, [JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
    completed_jobs = JobService.count_jobs_by_status(db, [JobStatus.COMPLETED])
    running_jobs = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
    pending_jobs = JobService.count_jobs_by_status(db, [JobStatus.PENDING])
    failed_jobs = JobService.count_jobs_by_status(db, [JobStatus.FAILED])

    # Success rate calculation
    success_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0

    # Average processing time (last 10 completed jobs)
    recent_jobs = JobService.get_jobs(db, limit=10, status=JobStatus.COMPLETED)
    avg_processing_time = None
    if recent_jobs:
        processing_times = []
        for job in recent_jobs:
            if job.started_at and job.completed_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                processing_times.append(duration)

        if processing_times:
            avg_processing_time = sum(processing_times) / len(processing_times)

    # Queue statistics
    executor_stats = TaskService.get_executor_stats()

    # Storage statistics
    upload_dir = os.getenv("UPLOAD_DIR", "/tmp/neuroinsight/uploads")
    output_dir = os.getenv("OUTPUT_DIR", "/tmp/neuroinsight/outputs")

    try:
        import shutil
        upload_usage = shutil.disk_usage(upload_dir)
        output_usage = shutil.disk_usage(output_dir)
        total_storage_used = upload_usage.used + output_usage.used
    except:
        total_storage_used = 0

    # Recent activity (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_jobs = db.query(Job).filter(Job.created_at >= yesterday).count()

    return {
        "jobs": {
            "total": total_jobs,
            "completed": completed_jobs,
            "running": running_jobs,
            "pending": pending_jobs,
            "failed": failed_jobs,
            "success_rate": round(success_rate, 1)
        },
        "performance": {
            "avg_processing_time_seconds": round(avg_processing_time, 1) if avg_processing_time else None,
            "recent_activity_24h": recent_jobs
        },
        "system": {
            "queue_size": executor_stats.get("queue_size", 0),
            "active_threads": executor_stats.get("active_threads", 0),
            "storage_used_mb": round(total_storage_used / (1024 * 1024), 1)
        },
        "limits": {
            "max_concurrent_jobs": settings.max_concurrent_jobs,
            "max_total_jobs": 5  # Allow some pending jobs to queue up
        }
    }


@router.get("/status", response_model=dict)
def get_job_status(
    job_id: str = Query(..., min_length=8, max_length=8, description="Job ID (8 characters)"),
    db: Session = Depends(get_db),
):
    """
    Get the current status of a job.
    
    Lightweight endpoint for polling job progress.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        Dictionary with job status information
    
    Raises:
        HTTPException: If job not found
    """
    job = JobService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": str(job.id),
        "status": job.status.value,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


@router.delete("/delete/{job_id}")
def delete_job_by_id(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a job by path parameter (for frontend compatibility).
    """
    logger.info("delete_job_endpoint_called", job_id=job_id)
    deleted = JobService.delete_job(db, job_id)

    if not deleted:
        logger.warning("job_not_found_for_deletion", job_id=job_id)
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info("job_deleted_successfully", job_id=job_id)
    return {"message": "Job deleted successfully"}

@router.delete("/remove")
def delete_job_simple(
    job_id: str = Query(..., description="Job ID"),
    db: Session = Depends(get_db),
):
    """
    Delete a job by query parameter (alternative method).
    """
    logger.info("delete_job_simple_endpoint_called", job_id=job_id)
    deleted = JobService.delete_job(db, job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"message": "Job deleted successfully"}

@router.delete("/test-delete")
def test_delete_endpoint():
    """Test DELETE endpoint to verify DELETE methods work."""
    logger.info("test_delete_endpoint_called")
    return {"message": "DELETE method works!", "method": "DELETE"}

