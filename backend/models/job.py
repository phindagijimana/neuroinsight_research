"""
Job Domain Model

Represents a neuroimaging pipeline execution job with complete lifecycle tracking.

JOB LIFECYCLE:
    pending -> running -> completed/failed/cancelled
"""
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class JobStatusEnum(str, PyEnum):
    """Job execution status enumeration.

    String-based enum for database storage and JSON serialization.
    Values match frontend JobStatus type for API consistency.
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Job Entity - Core Domain Model.

    Represents a neuroimaging pipeline execution job with full lifecycle tracking.
    Supports both local Docker and HPC SLURM execution backends.
    """
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, index=True, comment="Unique job identifier (UUID)")
    backend_type = Column(String(50), nullable=False, index=True, comment="Execution backend: local_docker or slurm")
    backend_job_id = Column(String(100), nullable=True, index=True, comment="Scheduler-specific job ID")
    pipeline_name = Column(String(100), nullable=False, index=True)
    pipeline_version = Column(String(20), nullable=True)
    container_image = Column(String(200), nullable=False)
    input_files = Column(JSON, nullable=False, comment="Array of input file paths")
    parameters = Column(JSON, nullable=False, comment="Pipeline execution parameters")
    resources = Column(JSON, nullable=False, comment="Computational resource allocation")
    status = Column(String(20), nullable=False, default=JobStatusEnum.PENDING.value, index=True, comment="Current execution status")
    progress = Column(Integer, nullable=False, default=0, comment="Estimated progress percentage (0-100)")
    current_phase = Column(String(120), nullable=True, comment="Current pipeline phase label")
    submitted_at = Column(DateTime, nullable=False, default=func.now(), index=True, comment="Job submission timestamp")
    started_at = Column(DateTime, nullable=True, comment="Execution start timestamp")
    completed_at = Column(DateTime, nullable=True, comment="Execution completion timestamp")
    output_dir = Column(String(500), nullable=False, comment="Path to job output directory")
    exit_code = Column(Integer, nullable=True, comment="Process exit code (0=success)")
    error_message = Column(Text, nullable=True, comment="Failure reason or error message")
    user_id = Column(String(100), nullable=True, index=True, comment="User ID (multi-user mode)")
    created_by = Column(String(100), nullable=True, comment="Job creator username")
    tags = Column(JSON, nullable=True, comment="User-defined tags (array of strings)")
    deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_status_submitted", "status", "submitted_at"),
        Index("idx_user_status", "user_id", "status"),
        Index("idx_deleted", "deleted"),
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id[:8]}... pipeline={self.pipeline_name} status={self.status} backend={self.backend_type}>"

    def __str__(self) -> str:
        return f"Job {self.id} ({self.pipeline_name}): {self.status}"

    @property
    def runtime_seconds(self) -> Optional[int]:
        """Calculate job runtime in seconds.

        For running jobs: start to now. For completed: start to completion.
        """
        if not self.started_at:
            return None
        end_time = self.completed_at if self.completed_at else datetime.now()
        return int((end_time - self.started_at).total_seconds())

    @property
    def runtime_formatted(self) -> str:
        """Get human-readable runtime string like '2h 34m 12s'."""
        secs = self.runtime_seconds
        if secs is None:
            return "Not started"
        td = timedelta(seconds=secs)
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        seconds = td.seconds % 60
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def is_terminal(self) -> bool:
        """Check if job is in terminal state (finished, cannot transition further)."""
        return self.status in (
            JobStatusEnum.COMPLETED.value,
            JobStatusEnum.FAILED.value,
            JobStatusEnum.CANCELLED.value,
        )

    @property
    def is_active(self) -> bool:
        """Check if job is currently active (pending or running)."""
        return self.status in (
            JobStatusEnum.PENDING.value,
            JobStatusEnum.RUNNING.value,
        )

    @property
    def succeeded(self) -> bool:
        """Check if job completed successfully."""
        return self.status == JobStatusEnum.COMPLETED.value and self.exit_code == 0

    @property
    def wait_time_seconds(self) -> Optional[int]:
        """Calculate time spent waiting in queue."""
        if not self.started_at:
            return None
        return int((self.started_at - self.submitted_at).total_seconds())

    @property
    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return not self.is_terminal

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == JobStatusEnum.FAILED.value

    def mark_started(self) -> None:
        """Mark job as started."""
        self.status = JobStatusEnum.RUNNING.value
        self.started_at = datetime.now()

    def mark_completed(self, exit_code: int = 0) -> None:
        """Mark job as completed."""
        self.status = JobStatusEnum.COMPLETED.value
        self.completed_at = datetime.now()
        self.exit_code = exit_code

    def mark_failed(self, error_message: str = "", exit_code: int = 1) -> None:
        """Mark job as failed."""
        self.status = JobStatusEnum.FAILED.value
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.exit_code = exit_code

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatusEnum.CANCELLED.value
        self.completed_at = datetime.now()

    def soft_delete(self) -> None:
        """Soft delete job (mark as deleted without removing from database)."""
        self.deleted = True
        self.deleted_at = datetime.now()

    def to_dict(self) -> dict:
        """Convert job to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "backend_type": self.backend_type,
            "backend_job_id": self.backend_job_id,
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "container_image": self.container_image,
            "input_files": self.input_files or [],
            "parameters": self.parameters or {},
            "resources": self.resources or {},
            "status": self.status,
            "progress": self.progress or 0,
            "current_phase": self.current_phase,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output_dir": self.output_dir,
            "exit_code": self.exit_code,
            "error_message": self.error_message,
            "runtime_seconds": self.runtime_seconds,
            "runtime_formatted": self.runtime_formatted,
            "user_id": self.user_id,
            "created_by": self.created_by,
            "tags": self.tags or [],
            "deleted": self.deleted,
        }

    @classmethod
    def from_spec(cls, job_id: str, backend_type: str, spec) -> "Job":
        """Create Job model from JobSpec.

        Args:
            job_id: Unique job identifier
            backend_type: Execution backend type
            spec: JobSpec from core.execution module
        """
        return cls(
            id=job_id,
            backend_type=backend_type,
            pipeline_name=spec.pipeline_name,
            container_image=spec.container_image,
            input_files=spec.input_files,
            parameters=spec.parameters,
            resources={
                "memory_gb": spec.resources.memory_gb,
                "cpus": spec.resources.cpus,
                "time_hours": spec.resources.time_hours,
                "gpu": spec.resources.gpu,
            },
            output_dir=spec.output_dir,
            status=JobStatusEnum.PENDING.value,
        )
