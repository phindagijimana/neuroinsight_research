
'''
Job Domain Model

Represents a neuroimaging pipeline execution job with complete lifecycle tracking.

DATABASE SCHEMA:
- Single table design with JSON columns for flexibility
- Soft delete support (deleted flag, not actual deletion)
- Indexed on status and submitted_at for efficient queries
- Timing columns for performance analysis

JOB LIFECYCLE:
    pending -> running -> completed/failed/cancelled
    
State Transitions:
1. PENDING: Job submitted, waiting for execution
2. RUNNING: Job is actively executing
3. COMPLETED: Job finished successfully (exit_code = 0)
4. FAILED: Job finished with error (exit_code != 0)
5. CANCELLED: User cancelled before completion

Only forward transitions allowed (no retry states in v1.0).

USAGE PATTERNS:

1. Create new job:
    job = Job(
        id=str(uuid.uuid4()),
        backend_type="local_docker",
        pipeline_name="freesurfer_hippocampus",
        input_files=["/data/T1.nii.gz"],
        parameters={"threads": 8},
        resources={"memory_gb": 32, "cpus": 8},
        status=JobStatusEnum.PENDING,
        output_dir="/results/job-123"
    )
    db.add(job)
    db.commit()

2. Query jobs:
    # Get all running jobs
    running = db.query(Job).filter(
        Job.status == JobStatusEnum.RUNNING
    ).all()
    
    # Get recent completed jobs
    completed = db.query(Job).filter(
        Job.status == JobStatusEnum.COMPLETED
    ).order_by(Job.completed_at.desc()).limit(10).all()

3. Update job status:
    job = db.query(Job).filter_by(id=job_id).first()
    job.status = JobStatusEnum.RUNNING
    job.started_at = datetime.now()
    db.commit()

INDEXING STRATEGY:
- Primary key: id (UUID, clustered)
- Index on: (status, submitted_at) for dashboard queries
- Index on: backend_job_id for scheduler lookups
- Index on: deleted for soft delete filtering
'''
from datetime import datetime, timedelta
from enum import Enum as PyEnum
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
Base = declarative_base()

