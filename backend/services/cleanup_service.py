"""
Cleanup service for managing storage and job lifecycle.

This service provides long-term storage management:
- Automatic cleanup of old/failed jobs
- Retention policies
- Orphaned file detection and cleanup
- Storage quota management
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.core.logging import get_logger
from backend.models import Job, Metric
from backend.models.job import JobStatus
from backend.services.storage_service import StorageService

logger = get_logger(__name__)
settings = get_settings()


class CleanupService:
    """
    Service for managing storage cleanup and retention policies.
    """
    
    def __init__(self):
        """Initialize cleanup service."""
        self.storage_service = StorageService()
        self.uploads_dir = Path(settings.upload_dir)
        self.outputs_dir = Path(settings.output_dir)
    
    def delete_job_files(self, job: Job) -> Tuple[int, int]:
        """
        Delete all files associated with a job.
        
        Args:
            job: Job instance
            
        Returns:
            Tuple of (upload_files_deleted, output_files_deleted)
        """
        upload_files_deleted = 0
        output_files_deleted = 0
        
        # Delete uploaded file
        if job.file_path:
            try:
                if self.storage_service.delete_file(job.file_path):
                    upload_files_deleted = 1
                    logger.info("job_upload_file_deleted", job_id=str(job.id), path=job.file_path)
            except Exception as e:
                logger.warning("job_upload_file_delete_failed", job_id=str(job.id), error=str(e))
        
        # Delete output directory
        output_dir = self.outputs_dir / str(job.id)
        if output_dir.exists():
            try:
                import shutil
                shutil.rmtree(output_dir)
                output_files_deleted = 1
                logger.info("job_output_directory_deleted", job_id=str(job.id), path=str(output_dir))
            except Exception as e:
                logger.warning("job_output_directory_delete_failed", job_id=str(job.id), error=str(e))
        
        return (upload_files_deleted, output_files_deleted)
    
    def cleanup_old_completed_jobs(
        self,
        db: Session,
        days_old: int = 30,
        dry_run: bool = False
    ) -> Tuple[int, int, int]:
        """
        Clean up old completed jobs based on retention policy.
        
        Args:
            db: Database session
            days_old: Number of days after completion to retain jobs
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (jobs_deleted, upload_files_deleted, output_dirs_deleted)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_jobs = db.query(Job).filter(
            Job.status == JobStatus.COMPLETED,
            Job.completed_at < cutoff_date
        ).all()
        
        jobs_deleted = 0
        upload_files_deleted = 0
        output_dirs_deleted = 0
        
        for job in old_jobs:
            logger.info(
                "old_job_cleanup",
                job_id=str(job.id),
                completed_at=job.completed_at.isoformat(),
                days_old=(datetime.utcnow() - job.completed_at).days,
                dry_run=dry_run
            )
            
            if not dry_run:
                # Delete associated metrics
                db.query(Metric).filter(Metric.job_id == job.id).delete()
                
                # Delete files
                upload_del, output_del = self.delete_job_files(job)
                upload_files_deleted += upload_del
                output_dirs_deleted += output_del
                
                # Delete job record
                db.delete(job)
                jobs_deleted += 1
        
        if not dry_run:
            db.commit()
        
        return (jobs_deleted, upload_files_deleted, output_dirs_deleted)
    
    def cleanup_failed_jobs(
        self,
        db: Session,
        days_old: int = 7,
        dry_run: bool = False
    ) -> Tuple[int, int, int]:
        """
        Clean up old failed jobs (shorter retention than completed).
        
        Args:
            db: Database session
            days_old: Number of days after failure to retain jobs
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (jobs_deleted, upload_files_deleted, output_dirs_deleted)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_jobs = db.query(Job).filter(
            Job.status == JobStatus.FAILED,
            Job.completed_at < cutoff_date
        ).all()
        
        jobs_deleted = 0
        upload_files_deleted = 0
        output_dirs_deleted = 0
        
        for job in old_jobs:
            logger.info(
                "failed_job_cleanup",
                job_id=str(job.id),
                failed_at=job.completed_at.isoformat(),
                error=job.error_message,
                dry_run=dry_run
            )
            
            if not dry_run:
                # Delete associated metrics
                db.query(Metric).filter(Metric.job_id == job.id).delete()
                
                # Delete files
                upload_del, output_del = self.delete_job_files(job)
                upload_files_deleted += upload_del
                output_dirs_deleted += output_del
                
                # Delete job record
                db.delete(job)
                jobs_deleted += 1
        
        if not dry_run:
            db.commit()
        
        return (jobs_deleted, upload_files_deleted, output_dirs_deleted)
    
    def cleanup_orphaned_files(self, db: Session, dry_run: bool = False) -> Tuple[int, int]:
        """
        Find and clean up files/directories with no corresponding job.
        
        Args:
            db: Database session
            dry_run: If True, only report what would be deleted
            
        Returns:
            Tuple of (orphaned_uploads_deleted, orphaned_outputs_deleted)
        """
        # Get all job IDs from database
        all_jobs = db.query(Job).all()
        valid_job_ids = {str(job.id) for job in all_jobs}
        
        orphaned_uploads = 0
        orphaned_outputs = 0
        
        # Check upload files
        if self.uploads_dir.exists():
            for upload_file in self.uploads_dir.glob("*"):
                if not upload_file.is_file():
                    continue
                
                # Extract UUID from filename (format: uuid_filename.ext)
                filename = upload_file.name
                if '_' in filename:
                    potential_uuid = filename.split('_')[0]
                    if len(potential_uuid) == 36:  # UUID length
                        if potential_uuid not in valid_job_ids:
                            logger.info(
                                "orphaned_upload_found",
                                file=filename,
                                dry_run=dry_run
                            )
                            
                            if not dry_run:
                                try:
                                    upload_file.unlink()
                                    orphaned_uploads += 1
                                except Exception as e:
                                    logger.warning("orphaned_upload_delete_failed", file=filename, error=str(e))
        
        # Check output directories
        if self.outputs_dir.exists():
            for output_dir in self.outputs_dir.iterdir():
                if not output_dir.is_dir():
                    continue
                
                dir_name = output_dir.name
                if len(dir_name) == 36:  # UUID length
                    if dir_name not in valid_job_ids:
                        logger.info(
                            "orphaned_output_found",
                            directory=dir_name,
                            dry_run=dry_run
                        )
                        
                        if not dry_run:
                            try:
                                import shutil
                                shutil.rmtree(output_dir)
                                orphaned_outputs += 1
                            except Exception as e:
                                logger.warning("orphaned_output_delete_failed", directory=dir_name, error=str(e))
        
        return (orphaned_uploads, orphaned_outputs)
    
    def get_storage_stats(self) -> dict:
        """
        Get storage usage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        upload_size = 0
        upload_count = 0
        output_size = 0
        output_count = 0
        
        if self.uploads_dir.exists():
            for f in self.uploads_dir.glob("*"):
                if f.is_file():
                    upload_size += f.stat().st_size
                    upload_count += 1
        
        if self.outputs_dir.exists():
            for d in self.outputs_dir.iterdir():
                if d.is_dir():
                    output_size += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    output_count += 1
        
        return {
            "uploads": {
                "count": upload_count,
                "size_bytes": upload_size,
                "size_mb": upload_size / 1024 / 1024,
                "size_gb": upload_size / 1024 / 1024 / 1024,
            },
            "outputs": {
                "count": output_count,
                "size_bytes": output_size,
                "size_mb": output_size / 1024 / 1024,
                "size_gb": output_size / 1024 / 1024 / 1024,
            },
            "total_size_mb": (upload_size + output_size) / 1024 / 1024,
            "total_size_gb": (upload_size + output_size) / 1024 / 1024 / 1024,
        }

