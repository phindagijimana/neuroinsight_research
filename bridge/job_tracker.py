"""
Job Tracker for FreeSurfer API Bridge

This module tracks the status and progress of FreeSurfer processing jobs:
- Maintains job state in memory (could be extended to database)
- Updates progress information
- Stores final results
- Provides status queries

This provides a clean interface for monitoring long-running FreeSurfer processes.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    """Enumeration of possible job statuses"""
    PENDING = "pending"
    STARTING = "starting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class JobInfo:
    """Data class for job information"""
    job_id: str
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    message: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    input_file: Optional[str] = None
    output_dir: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert job info to dictionary for API responses"""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "start_time": datetime.fromtimestamp(self.start_time) if self.start_time else None,
            "end_time": datetime.fromtimestamp(self.end_time) if self.end_time else None,
            "container_id": self.container_id,
            "container_status": self._get_container_status(),
            "processing_time": self.processing_time
        }

    def _get_container_status(self) -> Optional[str]:
        """Get simplified container status"""
        if self.container_id and self.status in [JobStatus.PROCESSING, JobStatus.COMPLETED]:
            return "running" if self.status == JobStatus.PROCESSING else "exited"
        return None

class JobTracker:
    """
    Tracks FreeSurfer processing jobs

    This class maintains an in-memory store of job information.
    In a production system, this would be backed by a database like Redis or PostgreSQL.
    """

    def __init__(self):
        """Initialize job tracker"""
        self.jobs: Dict[str, JobInfo] = {}
        logger.info("Job tracker initialized")

    def create_job(self, job_id: str, input_file: str, output_dir: str) -> JobInfo:
        """
        Create a new job entry

        Args:
            job_id: Unique job identifier
            input_file: Path to input MRI file
            output_dir: Directory for output results

        Returns:
            JobInfo object for the new job
        """
        job = JobInfo(
            job_id=job_id,
            status=JobStatus.PENDING,
            progress=0.0,
            message="Job created, waiting to start",
            input_file=input_file,
            output_dir=output_dir
        )

        self.jobs[job_id] = job
        logger.info(f"Created job {job_id}")
        return job

    def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        message: str
    ) -> bool:
        """
        Update job status and progress

        Args:
            job_id: Job identifier
            status: New status string
            progress: Progress percentage (0.0 to 1.0)
            message: Status message

        Returns:
            True if update was successful
        """
        try:
            if job_id not in self.jobs:
                logger.warning(f"Attempted to update unknown job {job_id}")
                return False

            job = self.jobs[job_id]

            # Convert string status to enum
            try:
                job.status = JobStatus(status.lower())
            except ValueError:
                logger.warning(f"Invalid status '{status}' for job {job_id}, keeping current")
                return False

            job.progress = max(0.0, min(1.0, progress))  # Clamp to 0-1
            job.message = message

            # Set timestamps
            if job.status == JobStatus.PROCESSING and not job.start_time:
                job.start_time = time.time()
            elif job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if not job.end_time:
                    job.end_time = time.time()
                    if job.start_time:
                        job.processing_time = job.end_time - job.start_time

            logger.info(f"Updated job {job_id}: {job.status.value} ({job.progress:.1%}) - {message}")
            return True

        except Exception as e:
            logger.error(f"Error updating job {job_id}: {e}")
            return False

    def update_container_info(self, job_id: str, container_info: Dict[str, Any]) -> bool:
        """
        Update job with container information

        Args:
            job_id: Job identifier
            container_info: Dictionary with container details

        Returns:
            True if update was successful
        """
        try:
            if job_id not in self.jobs:
                logger.warning(f"Attempted to update container info for unknown job {job_id}")
                return False

            job = self.jobs[job_id]
            job.container_id = container_info.get("container_id")
            job.container_name = container_info.get("container_name")

            # Update status to starting when container is created
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.STARTING
                job.message = "FreeSurfer container starting"

            logger.info(f"Updated container info for job {job_id}: {job.container_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating container info for job {job_id}: {e}")
            return False

    def complete_job(self, job_id: str, results: Dict[str, Any]) -> bool:
        """
        Mark job as completed with results

        Args:
            job_id: Job identifier
            results: Processing results dictionary

        Returns:
            True if completion was successful
        """
        try:
            if job_id not in self.jobs:
                logger.warning(f"Attempted to complete unknown job {job_id}")
                return False

            job = self.jobs[job_id]
            job.status = JobStatus.COMPLETED
            job.progress = 1.0
            job.message = "Processing completed successfully"
            job.results = results
            job.end_time = time.time()

            if job.start_time:
                job.processing_time = job.end_time - job.start_time

            logger.info(f"Completed job {job_id} in {job.processing_time:.1f}s")
            return True

        except Exception as e:
            logger.error(f"Error completing job {job_id}: {e}")
            return False

    def fail_job(self, job_id: str, error_message: str) -> bool:
        """
        Mark job as failed

        Args:
            job_id: Job identifier
            error_message: Error description

        Returns:
            True if failure was recorded successfully
        """
        try:
            if job_id not in self.jobs:
                logger.warning(f"Attempted to fail unknown job {job_id}")
                return False

            job = self.jobs[job_id]
            job.status = JobStatus.FAILED
            job.message = f"Processing failed: {error_message}"
            job.error = error_message
            job.end_time = time.time()

            if job.start_time:
                job.processing_time = job.end_time - job.start_time

            logger.error(f"Job {job_id} failed: {error_message}")
            return True

        except Exception as e:
            logger.error(f"Error failing job {job_id}: {e}")
            return False

    def cancel_job(self, job_id: str) -> bool:
        """
        Mark job as cancelled

        Args:
            job_id: Job identifier

        Returns:
            True if cancellation was recorded successfully
        """
        try:
            if job_id not in self.jobs:
                logger.warning(f"Attempted to cancel unknown job {job_id}")
                return False

            job = self.jobs[job_id]
            job.status = JobStatus.CANCELLED
            job.message = "Job cancelled by user"
            job.end_time = time.time()

            if job.start_time:
                job.processing_time = job.end_time - job.start_time

            logger.info(f"Cancelled job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a job

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job status information, or None if job not found
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        return job.to_dict()

    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get results of a completed job

        Args:
            job_id: Job identifier

        Returns:
            Dictionary with job results, or None if job not found or not completed
        """
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]

        if job.status != JobStatus.COMPLETED:
            return None

        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "results": job.results,
            "processing_time": job.processing_time,
            "input_file": job.input_file,
            "output_dir": job.output_dir
        }

    def list_jobs(self, status_filter: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        List all jobs, optionally filtered by status

        Args:
            status_filter: Optional status to filter by

        Returns:
            Dictionary mapping job_id to job status info
        """
        jobs_info = {}

        for job_id, job in self.jobs.items():
            if status_filter and job.status.value != status_filter:
                continue

            jobs_info[job_id] = job.to_dict()

        return jobs_info

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed/failed jobs

        Args:
            max_age_hours: Maximum age in hours for cleanup

        Returns:
            Number of jobs cleaned up
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        jobs_to_remove = []

        for job_id, job in self.jobs.items():
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                if job.end_time and (current_time - job.end_time) > max_age_seconds:
                    jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            logger.info(f"Cleaned up old job {job_id}")

        return len(jobs_to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get job tracker statistics

        Returns:
            Dictionary with job statistics
        """
        total_jobs = len(self.jobs)
        status_counts = {}

        for job in self.jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_jobs": total_jobs,
            "status_counts": status_counts,
            "active_jobs": status_counts.get("processing", 0) + status_counts.get("starting", 0)
        }
