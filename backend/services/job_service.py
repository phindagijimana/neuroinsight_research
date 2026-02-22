"""
Job service for managing MRI processing jobs.

This service provides business logic for creating, retrieving,
and updating jobs in the system.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
import subprocess as subprocess_module

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.core.config import get_settings
from backend.models import Job, Metric
from backend.models.job import JobStatus
from backend.schemas import JobCreate, JobUpdate, JobResponse

logger = get_logger(__name__)


class JobService:
    """
    Service class for job-related operations.
    
    Handles CRUD operations and business logic for MRI processing jobs.
    """
    
    @staticmethod
    def create_job(db: Session, job_data: JobCreate) -> Job:
        """
        Create a new processing job.
        
        Args:
            db: Database session
            job_data: Job creation data
        
        Returns:
            Created job instance
        """
        job = Job(
            filename=job_data.filename,
            file_path=job_data.file_path,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            patient_name=job_data.patient_name,
            patient_id=job_data.patient_id,
            patient_age=job_data.patient_age,
            patient_sex=job_data.patient_sex,
            scanner_info=job_data.scanner_info,
            sequence_info=job_data.sequence_info,
            notes=job_data.notes,
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(
            "job_created",
            job_id=str(job.id),
            filename=job.filename,
            status=job.status.value,
        )
        
        return job
    
    @staticmethod
    def get_job(db: Session, job_id) -> Optional[Job]:
        """
        Retrieve a job by ID.
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
        
        Returns:
            Job instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility (VARCHAR(36) with dashes)
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()

        # Ensure metrics have laterality computed
        if job and job.metrics:
            for metric in job.metrics:
                # Force computation of laterality property to ensure it's available
                _ = metric.laterality

        return job

    @staticmethod
    def get_job_response(db: Session, job_id) -> Optional[JobResponse]:
        """
        Retrieve a job by ID and return as JobResponse with computed laterality.

        Args:
            db: Database session
            job_id: Job identifier

        Returns:
            JobResponse instance if found, None otherwise
        """
        job = JobService.get_job(db, job_id)
        if not job:
            return None

        # Parse visualizations JSON if present
        visualizations = None
        if job.visualizations:
            try:
                import json
                visualizations = json.loads(job.visualizations)
            except:
                visualizations = None

        # Convert to dict for modification
        job_dict = {
            'id': job.id,
            'filename': job.filename,
            'file_path': job.file_path,
            'status': job.status,
            'error_message': job.error_message,
            'created_at': job.created_at,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
            'result_path': job.result_path,
            'progress': job.progress,
            'current_step': job.current_step,
            'patient_name': job.patient_name,
            'patient_id': job.patient_id,
            'patient_age': job.patient_age,
            'patient_sex': job.patient_sex,
            'scanner_info': job.scanner_info,
            'sequence_info': job.sequence_info,
            'notes': job.notes,
            'visualizations': visualizations,
            'metrics': []
        }

        # Add metrics with computed laterality
        for metric in job.metrics:
            metric_dict = {
                'id': metric.id,
                'region': metric.region,
                'left_volume': metric.left_volume,
                'right_volume': metric.right_volume,
                'asymmetry_index': metric.asymmetry_index,
                'laterality': metric.laterality  # This will compute the property
            }
            job_dict['metrics'].append(metric_dict)

        # Convert back to JobResponse
        return JobResponse(**job_dict)
    
    @staticmethod
    def get_jobs(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[Job]:
        """
        Retrieve multiple jobs with optional filtering.
        
        Args:
            db: Database session
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            status: Filter by job status (optional)
        
        Returns:
            List of job instances
        """
        query = db.query(Job)
        
        if status:
            query = query.filter(Job.status == status)
        
        return query.order_by(Job.created_at.desc(), Job.id.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def count_jobs_by_status(db: Session, statuses: List[JobStatus]) -> int:
        """
        Count jobs with specific statuses.

        Args:
            db: Database session
            statuses: List of job statuses to count

        Returns:
            Number of jobs with the specified statuses
        """
        return db.query(Job).filter(Job.status.in_(statuses)).count()

    @staticmethod
    def get_oldest_pending_job(db: Session) -> Optional[Job]:
        """
        Get the oldest job with PENDING status.

        Args:
            db: Database session

        Returns:
            Oldest pending job, or None if no pending jobs exist
        """
        return db.query(Job)\
                 .filter(Job.status == JobStatus.PENDING)\
                 .order_by(Job.created_at.asc())\
                 .first()

    @staticmethod
    def update_job(db: Session, job_id, job_update: JobUpdate) -> Optional[Job]:
        """
        Update an existing job.
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
            job_update: Updated job data
        
        Returns:
            Updated job instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()
        
        if not job:
            logger.warning("job_not_found", job_id=str(job_id))
            return None
        
        # Update fields if provided
        update_data = job_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(job, field, value)
        
        db.commit()
        db.refresh(job)
        
        logger.info(
            "job_updated",
            job_id=str(job.id),
            updates=list(update_data.keys()),
            status=job.status.value,
        )
        
        return job
    
    @staticmethod
    def delete_job(db: Session, job_id) -> bool:
        """
        Delete a job and its associated metrics and files.
        
        For RUNNING or PENDING jobs, this will:
        1. Cancel/revoke the Celery task
        2. Terminate FastSurfer processes (if running)
        3. Mark job as CANCELLED (if active)
        4. Delete files after a brief delay
        
        For COMPLETED or FAILED jobs, this will:
        1. Immediately delete files and database records
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
        
        Returns:
            True if deleted, False if not found
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()
        
        if not job:
            logger.warning("job_not_found", job_id=str(job_id))
            return False
        
        job_status = job.status
        is_active = job.is_active
        
        # Handle active jobs (PENDING or RUNNING)
        if is_active:
            logger.info("cancelling_active_job", job_id=str(job_id), status=job_status.value)
            
            # Kill Docker container if running
            if job.docker_container_id:
                try:
                    import subprocess
                    logger.info("killing_docker_container", 
                               job_id=str(job_id), 
                               container_id=job.docker_container_id)
                    
                    # Stop the container (will kill the subprocess too)
                    result = subprocess.run(
                        ["docker", "stop", job.docker_container_id],
                        capture_output=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.info("docker_container_stopped", 
                                   job_id=str(job_id), 
                                   container_id=job.docker_container_id)
                    else:
                        logger.warning("docker_container_stop_failed",
                                      job_id=str(job_id),
                                      container_id=job.docker_container_id,
                                      stderr=result.stderr.decode() if result.stderr else "")
                    
                    # Remove the container to prevent it from becoming orphaned
                    remove_result = subprocess.run(
                        ["docker", "rm", "-f", job.docker_container_id],
                        capture_output=True,
                        timeout=10
                    )
                    
                    if remove_result.returncode == 0:
                        logger.info("docker_container_removed", 
                                   job_id=str(job_id), 
                                   container_id=job.docker_container_id)
                    else:
                        logger.warning("docker_container_remove_failed",
                                      job_id=str(job_id),
                                      container_id=job.docker_container_id,
                                      stderr=remove_result.stderr.decode() if remove_result.stderr else "")
                        
                except Exception as e:
                    logger.warning("docker_container_cleanup_error", 
                                  job_id=str(job_id), 
                                  error=str(e))
            
            # Cancel Celery task and terminate FastSurfer
            try:
                from backend.services import TaskManagementService
                TaskManagementService.cancel_job_task(job_id, job_status.value)
            except Exception as e:
                logger.warning("task_cancellation_failed", job_id=str(job_id), error=str(e))
                # Continue with deletion even if cancellation fails
            
            # Mark job as CANCELLED instead of deleting immediately
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            job.error_message = "Job cancelled by user"
            job.docker_container_id = None  # Clear container ID
            db.commit()
            
            # Wait a moment for processes to terminate gracefully
            import time
            time.sleep(2)
            
            logger.info("job_marked_cancelled", job_id=str(job_id))
        
        # Delete associated metrics (use string format for SQLite)
        db.query(Metric).filter(Metric.job_id == job_id_str).delete()
        
        # Delete associated files (upload and output directory)
        try:
            from backend.services import CleanupService
            cleanup_service = CleanupService()
            cleanup_service.delete_job_files(job)
        except Exception as e:
            logger.warning("file_cleanup_failed_during_job_delete", job_id=str(job_id), error=str(e))
            # Continue with database deletion even if file deletion fails
        
        # Delete job record
        db.delete(job)
        db.commit()
        
        logger.info(
            "job_deleted_with_files",
            job_id=str(job_id),
            previous_status=job_status.value,
            was_active=is_active
        )
        
        # If we deleted a running or pending job, try to start the next pending job
        if is_active:
            try:
                JobService._start_next_pending_job(db)
            except Exception as e:
                logger.warning("failed_to_auto_start_next_job_after_deletion", error=str(e))
        
        return True

    @staticmethod
    def cleanup_orphaned_containers(db: Session, logger) -> int:
        """
        Clean up Docker containers that don't have corresponding database jobs.

        This maintenance function identifies and removes containers that may have been
        left running after jobs were deleted or system interruptions occurred.

        Args:
            db: Database session
            logger: Logger instance

        Returns:
            Number of orphaned containers cleaned up
        """
        try:
            import subprocess
            from backend.core.database import SessionLocal
            from sqlalchemy.orm import Session as OrmSession

            owns_session = False
            if db is None:
                db = SessionLocal()
                owns_session = True

            # Get all running FreeSurfer containers
            settings = get_settings()
            prefix = settings.freesurfer_container_prefix
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.warning("failed_to_list_containers", error=result.stderr.strip())
                return 0

            running_containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
            cleaned_count = 0

            pending_container_grace_seconds = settings.processing_timeout

            for container_name in running_containers:
                if not container_name.strip():
                    continue

                # Extract job ID from container name (format: {prefix}{job_id})
                try:
                    if not container_name.startswith(prefix):
                        continue
                    job_id_part = container_name.replace(prefix, "", 1)
                    
                    # Check container age to avoid race conditions with newly started jobs
                    try:
                        inspect_result = subprocess.run(
                            ["docker", "inspect", "--format", "{{.Created}}", container_name],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if inspect_result.returncode == 0:
                            created_str = inspect_result.stdout.strip()
                            # Parse Docker's timestamp format (2026-01-28T20:22:46.829294235Z)
                            # Docker uses nanosecond precision, but Python only supports microseconds
                            # Remove extra digits beyond microseconds (keep only 6 decimal places)
                            import re
                            from datetime import timezone
                            fixed_timestamp = re.sub(r'\.(\d{6})\d+', r'.\1', created_str)
                            created_at = datetime.fromisoformat(fixed_timestamp.replace('Z', '+00:00'))
                            age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
                            
                            # Skip cleanup for containers less than 60 seconds old
                            # This prevents race conditions with newly started jobs
                            if age_seconds < 60:
                                logger.info(
                                    "skipping_cleanup_for_new_container",
                                    container_name=container_name,
                                    age_seconds=round(age_seconds, 2),
                                    reason="container_too_new"
                                )
                                continue  # Skip this container
                    except Exception as age_check_error:
                        logger.warning(
                            "failed_to_check_container_age",
                            container_name=container_name,
                            error=str(age_check_error)
                        )
                        # Continue with normal cleanup logic if age check fails
                    
                    job = JobService.get_job(db, job_id_part)

                    should_stop = False
                    stop_reason = None

                    if not job:
                        should_stop = True
                        stop_reason = "job_missing"
                    else:
                        job_status = job.status.value if hasattr(job.status, "value") else str(job.status)
                        if job_status in ["failed", "cancelled", "completed"]:
                            should_stop = True
                            stop_reason = f"job_{job_status}"
                        elif job_status == "pending":
                            # Avoid race conditions: only treat as stale if it has been pending for a while
                            if job.started_at:
                                elapsed_seconds = (datetime.utcnow() - job.started_at).total_seconds()
                                if elapsed_seconds > pending_container_grace_seconds:
                                    should_stop = True
                                    stop_reason = "pending_with_running_container"

                    if should_stop:
                        # Enhanced logging BEFORE stopping container for better debugging
                        import os
                        logger.info(
                            "about_to_stop_container_decision",
                            container_name=container_name,
                            job_id=job_id_part,
                            reason=stop_reason,
                            job_status=job_status if job else "missing",
                            job_started_at=str(job.started_at) if job and job.started_at else None,
                            job_created_at=str(job.created_at) if job and job.created_at else None,
                            elapsed_seconds=elapsed_seconds if 'elapsed_seconds' in locals() else None,
                            grace_period_seconds=pending_container_grace_seconds,
                            process_id=os.getpid(),
                            function="cleanup_orphaned_containers"
                        )
                        
                        logger.warning(
                            "found_orphaned_or_stale_container",
                            container_name=container_name,
                            job_id=job_id_part,
                            reason=stop_reason,
                        )

                        stop_result = subprocess.run(
                            ["docker", "stop", container_name],
                            capture_output=True,
                            timeout=30
                        )

                        if stop_result.returncode == 0:
                            logger.info(
                                "stopped_orphaned_or_stale_container",
                                container_name=container_name,
                                job_id=job_id_part,
                                reason=stop_reason,
                            )
                            cleaned_count += 1

                            if job and job.docker_container_id == container_name:
                                job.docker_container_id = None
                                db.commit()
                        else:
                            logger.error(
                                "failed_to_stop_orphaned_or_stale_container",
                                container_name=container_name,
                                error=stop_result.stderr.decode(),
                            )
                    else:
                        logger.debug(
                            "container_has_active_job",
                            container_name=container_name,
                            job_id=str(job.id) if job else None,
                            job_status=job.status.value if job else None,
                        )
                except Exception as e:
                    logger.error("error_processing_container",
                               container_name=container_name,
                               error=str(e))

            if cleaned_count > 0:
                logger.info("orphaned_container_cleanup_completed", cleaned_count=cleaned_count)

            return cleaned_count

        except Exception as e:
            logger.error("orphaned_container_cleanup_failed", error=str(e))
            return 0

    @staticmethod
    def cleanup_stopped_containers(logger, retention_days: int = 5) -> int:
        """
        Remove stopped FreeSurfer containers older than retention_days.
        """
        try:
            settings = get_settings()
            prefix = settings.freesurfer_container_prefix
            result = subprocess_module.run(
                ["docker", "ps", "-a", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.warning("failed_to_list_all_containers", error=result.stderr.strip())
                return 0

            container_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            removed = 0
            now = datetime.now(timezone.utc)

            for container_name in container_names:
                inspect = subprocess_module.run(
                    ["docker", "inspect", "--format", "{{.State.Status}} {{.State.FinishedAt}}", container_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if inspect.returncode != 0:
                    continue
                parts = inspect.stdout.strip().split(" ", 1)
                if len(parts) != 2:
                    continue
                status, finished_at = parts
                if status not in ("exited", "dead"):
                    continue
                try:
                    finished_time = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
                except Exception:
                    continue
                if now - finished_time < timedelta(days=retention_days):
                    continue

                rm_result = subprocess_module.run(
                    ["docker", "rm", container_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if rm_result.returncode == 0:
                    removed += 1
                    logger.info("removed_stopped_container", container_name=container_name)

            if removed:
                logger.info("stopped_container_cleanup_completed", removed=removed, retention_days=retention_days)
            return removed
        except Exception as e:
            logger.error("stopped_container_cleanup_failed", error=str(e))
            return 0
        finally:
            try:
                if 'owns_session' in locals() and owns_session:
                    db.close()
            except Exception:
                pass
    
    @staticmethod
    def start_job(db: Session, job_id) -> Optional[Job]:
        """
        Mark a job as started.
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
        
        Returns:
            Updated job instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()
        
        if not job:
            return None
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        db.commit()
        db.refresh(job)
        
        logger.info("job_started", job_id=str(job.id))
        
        return job
    
    @staticmethod
    def build_visualization_payload(job_id: str) -> Dict:
        """
        Build visualization URLs for the frontend viewer.

        Uses API endpoints so the UI can load overlays without needing file paths.
        """
        base = f"/api/visualizations/{job_id}"
        overlay_base = f"{base}/overlay/slice_00"
        return {
            "overlays": {
                "axial": {
                    "anatomical": f"{overlay_base}?orientation=axial&layer=anatomical",
                    "hippocampus": f"{overlay_base}?orientation=axial&layer=overlay",
                },
                "coronal": {
                    "anatomical": f"{overlay_base}?orientation=coronal&layer=anatomical",
                    "hippocampus": f"{overlay_base}?orientation=coronal&layer=overlay",
                },
            },
            "whole_hippocampus": {
                "anatomical": f"{base}/whole-hippocampus/anatomical",
                "segmentation": f"{base}/whole-hippocampus/nifti",
                "metadata": f"{base}/whole-hippocampus/metadata",
            },
            "subfields": {
                "segmentation": f"{base}/subfields/nifti",
                "metadata": f"{base}/subfields/metadata",
            },
        }

    @staticmethod
    def complete_job(
        db: Session,
        job_id,
        result_path: str,
        visualizations: Optional[Dict] = None
    ) -> Optional[Job]:
        """
        Mark a job as completed.

        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
            result_path: Path to processing results
            visualizations: Dictionary of visualization paths (optional)

        Returns:
            Updated job instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()
        
        if not job:
            return None
        
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.result_path = result_path

        # Save visualizations (default to API URLs if none provided)
        if visualizations is None:
            visualizations = JobService.build_visualization_payload(job_id_str)
        import json
        job.visualizations = json.dumps(visualizations)

        db.commit()
        db.refresh(job)
        
        logger.info(
            "job_completed",
            job_id=str(job.id),
            duration_seconds=job.duration_seconds,
        )

        # Trigger queue processing to start next pending job
        JobService.process_job_queue(db)

        return job
    
    @staticmethod
    def fail_job(db: Session, job_id, error_message: str) -> Optional[Job]:
        """
        Mark a job as failed.
        
        Args:
            db: Database session
            job_id: Job identifier (UUID or string - will be converted to string for SQLite)
            error_message: Error description
        
        Returns:
            Updated job instance if found, None otherwise
        """
        # Convert to string for SQLite compatibility
        job_id_str = str(job_id)
        job = db.query(Job).filter(Job.id == job_id_str).first()
        
        if not job:
            return None
        
        # Status protection: Don't overwrite completed jobs
        # This prevents duplicate/retry tasks from marking a successful job as failed
        if job.status == JobStatus.COMPLETED:
            logger.warning("attempted_to_fail_completed_job",
                          job_id=job_id_str,
                          current_status="COMPLETED",
                          error_message=error_message,
                          message="Skipping status change - job is already completed")
            return job
        
        job.status = JobStatus.FAILED
        job.completed_at = datetime.utcnow()
        job.error_message = error_message

        if job.docker_container_id:
            try:
                subprocess_module.run(
                    ["docker", "stop", job.docker_container_id],
                    capture_output=True,
                    timeout=30,
                )
            except Exception as e:
                logger.warning("failed_to_stop_container_on_failure", job_id=str(job.id), error=str(e))
        
        db.commit()
        db.refresh(job)
        
        logger.error(
            "job_failed",
            job_id=str(job.id),
            error=error_message,
        )

        # Trigger queue processing to start next pending job
        JobService.process_job_queue(db)

        return job


    @staticmethod
    def process_job_queue(db: Session) -> None:
        """
        Check for pending jobs and start the next one if capacity allows.
        
        This should be called whenever a job completes or fails.
        """
        try:
            # First, clean up any orphaned containers that might be blocking the queue
            JobService._cleanup_orphaned_containers(db)
            
            # Check current running jobs
            running_jobs = db.query(Job).filter(Job.status == JobStatus.RUNNING).count()
            # Import settings properly
            from backend.core.config import Settings
            settings = Settings()
            if running_jobs < settings.max_concurrent_jobs:
                pending_job = db.query(Job).filter(
                    Job.status == JobStatus.PENDING
                ).order_by(Job.created_at.asc()).with_for_update(skip_locked=True).first()
                
                if pending_job:
                    logger.info("starting_queued_job",
                              job_id=str(pending_job.id),
                              queue_position="next_pending",
                              environment=settings.environment)

                    # Mark job as RUNNING immediately while holding the lock
                    # This prevents race conditions and duplicate submissions
                    pending_job.status = JobStatus.RUNNING
                    pending_job.started_at = datetime.utcnow()  # Set timestamp when transitioning to RUNNING
                    db.commit()  # Commit and release lock

                    # Start the job using the appropriate method for the environment
                    try:
                        # Use desktop processing only in development/desktop environments
                        # unless Celery is explicitly forced.
                        if settings.environment in ["development", "desktop"] and not settings.force_celery:
                            # Use desktop-specific queue processing
                            from workers.tasks.processing_desktop import _start_next_pending_job
                            _start_next_pending_job(db)
                            logger.info("job_started_desktop_mode",
                                      job_id=str(pending_job.id),
                                      environment=settings.environment,
                                      max_concurrent=settings.max_concurrent_jobs)
                        else:
                            # Always use Celery/Redis in production; concurrency is still enforced above.
                            from workers.tasks.processing_web import process_mri_task
                            task = process_mri_task.delay(str(pending_job.id))
                            logger.info("job_started_celery_mode",
                                      job_id=str(pending_job.id),
                                      celery_task_id=task.id,
                                      max_concurrent=settings.max_concurrent_jobs)
                    except Exception as e:
                        logger.error("failed_to_start_queued_job",
                                   job_id=str(pending_job.id),
                                   environment=settings.environment,
                                   error=str(e))
        except Exception as e:
            logger.error("job_queue_processing_failed", error=str(e))
    
    @staticmethod
    def _cleanup_orphaned_containers(db: Session):
        """
        Find and remove FreeSurfer containers that have no corresponding database record.
        
        These "orphaned" containers can block new jobs from starting by consuming
        the concurrency limit even though they're not tracked in the database.
        
        Args:
            db: Database session
        """
        try:
            import subprocess
            from backend.core.config import Settings
            settings = Settings()
            
            # Get all FreeSurfer containers
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={settings.freesurfer_container_prefix}", 
                 "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logger.warning("failed_to_list_freesurfer_containers", 
                              stderr=result.stderr if result.stderr else "")
                return
            
            container_names = [name.strip() for name in result.stdout.strip().split('\n') if name.strip()]
            
            if not container_names:
                logger.debug("no_freesurfer_containers_found")
                return
            
            # Extract job IDs from container names
            prefix_len = len(settings.freesurfer_container_prefix)
            container_job_ids = {name[prefix_len:]: name for name in container_names}
            
            # Get all active job IDs from database
            active_jobs = db.query(Job.id).filter(
                Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING])
            ).all()
            active_job_ids = {str(job.id) for job in active_jobs}
            
            # Find orphaned containers (container exists but no active database record)
            orphaned_containers = {
                name: container_name 
                for name, container_name in container_job_ids.items() 
                if name not in active_job_ids
            }
            
            if orphaned_containers:
                logger.info("found_orphaned_containers", 
                           count=len(orphaned_containers),
                           containers=list(orphaned_containers.values()))
                
                # Remove each orphaned container
                for job_id, container_name in orphaned_containers.items():
                    try:
                        remove_result = subprocess.run(
                            ["docker", "rm", "-f", container_name],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if remove_result.returncode == 0:
                            logger.info("removed_orphaned_container", 
                                       job_id=job_id,
                                       container_name=container_name)
                        else:
                            logger.warning("failed_to_remove_orphaned_container",
                                          job_id=job_id,
                                          container_name=container_name,
                                          stderr=remove_result.stderr if remove_result.stderr else "")
                    except Exception as e:
                        logger.warning("error_removing_orphaned_container",
                                      job_id=job_id,
                                      container_name=container_name,
                                      error=str(e))
            else:
                logger.debug("no_orphaned_containers_found", 
                            active_containers=len(container_names),
                            active_jobs=len(active_job_ids))
                
        except Exception as e:
            logger.error("orphaned_container_cleanup_failed", error=str(e), exc_info=True)
    
    @staticmethod
    def _start_next_pending_job(db: Session):
        """
        Check for pending jobs and start the next one if no jobs are currently running.
        
        This is called automatically after a job completes, fails, or is deleted.
        
        Args:
            db: Database session
        """
        try:
            # First, clean up any orphaned containers that might be blocking the queue
            JobService._cleanup_orphaned_containers(db)
            
            # Check if there are any running jobs
            running_count = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
            
            if running_count > 0:
                logger.info("job_already_running_skipping_auto_start", running_count=running_count)
                return
            
            # Get the oldest pending job with row-level locking (FIFO queue)
            # with_for_update(skip_locked=True) ensures only one worker grabs this job
            pending_job = db.query(Job).filter(
                Job.status == JobStatus.PENDING
            ).with_for_update(skip_locked=True).order_by(Job.created_at.asc()).first()
            
            if not pending_job:
                logger.info("no_pending_jobs_to_auto_start")
                return
            
            # Mark job as RUNNING immediately while holding the lock
            # This prevents race conditions when multiple deletion/completion events trigger simultaneously
            pending_job.status = JobStatus.RUNNING
            pending_job.started_at = datetime.utcnow()  # Set timestamp when transitioning to RUNNING
            db.commit()  # Commit and release lock
            
            # Start the pending job
            logger.info("auto_starting_next_pending_job_after_completion",
                       job_id=str(pending_job.id),
                       filename=pending_job.filename)

            # Use the appropriate processing method based on environment
            from backend.core.config import Settings
            settings = Settings()

            if settings.environment in ["development", "desktop"] and not settings.force_celery:
                # Use desktop-specific queue processing
                from workers.tasks.processing_desktop import _start_next_pending_job
                _start_next_pending_job(db)
            else:
                # Submit to Celery queue
                from workers.tasks.processing_web import process_mri_task
                task = process_mri_task.delay(str(pending_job.id))
                logger.info("auto_started_pending_job_from_service",
                           job_id=str(pending_job.id),
                           celery_task_id=task.id,
                           filename=pending_job.filename)
            
        except Exception as e:
            logger.error("failed_to_auto_start_pending_job_from_service", error=str(e), exc_info=True)



