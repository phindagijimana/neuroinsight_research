#!/usr/bin/env python3
"""
NeuroInsight cleanup utility.
Removes old completed/failed jobs and their files.
Also cleans orphaned job directories (files without database records).
"""

import argparse
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.database import SessionLocal
from backend.core.config import get_settings
from backend.models.job import Job, JobStatus
from backend.models.metric import Metric
from backend.services.cleanup_service import CleanupService


def _parse_keep_ids(values: list[str]) -> set[str]:
    keep_ids: set[str] = set()
    for value in values:
        for item in value.split(","):
            item = item.strip()
            if item:
                keep_ids.add(item)
    return keep_ids


def _job_cutoff_timestamp(job: Job) -> datetime:
    if job.completed_at:
        return job.completed_at
    return job.created_at


def clean_orphaned_files(keep_ids: set[str], retention_days: int) -> int:
    """
    Clean orphaned job directories that don't have database records.
    
    Args:
        keep_ids: Set of job IDs to preserve
        retention_days: Age threshold in days
        
    Returns:
        Number of orphaned directories removed
    """
    settings = get_settings()
    outputs_dir = Path(settings.output_dir)
    
    if not outputs_dir.exists():
        return 0
    
    db = SessionLocal()
    try:
        # Get all job IDs from database
        db_job_ids = {str(job.id) for job in db.query(Job.id).all()}
        
        # CRITICAL: Get all RUNNING/PENDING job IDs to protect their directories
        running_job_ids = {
            str(job.id) for job in db.query(Job.id).filter(
                Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
            ).all()
        }
    finally:
        db.close()
    
    cutoff_time = datetime.utcnow().timestamp() - (retention_days * 86400)
    removed_count = 0
    skipped_running_count = 0
    
    # Scan all directories in outputs
    for item in outputs_dir.iterdir():
        if not item.is_dir():
            continue
        
        job_id = item.name
        
        # Skip if in database
        if job_id in db_job_ids:
            continue
        
        # CRITICAL: Skip if job is currently running or pending
        if job_id in running_job_ids:
            print(f"  Skipping active job (running/pending): {job_id}")
            skipped_running_count += 1
            continue
        
        # Skip if in keep list
        if job_id in keep_ids:
            print(f"  Keeping orphaned job (in keep list): {job_id}")
            continue
        
        # Check directory age
        try:
            dir_mtime = item.stat().st_mtime
            if dir_mtime >= cutoff_time:
                continue  # Too recent
            
            # Delete orphaned directory
            shutil.rmtree(item)
            removed_count += 1
            print(f"  Removed orphaned job directory: {job_id}")
        except Exception as e:
            print(f"  Warning: Failed to remove {job_id}: {e}")
    
    if skipped_running_count > 0:
        print(f"  Protected {skipped_running_count} active job(s) from deletion")
    
    return removed_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean old NeuroInsight jobs.",
        epilog="Cleans both database records and orphaned files on disk."
    )
    retention_group = parser.add_mutually_exclusive_group()
    retention_group.add_argument(
        "--days",
        type=int,
        default=90,
        help="Retention period in days for completed/failed jobs (default: 90).",
    )
    retention_group.add_argument(
        "--months",
        type=int,
        help="Retention period in months for completed/failed jobs.",
    )
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        help="Job IDs to keep (comma-separated or repeatable).",
    )
    parser.add_argument(
        "--orphaned-only",
        action="store_true",
        help="Only clean orphaned files (not database jobs).",
    )
    parser.add_argument(
        "--skip-orphaned",
        action="store_true",
        help="Skip orphaned file cleanup (only clean database jobs).",
    )
    args = parser.parse_args()

    retention_days = args.days
    if args.months is not None:
        retention_days = args.months * 30

    keep_ids = _parse_keep_ids(args.keep)
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    removed_jobs = 0
    skipped_jobs = 0
    removed_orphaned = 0
    
    # Clean database jobs (unless --orphaned-only)
    if not args.orphaned_only:
        print("Cleaning database jobs...")
        db = SessionLocal()
        cleanup_service = CleanupService()
        try:
            # Only clean COMPLETED or FAILED jobs (never RUNNING or PENDING)
            candidates = (
                db.query(Job)
                .filter(Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]))
                .all()
            )

            for job in candidates:
                if str(job.id) in keep_ids:
                    skipped_jobs += 1
                    continue

                job_time = _job_cutoff_timestamp(job)
                if job_time and job_time < cutoff:
                    db.query(Metric).filter(Metric.job_id == job.id).delete()
                    cleanup_service.delete_job_files(job)
                    db.delete(job)
                    removed_jobs += 1

            db.commit()
            
            # Verify no running jobs were affected
            running_count = db.query(Job).filter(
                Job.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
            ).count()
            if running_count > 0:
                print(f"  Note: {running_count} active job(s) were protected from cleanup")
        finally:
            db.close()
    
    # Clean orphaned files (unless --skip-orphaned)
    if not args.skip_orphaned:
        print("Cleaning orphaned files...")
        removed_orphaned = clean_orphaned_files(keep_ids, retention_days)

    print(
        "\nCleanup completed. "
        f"Database jobs removed: {removed_jobs}. "
        f"Jobs kept by ID: {skipped_jobs}. "
        f"Orphaned files removed: {removed_orphaned}."
    )


if __name__ == "__main__":
    main()

