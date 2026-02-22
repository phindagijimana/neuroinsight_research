"""
API routes for hippocampal metrics.

Provides endpoints for retrieving volumetric measurements
and asymmetry indices.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.schemas import MetricResponse
from backend.services import MetricService

logger = get_logger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/", response_model=List[MetricResponse])
def list_metrics(
    job_id: str = Query(..., description="Job identifier"),
    db: Session = Depends(get_db),
):
    """
    Retrieve all metrics for a specific job.

    Args:
        job_id: Job identifier
        db: Database session dependency

    Returns:
        List of hippocampal metrics

    Raises:
        HTTPException: If job doesn't exist or has no metrics
    """
    from backend.services import JobService

    # First check if the job exists
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    metrics = MetricService.get_metrics_by_job(db, job_id)

    # If job exists but has no metrics, this might indicate processing hasn't completed
    if not metrics and job.status.value in ['running', 'pending']:
        raise HTTPException(status_code=202, detail="Metrics not yet available - job still processing")

    return metrics


@router.get("/{metric_id}", response_model=MetricResponse)
def get_metric(
    metric_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve a specific metric by ID.
    
    Args:
        metric_id: Metric identifier
        db: Database session dependency
    
    Returns:
        Metric record
    
    Raises:
        HTTPException: If metric not found
    """
    metric = MetricService.get_metric(db, metric_id)
    
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    
    return metric


@router.get("/region/{region}", response_model=List[MetricResponse])
def get_metrics_by_region(
    region: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve all metrics for a specific hippocampal region.
    
    Useful for comparing asymmetry across multiple subjects.
    
    Args:
        region: Hippocampal subregion name (e.g., 'CA1', 'CA3')
        db: Database session dependency
    
    Returns:
        List of metrics for the specified region
    """
    metrics = MetricService.get_metrics_by_region(db, region)
    return metrics

