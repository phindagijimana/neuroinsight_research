"""
API routes for storage cleanup (admin operations).

Provides endpoints for manual cleanup and storage statistics.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.services import CleanupService

logger = get_logger(__name__)

router = APIRouter(prefix="/cleanup", tags=["cleanup"])


@router.get("/stats")
def get_storage_stats():
    """
    Get storage usage statistics.
    
    Returns:
        Dictionary with storage statistics (uploads, outputs, total size)
    """
    cleanup_service = CleanupService()
    stats = cleanup_service.get_storage_stats()
    return stats


@router.post("/run")
def run_cleanup(
    dry_run: bool = Query(False, description="If true, only report what would be deleted"),
    orphaned_only: bool = Query(False, description="Only clean up orphaned files"),
    old_completed: bool = Query(False, description="Only clean up old completed jobs"),
    old_failed: bool = Query(False, description="Only clean up old failed jobs"),
    completed_days: Optional[int] = Query(None, description="Days to retain completed jobs"),
    failed_days: Optional[int] = Query(None, description="Days to retain failed jobs"),
    db: Session = Depends(get_db),
):
    """
    Manually trigger storage cleanup.
    
    Args:
        dry_run: If true, only report what would be deleted
        orphaned_only: Only clean up orphaned files
        old_completed: Only clean up old completed jobs
        old_failed: Only clean up old failed jobs
        completed_days: Override retention period for completed jobs
        failed_days: Override retention period for failed jobs
        db: Database session
        
    Returns:
        Dictionary with cleanup results
    """
    from backend.core.config import get_settings
    
    settings = get_settings()
    cleanup_service = CleanupService()
    
    results = {
        "dry_run": dry_run,
        "completed_jobs": 0,
        "failed_jobs": 0,
        "orphaned_uploads": 0,
        "orphaned_outputs": 0,
    }
    
    # Clean up orphaned files
    if orphaned_only or not (old_completed or old_failed):
        orphaned_uploads, orphaned_outputs = cleanup_service.cleanup_orphaned_files(
            db=db,
            dry_run=dry_run
        )
        results["orphaned_uploads"] = orphaned_uploads
        results["orphaned_outputs"] = orphaned_outputs
    
    # Clean up old completed jobs
    if old_completed or (not orphaned_only and not old_failed):
        completed_days_override = completed_days or settings.retention_completed_days
        completed_jobs, completed_uploads, completed_outputs = cleanup_service.cleanup_old_completed_jobs(
            db=db,
            days_old=completed_days_override,
            dry_run=dry_run
        )
        results["completed_jobs"] = completed_jobs
        results["orphaned_uploads"] += completed_uploads
        results["orphaned_outputs"] += completed_outputs
    
    # Clean up old failed jobs
    if old_failed or (not orphaned_only and not old_completed):
        failed_days_override = failed_days or settings.retention_failed_days
        failed_jobs, failed_uploads, failed_outputs = cleanup_service.cleanup_failed_jobs(
            db=db,
            days_old=failed_days_override,
            dry_run=dry_run
        )
        results["failed_jobs"] = failed_jobs
        results["orphaned_uploads"] += failed_uploads
        results["orphaned_outputs"] += failed_outputs
    
    # Get storage stats after cleanup
    if not dry_run:
        results["storage_stats"] = cleanup_service.get_storage_stats()
    else:
        results["storage_stats"] = cleanup_service.get_storage_stats()
    
    logger.info("manual_cleanup_run", **results)
    
    return results