class JobStatusEnum(PyEnum, str):
    '''
    Job execution status enumeration
    
    String-based enum for database storage and JSON serialization.
    Values match frontend JobStatus type for API consistency.
    '''
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class Job(Base):
    """
    Job Entity - Core Domain Model
    
    Represents a neuroimaging pipeline execution job with full lifecycle tracking.
    Supports both local Docker and HPC SLURM execution backends.
    
    Design Principles:
    - Backend-agnostic: Same model works for local and HPC
    - Immutable specification: input_files, parameters stored at submission
    - Audit trail: All timestamps preserved for analysis
    - Soft deletes: Preserve history, don't actually delete rows
    
    JSON Columns:
    - input_files: Array of strings (file paths)
    - parameters: Object (parameter name -> value)
    - resources: Object (memory_gb, cpus, time_hours, gpu)
    - tags: Optional array of strings (user-defined labels)
    """
    __tablename__ = 'jobs'
    id = Column(String(36), True, True, 'Unique job identifier (UUID)', **('primary_key', 'index', 'comment'))
    backend_type = Column(String(50), False, True, 'Execution backend: local_docker or slurm', **('nullable', 'index', 'comment'))
    backend_job_id = Column(String(100), True, True, 'Scheduler-specific job ID (container ID or SLURM job number)', **('nullable', 'index', 'comment'))
    pipeline_name = Column(String(100), False, True, **('nullable', 'index'))
    pipeline_version = Column(String(20), True, **('nullable',))
    container_image = Column(String(200), False, **('nullable',))
    input_files = Column(JSON, False, 'Array of input file paths', **('nullable', 'comment'))
    parameters = Column(JSON, False, 'Pipeline execution parameters', **('nullable', 'comment'))
    resources = Column(JSON, False, 'Computational resource allocation', **('nullable', 'comment'))
    status = Column(String(20), False, JobStatusEnum.PENDING.value, True, 'Current execution status', **('nullable', 'default', 'index', 'comment'))
    progress = Column(Integer, False, 0, 'Estimated progress percentage (0-100)', **('nullable', 'default', 'comment'))
    current_phase = Column(String(120), True, 'Current pipeline phase label', **('nullable', 'comment'))
    submitted_at = Column(DateTime, False, func.now(), True, 'Job submission timestamp', **('nullable', 'default', 'index', 'comment'))
    started_at = Column(DateTime, True, 'Execution start timestamp', **('nullable', 'comment'))
    completed_at = Column(DateTime, True, 'Execution completion timestamp', **('nullable', 'comment'))
    output_dir = Column(String(500), False, 'Path to job output directory (local or HPC)', **('nullable', 'comment'))
    exit_code = Column(Integer, True, 'Process exit code (0=success)', **('nullable', 'comment'))
    error_message = Column(Text, True, 'Failure reason or error message', **('nullable', 'comment'))
    user_id = Column(String(100), True, True, 'User ID (multi-user mode)', **('nullable', 'index', 'comment'))
    created_by = Column(String(100), True, 'Job creator username', **('nullable', 'comment'))
    tags = Column(JSON, True, 'User-defined tags (array of strings)', **('nullable', 'comment'))
    deleted = Column(Boolean, False, False, True, **('default', 'nullable', 'index'))
    deleted_at = Column(DateTime, True, **('nullable',))
    __table_args__ = (Index('idx_status_submitted', 'status', 'submitted_at'), Index('idx_user_status', 'user_id', 'status'), Index('idx_deleted', 'deleted'))
    
    def __repr__(self = None):
        '''String representation for logging and debugging'''
        return f'''<Job id={self.id[:8]}... pipeline={self.pipeline_name} status={self.status.value} backend={self.backend_type}>'''

    
    def __str__(self = None):
        '''Human-readable string representation'''
        return f'''Job {self.id} ({self.pipeline_name}): {self.status.value}'''

    
    def runtime_seconds(self = None):
        '''
        Calculate job runtime in seconds
        
        Returns:
            Runtime in seconds if job has started, None otherwise
            
        Note:
            For running jobs, calculates from start to current time.
            For completed jobs, calculates from start to completion.
        '''
        if not self.started_at:
            return None
        if not None.completed_at:
            pass
        end_time = datetime.now()
        return int((end_time - self.started_at).total_seconds())

    runtime_seconds = None(runtime_seconds)
    
    def runtime_formatted(self = None):
        '''
        Get human-readable runtime string
        
        Returns:
            Formatted string like "2h 34m 12s" or "Not started"
            
        Example:
            print(f"Job ran for: {job.runtime_formatted}")
            # Output: "Job ran for: 5h 32m 18s"
        '''
        if not self.runtime_seconds:
            return 'Not started'
        td = None(self.runtime_seconds, **('seconds',))
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        seconds = td.seconds % 60
        if hours > 0:
            return f'''{hours}h {minutes}m {seconds}s'''
        if None > 0:
            return f'''{minutes}m {seconds}s'''
        return f'''{None}s'''

    runtime_formatted = None(runtime_formatted)
    
    def is_terminal(self = None):
        '''
        Check if job is in terminal state (finished, cannot transition further)
        
        Returns:
            True if status is completed/failed/cancelled, False otherwise
            
        Use Case:
            Only cancel jobs that are not terminal.
            Only retry jobs that are terminal (failed).
        '''
        return self.status in (JobStatusEnum.COMPLETED.value, JobStatusEnum.FAILED.value, JobStatusEnum.CANCELLED.value)

    is_terminal = None(is_terminal)
    
    def is_active(self = None):
        '''
        Check if job is currently active (pending or running)
        
        Returns:
            True if job can still transition to completion
        '''
        return self.status in (JobStatusEnum.PENDING.value, JobStatusEnum.RUNNING.value)

    is_active = None(is_active)
    
    def succeeded(self = None):
        '''Check if job completed successfully'''
        if self.status == JobStatusEnum.COMPLETED.value:
            pass
        return self.exit_code == 0

    succeeded = None(succeeded)
    
    def wait_time_seconds(self = None):
        '''
        Calculate time spent waiting in queue
        
        Returns:
            Seconds between submission and execution start
        '''
        if not self.started_at:
            return None
        return None((self.started_at - self.submitted_at).total_seconds())

    wait_time_seconds = None(wait_time_seconds)
    
    def can_cancel(self = None):
        '''
        Check if job can be cancelled
        
        Returns:
            True if job is pending or running (not yet finished)
        '''
        return not (self.is_terminal)

    
    def can_retry(self = None):
        '''
        Check if job can be retried
        
        Returns:
            True if job failed and can be resubmitted
        '''
        return self.status == JobStatusEnum.FAILED.value

    
    def mark_started(self = None):
        '''Mark job as started.'''
        self.status = JobStatusEnum.RUNNING.value
        self.started_at = datetime.now()

    
    def mark_completed(self = None, exit_code = None):
        '''Mark job as completed.'''
        self.status = JobStatusEnum.COMPLETED.value
        self.completed_at = datetime.now()
        self.exit_code = exit_code

    
    def mark_failed(self = None, error_message = None, exit_code = None):
        '''Mark job as failed.'''
        self.status = JobStatusEnum.FAILED.value
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.exit_code = exit_code

    
    def mark_cancelled(self = None):
        '''Mark job as cancelled.'''
        self.status = JobStatusEnum.CANCELLED.value
        self.completed_at = datetime.now()

    
    def soft_delete(self = None):
        '''
        Soft delete job (mark as deleted without removing from database)
        
        Preserves audit trail while hiding from normal queries.
        '''
        self.deleted = True
        self.deleted_at = datetime.now()

    
    def to_dict(self = None):
        '''
        Convert job to dictionary for JSON serialization
        
        Returns:
            Dictionary with all job fields, suitable for API responses
            
        Example:
            job = db.query(Job).first()
            return {"job": job.to_dict()}
        '''
        pass
    # WARNING: Decompyle incomplete

    
    def from_spec(cls = None, job_id = None, backend_type = classmethod, spec = ('job_id', str, 'backend_type', str, 'spec', 'JobSpec', 'return', 'Job')):
        '''
        Create Job model from JobSpec
        
        Args:
            job_id: Unique job identifier
            backend_type: Execution backend type
            spec: JobSpec from core.execution module
            
        Returns:
            Job instance ready to be added to database
            
        Example:
            from backend.core.execution import JobSpec, ResourceSpec
            
            spec = JobSpec(
                pipeline_name="freesurfer_hippocampus",
                container_image="freesurfer/freesurfer:7.3.2",
                input_files=["/data/T1.nii.gz"],
                output_dir="/results/job-123",
                parameters={"threads": 8},
                resources=ResourceSpec(memory_gb=32, cpus=8)
            )
            
            job = Job.from_spec(job_id, "local_docker", spec)
            db.add(job)
            db.commit()
        '''
        return cls(job_id, backend_type, spec.pipeline_name, spec.container_image, spec.input_files, spec.parameters, {
            'memory_gb': spec.resources.memory_gb,
            'cpus': spec.resources.cpus,
            'time_hours': spec.resources.time_hours,
            'gpu': spec.resources.gpu }, spec.output_dir, JobStatusEnum.PENDING, **('id', 'backend_type', 'pipeline_name', 'container_image', 'input_files', 'parameters', 'resources', 'output_dir', 'status'))

    from_spec = None(from_spec)

