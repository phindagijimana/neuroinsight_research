"""
Execution Backend Abstraction Layer

Defines the core interface for job execution backends.
All backends (Local, SLURM, PBS, etc.) implement this interface,
allowing the application to be deployment-agnostic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path


class JobStatus(Enum):
    """Universal job status across all backends."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class ResourceSpec:
    """Computational resource requirements for a job."""
    memory_gb: int = 8
    cpus: int = 4
    time_hours: int = 6
    gpu: bool = False
    threads: Optional[int] = None
    omp_nthreads: Optional[int] = None
    parallel: bool = False


@dataclass
class JobSpec:
    """Complete specification for submitting a job."""
    pipeline_name: str
    container_image: str
    input_files: List[str]
    output_dir: str
    parameters: Dict = field(default_factory=dict)
    resources: ResourceSpec = field(default_factory=ResourceSpec)
    pipeline_version: Optional[str] = None
    workflow_id: Optional[str] = None
    plugin_id: Optional[str] = None
    execution_mode: str = "plugin"  # "plugin" or "workflow"


@dataclass
class JobInfo:
    """Detailed information about a job."""
    job_id: str
    status: JobStatus
    pipeline_name: str
    container_image: str = ""
    backend_job_id: Optional[str] = None
    progress: int = 0
    current_phase: Optional[str] = None
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    output_dir: Optional[str] = None


@dataclass
class JobLogs:
    """Job execution logs."""
    job_id: str
    stdout: str = ""
    stderr: str = ""


class ExecutionBackend(ABC):
    """
    Abstract interface for job execution backends.

    All backends (Local Docker, SLURM, PBS, etc.) must implement
    this interface to ensure consistent behavior across deployments.
    """

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return backend type identifier (e.g., 'local', 'slurm', 'pbs')."""
        pass

    @abstractmethod
    def submit_job(self, spec: JobSpec, job_id: Optional[str] = None) -> str:
        """Submit a job for execution.

        Args:
            spec: Job specification with all required information
            job_id: Optional pre-generated job ID

        Returns:
            job_id: Internal job identifier (UUID)

        Raises:
            ExecutionError: If job submission fails
        """
        pass

    @abstractmethod
    def get_job_status(self, job_id: str) -> JobStatus:
        """Query current job status.

        Args:
            job_id: Internal job identifier

        Returns:
            Current job status

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass

    @abstractmethod
    def get_job_info(self, job_id: str) -> JobInfo:
        """Get detailed job information.

        Args:
            job_id: Internal job identifier

        Returns:
            Complete job information including status, timing, etc.
        """
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job.

        Returns:
            True if cancellation successful, False otherwise
        """
        pass

    @abstractmethod
    def get_job_logs(self, job_id: str) -> JobLogs:
        """Retrieve job logs (stdout/stderr)."""
        pass

    @abstractmethod
    def list_jobs(self, status_filter: Optional[List[str]] = None, limit: int = 100) -> List[JobInfo]:
        """List jobs with optional filtering."""
        pass

    @abstractmethod
    def cleanup_job(self, job_id: str) -> bool:
        """Clean up job resources (containers, temp files, etc.)."""
        pass

    @abstractmethod
    def health_check(self) -> dict:
        """Check backend health and availability.

        Returns:
            Dictionary with: healthy (bool), message (str), details (dict)
        """
        pass


class ExecutionError(Exception):
    """Base exception for execution backend errors."""
    pass


class JobNotFoundError(ExecutionError):
    """Raised when requested job doesn't exist."""
    pass


class BackendUnavailableError(ExecutionError):
    """Raised when execution backend is unavailable."""
    pass


class ResourceError(ExecutionError):
    """Raised when requested resources are unavailable."""
    pass
