
'''
Execution Backend Abstraction Layer

This module defines the core interface for job execution backends.
All backends (Local, SLURM, PBS, etc.) implement this interface,
allowing the application to be deployment-agnostic.
'''
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pathlib import Path

class JobStatus(Enum):
    '''Universal job status across all backends'''
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    UNKNOWN = 'unknown'

# NOTE: ResourceSpec dataclass def inition (decompiler artifact - see original)
# NOTE: JobSpec dataclass def inition (decompiler artifact - see original)
# NOTE: JobInfo dataclass def inition (decompiler artifact - see original)
# NOTE: JobLogs dataclass def inition (decompiler artifact - see original)

class ExecutionBackend(ABC):
    """
    Abstract interface for job execution backends.
    
    All backends (Local Docker, SLURM, PBS, etc.) must implement
    this interface to ensure consistent behavior across deployments.
    
    Design Philosophy:
    - Backend-agnostic: Application code doesn't care where jobs run
    - Path-agnostic: Paths can be local or remote
    - Status-agnostic: Common status model across all schedulers
    """
    
    def backend_type(self = None):
        """Return backend type identifier (e.g., 'local', 'slurm', 'pbs')"""
        pass

    # backend_type = property(backend_type)  # decompiler artifact
    
    def submit_job(self = None, spec = None, job_id = abstractmethod):
        '''
        Submit a job for execution.
        
        Args:
            spec: Job specification with all required information
            job_id: Optional pre-generated job ID. If None, backend generates one.
            
        Returns:
            job_id: Internal job identifier (UUID)
            
        Raises:
            ExecutionError: If job submission fails
        '''
        pass

    submit_job = None(submit_job)
    
    def get_job_status(self = None, job_id = None):
        """
        Query current job status.
        
        Args:
            job_id: Internal job identifier
            
        Returns:
            Current job status
            
        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass

    get_job_status = None(get_job_status)
    
    def get_job_info(self = None, job_id = None):
        """
        Get detailed job information.
        
        Args:
            job_id: Internal job identifier
            
        Returns:
            Complete job information including status, timing, etc.
            
        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass

    get_job_info = None(get_job_info)
    
    def cancel_job(self = None, job_id = None):
        """
        Cancel a running or pending job.
        
        Args:
            job_id: Internal job identifier
            
        Returns:
            True if cancellation successful, False otherwise
            
        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass

    cancel_job = None(cancel_job)
    
    def get_job_logs(self = None, job_id = None):
        """
        Retrieve job logs (stdout/stderr).
        
        Args:
            job_id: Internal job identifier
            
        Returns:
            JobLogs with stdout and stderr
            
        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass

    get_job_logs = None(get_job_logs)
    
    def list_jobs(self = None, status_filter = None, limit = abstractmethod):
        '''
        List jobs with optional filtering.
        
        Args:
            status_filter: Optional list of statuses to filter by
            limit: Maximum number of jobs to return
            
        Returns:
            List of job information objects
        '''
        pass

    list_jobs = None(list_jobs)
    
    def cleanup_job(self = None, job_id = None):
        '''
        Clean up job resources (containers, temp files, etc.).
        
        Args:
            job_id: Internal job identifier
            
        Returns:
            True if cleanup successful, False otherwise
        '''
        pass

    cleanup_job = None(cleanup_job)
    
    def health_check(self = None):
        '''
        Check backend health and availability.
        
        Returns:
            Dictionary with health status information:
            - healthy: bool
            - message: str
            - details: dict (backend-specific)
        '''
        pass

    health_check = None(health_check)


class ExecutionError(Exception):
    '''Base exception for execution backend errors'''
    pass


class JobNotFoundError(ExecutionError):
    """Raised when requested job doesn't exist"""
    pass


class BackendUnavailableError(ExecutionError):
    '''Raised when execution backend is unavailable'''
    pass


class ResourceError(ExecutionError):
    '''Raised when requested resources are unavailable'''
    pass

