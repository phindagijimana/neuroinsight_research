"""
Pydantic schemas for Metric-related API operations.

These schemas define the structure and validation rules for
metric-related API requests and responses.
"""

from datetime import datetime
from typing import Optional
# from uuid import UUID  # Not needed for string job IDs

from pydantic import BaseModel, Field, validator


class MetricCreate(BaseModel):
    """
    Schema for creating a new metric.
    
    Used when storing hippocampal volumetric measurements.
    """
    
    job_id: str = Field(
        ...,
        description="Associated job identifier (8 characters)"
    )
    
    region: str = Field(
        ...,
        description="Hippocampal subregion name",
        example="CA1"
    )
    
    left_volume: float = Field(
        ...,
        gt=0,
        description="Left hemisphere volume in mm³",
        example=1234.56
    )
    
    right_volume: float = Field(
        ...,
        gt=0,
        description="Right hemisphere volume in mm³",
        example=1198.32
    )
    
    asymmetry_index: Optional[float] = Field(
        None,
        ge=-1,
        le=1,
        description="Computed asymmetry index (will be calculated if not provided)"
    )
    
    @validator("asymmetry_index", always=True)
    def calculate_asymmetry_index(cls, v, values):
        """
        Calculate asymmetry index if not provided.
        
        Formula: AI = (L - R) / (L + R)
        """
        if v is None and "left_volume" in values and "right_volume" in values:
            left = values["left_volume"]
            right = values["right_volume"]
            sum_volume = left + right
            if sum_volume > 0:
                v = (left - right) / sum_volume
            else:
                v = 0.0
        return v


class MetricResponse(BaseModel):
    """
    Schema for metric API responses.
    
    Includes all metric details and computed properties.
    """
    
    id: str = Field(
        ...,
        description="Unique metric identifier"
    )
    
    job_id: str = Field(
        ...,
        description="Associated job identifier (8 characters)"
    )
    
    region: str = Field(
        ...,
        description="Hippocampal subregion name"
    )
    
    left_volume: float = Field(
        ...,
        description="Left hemisphere volume in mm³"
    )
    
    right_volume: float = Field(
        ...,
        description="Right hemisphere volume in mm³"
    )
    
    asymmetry_index: float = Field(
        ...,
        description="Computed asymmetry index"
    )
    
    created_at: datetime = Field(
        ...,
        description="Metric creation timestamp"
    )
    
    class Config:
        """Pydantic configuration."""
        from_attributes = True

