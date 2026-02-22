"""
Job Queue Processor for Desktop Mode.

Continuously monitors for PENDING jobs and processes them when no jobs are running.
This replaces the missing Celery worker functionality for desktop applications.
"""

import time
import threading
from typing import Optional

from sqlalchemy.orm import Session
from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.core.logging import get_logger
from backend.models.job import JobStatus
from backend.services import JobService
from backend.services.task_service import TaskService

logger = get_logger(__name__)
settings = get_settings()


class JobQueueProcessor:
    """Background job queue processor for desktop mode."""

    def __init__(self):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.check_interval = 5  # Check for pending jobs every 5 seconds

    def start(self):
        """Start the job queue processor in a background thread."""
        if self.running:
            logger.warning("Job queue processor is already running")
            return

        logger.info("Starting job queue processor")
        self.running = True
        self.thread = threading.Thread(
            target=self._process_queue,
            name="job-queue-processor",
            daemon=True
        )
        self.thread.start()

    def stop(self):
        """Stop the job queue processor."""
        logger.info("Stopping job queue processor")
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)

    def _process_queue(self):
        """Main queue processing loop."""
        logger.info("Job queue processor started")

        while self.running:
            try:
                self._check_and_process_pending_jobs()
            except Exception as e:
                logger.error("Error in job queue processor", error=str(e), exc_info=True)

            # Wait before next check
            time.sleep(self.check_interval)

        logger.info("Job queue processor stopped")

    def _check_and_process_pending_jobs(self):
        """Check for pending jobs and start processing if possible."""
        db: Session = SessionLocal()

        try:
            # Count running jobs
            running_jobs = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])

            if running_jobs > 0:
                # There's already a job running, don't start another
                return

            # Find the oldest pending job
            pending_job = JobService.get_oldest_pending_job(db)

            if pending_job:
                logger.info("Found pending job, starting processing", job_id=str(pending_job.id))
                self._start_job_processing(pending_job.id)
            else:
                # No pending jobs, nothing to do
                pass

        except Exception as e:
            logger.error("Error checking pending jobs", error=str(e))
        finally:
            db.close()

    def _start_job_processing(self, job_id):
        """Start processing a pending job."""
        try:
            from workers.tasks.processing_desktop import process_mri_direct

            def process_async():
                db: Session = SessionLocal()
                try:
                    # Mark job as running
                    JobService.start_job(db, str(job_id))

                    logger.info("Starting job processing", job_id=str(job_id))
                    result = process_mri_direct(str(job_id))
                    logger.info("Job processing completed", job_id=str(job_id), result=result)

                except Exception as e:
                    logger.error("Job processing failed", job_id=str(job_id), error=str(e), exc_info=True)
                finally:
                    db.close()

            # Submit to task service
            TaskService.submit_task(process_async)
            logger.info("Job submitted for processing", job_id=str(job_id))

        except Exception as e:
            logger.error("Failed to start job processing", job_id=str(job_id), error=str(e))


# Global processor instance
_processor_instance: Optional[JobQueueProcessor] = None


def start_job_queue_processor():
    """Start the global job queue processor."""
    global _processor_instance

    if settings.environment == "production" or settings.force_celery:
        logger.info(
            "job_queue_processor_disabled",
            environment=settings.environment,
            force_celery=settings.force_celery,
        )
        return

    if _processor_instance is None:
        _processor_instance = JobQueueProcessor()

    _processor_instance.start()
    logger.info("Job queue processor started globally")


def stop_job_queue_processor():
    """Stop the global job queue processor."""
    global _processor_instance

    if _processor_instance:
        _processor_instance.stop()
        _processor_instance = None
        logger.info("Job queue processor stopped globally")


def get_processor_status():
    """Get the status of the job queue processor."""
    global _processor_instance

    if _processor_instance and _processor_instance.running:
        return {
            "status": "running",
            "check_interval": _processor_instance.check_interval,
            "thread_alive": _processor_instance.thread.is_alive() if _processor_instance.thread else False
        }
    else:
        return {
            "status": "stopped"
        }
