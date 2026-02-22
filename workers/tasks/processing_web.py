"""
Production MRI processing with Celery.

This module provides Celery-based processing tasks for production web deployment.
Uses Redis as message broker and result backend.
"""

import os
import time
from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.core.logging import get_logger
from backend.models.job import Job, JobStatus
from backend.services import JobService, MetricService, StorageService
from pipeline.processors import MRIProcessor

# Celery imports
from celery import Celery

logger = get_logger(__name__)
settings = get_settings()

# Initialize Celery app
# Try Redis first, fallback to SQLite
# Use localhost for native deployment (host can't resolve 'redis' hostname)
# No password for local development (Redis container has no password set)
broker_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
backend_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def test_redis_connection(url):
    """Test Redis connection and return True if successful."""
    try:
        import redis
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 6379
        password = parsed.password

        r = redis.Redis(host=host, port=port, password=password)
        r.ping()
        return True
    except Exception as e:
        print(f"Redis connection test failed: {e}")
        return False

# Test Redis connection at startup
if test_redis_connection(broker_url):
        print("Using Redis broker")
else:
    print("Redis not available, using SQLite broker")
    # Use SQLite broker as fallback
    broker_url = "sqlalchemy+sqlite:///celery_broker.db"
    backend_url = "db+sqlite:///celery_results.db"

