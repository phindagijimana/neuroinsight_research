"""
Pydantic schemas for Job-related API operations.

These schemas define the structure and validation rules for
job-related API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, field_serializer


class JobStatus(str, Enum):
    """Job status enumeration for API."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreate(BaseModel):
    """
    Schema for creating a new job.

    Used when uploading a new MRI file for processing.
    """

    filename: str = Field(
        ...,
        description="Original filename of the MRI scan",
        example="patient_001_T1w.nii.gz"
    )

    file_path: Optional[str] = Field(
        None,
        description="Storage path for the uploaded file",
        example="/data/uploads/patient_001_T1w.nii.gz"
    )

    # Patient information fields (matching frontend field names)
    patient_name: Optional[str] = Field(
        default=None,
        description="Patient name",
        example="John Doe"
    )

    patient_id: Optional[str] = Field(
        default=None,
        description="Patient ID/MRN",
        example="MRN123456"
    )

    patient_age: Optional[int] = Field(
        default=None,
        description="Patient age in years",
        ge=0,
        le=150,
        example=65
    )

    patient_sex: Optional[str] = Field(
        default=None,
        description="Patient sex",
        example="M"
    )

    scanner_info: Optional[str] = Field(
        default=None,
        description="MRI scanner information",
        example="Siemens Prisma 3T"
    )

    sequence_info: Optional[str] = Field(
        default=None,
        description="MRI sequence information",
        example="T1 MPRAGE"
    )

    notes: Optional[str] = Field(
        default=None,
        description="Additional clinical notes",
        example="Pre-surgical evaluation"
    )


class JobUpdate(BaseModel):
    """
    Schema for updating an existing job.
    
    Used to update job status and related fields during processing.
    """
    
    status: Optional[JobStatus] = Field(
        None,
        description="Updated job status"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error message if job failed"
    )
    
    started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when processing started"
    )
    
    completed_at: Optional[datetime] = Field(
        None,
        description="Timestamp when processing completed"
    )
    
    result_path: Optional[str] = Field(
        None,
        description="Path to processing output directory"
    )

    celery_task_id: Optional[str] = Field(
        None,
        description="Celery task ID for async processing tracking"
    )


class MetricSummary(BaseModel):
    """
    Simplified metric schema for job responses.
    
    Includes key volumetric data without full metric details.
    """
    
    id: str
    region: str
    left_volume: float
    right_volume: float
    asymmetry_index: float
    laterality: str
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True


class JobResponse(BaseModel):
    """
    Schema for job API responses.
    
    Includes all job details and associated metrics.
    """
    
    id: str = Field(
        ...,
        description="Unique job identifier (8 characters)",
        min_length=8,
        max_length=8
    )

    @field_validator('id', mode='before')
    @classmethod
    def validate_id(cls, v):
        """Convert UUID objects to string."""
        if hasattr(v, '__str__'):
            return str(v)
        return v

    @field_serializer('id')
    def serialize_id(self, value):
        """Ensure ID is returned as string."""
        return str(value)
    
    filename: str = Field(
        ...,
        description="Original filename"
    )
    
    file_path: Optional[str] = Field(
        None,
        description="Storage path"
    )
    
    status: JobStatus = Field(
        ...,
        description="Current processing status"
    )

    celery_task_id: Optional[str] = Field(
        None,
        description="Celery task ID for async processing tracking"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Error details if failed"
    )
    
    created_at: datetime = Field(
        ...,
        description="Job creation timestamp"
    )
    
    started_at: Optional[datetime] = Field(
        None,
        description="Processing start timestamp"
    )
    
    completed_at: Optional[datetime] = Field(
        None,
        description="Processing completion timestamp"
    )
    
    result_path: Optional[str] = Field(
        None,
        description="Output directory path"
    )
    
    progress: int = Field(
        default=0,
        description="Processing progress percentage (0-100)",
        ge=0,
        le=100
    )
    
    current_step: Optional[str] = Field(
        None,
        description="Current processing step description"
    )

    # Patient information
    patient_name: Optional[str] = Field(
        None,
        description="Patient name"
    )

    patient_id: Optional[str] = Field(
        None,
        description="Patient ID/MRN"
    )

    patient_age: Optional[int] = Field(
        None,
        description="Patient age in years"
    )

    patient_sex: Optional[str] = Field(
        None,
        description="Patient sex"
    )

    scanner_info: Optional[str] = Field(
        None,
        description="MRI scanner information"
    )

    sequence_info: Optional[str] = Field(
        None,
        description="MRI sequence information"
    )

    notes: Optional[str] = Field(
        None,
        description="Additional clinical notes"
    )

    metrics: List[MetricSummary] = Field(
        default=[],
        description="Associated hippocampal metrics"
    )

    visualizations: Optional[Dict] = Field(
        default=None,
        description="Paths to generated visualization files"
    )

    class Config:
        """Pydantic configuration."""
        from_attributes = True