celery_app = Celery(
    "neuroinsight",
    broker=broker_url,
    backend=backend_url,
    include=["workers.tasks.processing_web"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=36000,  # 10 hours
    task_soft_time_limit=32400,  # 9 hours
    worker_prefetch_multiplier=1,  # One task per worker
    worker_max_tasks_per_child=1,  # Restart worker after each task
)


def update_job_progress(db: Session, job_id, progress: int, current_step: str):
    """
    Update job progress and current step description.

    Args:
        db: Database session
        job_id: Job identifier (string or UUID - will be converted to string for SQLite)
        progress: Progress percentage (0-100)
        current_step: Description of current processing step
    """
    try:
        # Ensure job_id is string format (for SQLite VARCHAR(36) with dashes)
        job_id_str = str(job_id)

        db.execute(
            update(Job)
            .where(Job.id == job_id_str)
            .values(progress=progress, current_step=current_step)
        )
        db.commit()
        logger.info("progress_updated", job_id=job_id_str, progress=progress, step=current_step)
    except Exception as e:
        logger.warning("progress_update_failed", job_id=str(job_id), error=str(e))
        db.rollback()


def fail_job_sync(job_id: str, error_message: str):
    """
    Synchronously mark a job as failed from progress monitor thread.
    
    This is a helper function for the progress monitor to fail jobs immediately
    when critical errors are detected (e.g., directory deleted, container crashed).
    
    Args:
        job_id: Job identifier string
        error_message: Error message describing why job failed
    """
    db = SessionLocal()
    try:
        job_service = JobService()
        job_service.fail_job(db, job_id, error_message)
        logger.info("job_failed_by_monitor", job_id=job_id, reason=error_message[:100])
    except Exception as e:
        logger.error("failed_to_fail_job_from_monitor", job_id=job_id, error=str(e))
        db.rollback()
    finally:
        db.close()


def start_next_pending_job(db: Session):
    """
    Check for pending jobs and start the next one if no jobs are currently running.
    
    This ensures automatic job progression after a job completes or fails.
    Uses database-level row locking to prevent race conditions when multiple
    workers try to start the same job simultaneously.
    
    The row lock ensures only one worker can select a given PENDING job.
    The job status is updated to RUNNING by process_mri_task() itself,
    not here, to avoid conflicts with the idempotency check.
    
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
        # Other workers will skip to the next available job or return None
        pending_job = db.query(Job).filter(
            Job.status == JobStatus.PENDING
        ).with_for_update(skip_locked=True).order_by(Job.created_at.asc()).first()
        
        if not pending_job:
            logger.info("no_pending_jobs_found")
            return
        
        # Mark job as RUNNING immediately while holding the lock
        # This prevents other workers from selecting this job in concurrent start_next_pending_job calls
        # The row lock + status change ensures atomic job selection
        pending_job.status = JobStatus.RUNNING
        pending_job.started_at = datetime.utcnow()  # Set timestamp when transitioning to RUNNING
        db.commit()  # Commit and release lock
        
        logger.info("submitting_job_to_celery", job_id=str(pending_job.id), filename=pending_job.filename)
        
        # Submit to Celery - task has idempotency check in case this fails
        task = process_mri_task.delay(str(pending_job.id))
        logger.info("job_submitted_to_celery", 
                   job_id=str(pending_job.id), 
                   celery_task_id=task.id,
                   filename=pending_job.filename)
        
    except Exception as e:
        logger.error("failed_to_submit_job_to_celery", error=str(e), exc_info=True)
        db.rollback()


@celery_app.task(bind=True, name="process_mri_task")
def process_mri_task(self, job_id: str):
    """
    Celery task for processing MRI data.

    Args:
        job_id: UUID string of the job to process

    Returns:
        Dict with processing results
    """
    logger.info("celery_task_started", job_id=job_id, task_id=self.request.id)

    db = SessionLocal()
    try:
        # Get job details
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Idempotency check: Only process if job is PENDING or RUNNING (but not already processed)
        # RUNNING is acceptable because process_job_queue marks it as RUNNING before submission
        # This prevents duplicate tasks from processing the same job
        if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            logger.warning("job_already_processed",
                          job_id=job_id,
                          current_status=job.status.value,
                          task_id=self.request.id,
                          message="Skipping duplicate task - job is not PENDING or RUNNING")
            return {
                'status': 'skipped',
                'reason': f'Job already in {job.status.value} status',
                'job_id': job_id
            }

        # Update job status to running (if it's still PENDING)
        # If already RUNNING from queue, started_at is already set
        if job.status == JobStatus.PENDING:
            JobService.start_job(db, job_id)
        elif job.status == JobStatus.RUNNING and not job.started_at:
            # Edge case: job marked as RUNNING but started_at missing
            # (shouldn't happen with process_job_queue fix, but defensive)
            job.started_at = datetime.utcnow()
            db.commit()
            logger.info("job_started_at_set_by_worker", job_id=job_id)

        # Check container concurrency limits BEFORE starting processing
        # This prevents jobs from starting when FreeSurfer containers are already at capacity
        try:
            from pipeline.processors import MRIProcessor
            processor = MRIProcessor(job_id=job_id, db_session=db, progress_callback=lambda p, s: None)
            processor._check_container_concurrency_limit()
            logger.info("container_concurrency_check_passed", job_id=job_id)
        except RuntimeError as concurrency_error:
            # Concurrency limit exceeded - fail the job with clear error message
            error_msg = str(concurrency_error)
            logger.warning("job_failed_concurrency_limit",
                          job_id=job_id,
                          error=error_msg)

            # Update job status to failed
            JobService.fail_job(db, job_id, error_msg)

            # Don't start processing - exit early
            return {
                "status": "failed",
                "job_id": job_id,
                "error": error_msg
            }

        # Update progress
        update_job_progress(db, job_id, 5, "Initializing MRI processor")

        # Define progress callback for detailed tracking (5% increments)
        last_reported_progress = 5

        def progress_callback(progress: int, step: str):
            """Callback for processor to update job progress in 5% increments."""
            nonlocal last_reported_progress

            # Only update if progress increased by at least 5%
            if progress >= last_reported_progress + 5 or progress >= 100:
                update_job_progress(db, job_id, progress, step)
                last_reported_progress = progress
                logger.info(
                    "processing_progress",
                    job_id=job_id,
                    progress=progress,
                    step=step
                )

        # Initialize MRI processor with progress callback and database session
        print(f"DEBUG: Celery task initializing MRI processor for job {job_id}")
        # Job IDs are 8-character strings, not UUIDs
        processor = MRIProcessor(job_id=job_id, progress_callback=progress_callback, db_session=db)
        print(f"DEBUG: MRI processor initialized for job {job_id}")
        logger.info("processor_initialized", job_id=job_id)

        update_job_progress(db, job_id, 10, "Loading and validating input data")

        # Process the MRI data
        logger.info("celery_processor_process_start", job_id=job_id, file_path=job.file_path)
        try:
            results = processor.process(job.file_path)
            logger.info("celery_processor_process_success",
                       job_id=job_id,
                       results_keys=list(results.keys()) if results else None,
                       has_output_dir='output_dir' in results if results else False)
        except Exception as process_error:
            print(f"DEBUG: processor.process() failed for job {job_id}: {str(process_error)}")
            logger.error("processor_process_failed", job_id=job_id, error=str(process_error), exc_info=True)

            # Don't call fail_job here - let the outer exception handler do it
            # This prevents duplicate fail_job calls and multiple queue processing attempts
            
            # Re-raise the exception to fail the Celery task
            raise process_error

        update_job_progress(db, job_id, 90, "Extracting metrics and generating visualizations")

        # Extract metrics if processing was successful
        if results and "output_dir" in results:
            try:
                metrics = MetricService.extract_metrics(db, job_id, results["output_dir"])
                logger.info("metrics_extracted", job_id=job_id, metrics_count=len(metrics))
            except Exception as e:
                logger.warning("metrics_extraction_failed", job_id=job_id, error=str(e))

        update_job_progress(db, job_id, 95, "Finalizing results")


        # Update job with results and visualization URLs
        JobService.complete_job(
            db,
            job_id,
            results.get("output_dir"),
            JobService.build_visualization_payload(job_id)
        )

        update_job_progress(db, job_id, 100, "Processing completed successfully")

        logger.info("celery_task_completed", job_id=job_id, results=results)

        return {
            "status": "completed",
            "job_id": job_id,
            "output_dir": results.get("output_dir"),
            "metrics_count": len(metrics) if 'metrics' in locals() else 0
        }

    except Exception as e:
        logger.error("celery_task_failed", job_id=job_id, error=str(e), exc_info=True)

        # Update job status to failed
        try:
            JobService.fail_job(db, job_id, str(e))
        except Exception as db_error:
            logger.error("job_status_update_failed", job_id=job_id, error=str(db_error))

        # Re-raise the exception for Celery
        raise

    finally:
        # Ensure container cleanup happens regardless of failure point
        try:
            from pipeline.processors import MRIProcessor
            cleanup_processor = MRIProcessor(job_id=job_id, db_session=None, progress_callback=None)
            cleanup_processor._cleanup_job_containers()
            logger.info("container_cleanup_completed", job_id=job_id)
        except Exception as cleanup_error:
            logger.warning("container_cleanup_failed_in_finally",
                          job_id=job_id,
                          error=str(cleanup_error))

        # Close database session
        try:
            db.close()
            logger.info("db_session_closed", job_id=job_id)
        except Exception as db_close_error:
            logger.error("db_close_failed", 
                        job_id=job_id,
                        error=str(db_close_error))

        # Note: Next job is automatically started by JobService.fail_job() or JobService.complete_job()
        # No need to call start_next_pending_job here to avoid duplicate submissions


@celery_app.task(name="health_check")
def health_check():
    """Simple health check task."""
    return {"status": "healthy", "timestamp": time.time()}


@celery_app.task(name="check_pending_jobs")
def check_pending_jobs():
    """
    Periodic task to check for pending jobs and start them if no jobs are running.
    
    This prevents orphaned pending jobs when:
    - A running job gets stuck and is manually marked as failed
    - Worker restarts occur
    - Auto-start mechanism fails for any reason
    
    Runs every 60 seconds via Celery Beat.
    """
    db = SessionLocal()
    try:
        # Check if there are any running jobs
        running_count = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
        
        if running_count > 0:
            logger.debug("periodic_check_skipped_job_running", running_count=running_count)
            return {"status": "skipped", "reason": "job_already_running", "running_count": running_count}
        
        # Check for pending jobs
        pending_count = JobService.count_jobs_by_status(db, [JobStatus.PENDING])
        
        if pending_count == 0:
            logger.debug("periodic_check_no_pending_jobs")
            return {"status": "ok", "pending_count": 0}
        
        # Try to start next pending job
        logger.info("periodic_check_starting_pending_job", pending_count=pending_count)
        start_next_pending_job(db)
        
        return {"status": "started", "pending_count": pending_count}
        
    except Exception as e:
        logger.error("periodic_check_failed", error=str(e), exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        db.close()


# Configure Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'check-pending-jobs-every-60-seconds': {
        'task': 'check_pending_jobs',
        'schedule': 60.0,  # Run every 60 seconds
    },
}
celery_app.conf.timezone = 'UTC'


