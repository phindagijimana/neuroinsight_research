"""
Placeholder API endpoints for frontend compatibility.

Provides endpoints that match frontend expectations for image serving.
"""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.database import get_db
from backend.models.job import JobStatus
from backend.services import JobService
from .visualizations import get_overlay_image

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/placeholder", tags=["placeholder"])


@router.get("/anatomical/{job_id}/{orientation}/{slice_num}.png")
def get_placeholder_anatomical(
    job_id: str,
    orientation: str,
    slice_num: int,
    db: Session = Depends(get_db),
):
    """
    Placeholder endpoint for anatomical images - redirects to overlay endpoint.

    This endpoint exists for frontend compatibility.
    Frontend expects: /api/placeholder/anatomical/{job_id}/{orientation}/{slice_num}.png
    """
    slice_id = f"slice_{slice_num:02d}"
    return get_overlay_image(job_id, slice_id, orientation, "anatomical", None, db)


@router.get("/overlay/{job_id}/{orientation}/{slice_num}.png")
def get_placeholder_overlay(
    job_id: str,
    orientation: str,
    slice_num: int,
    db: Session = Depends(get_db),
):
    """
    Placeholder endpoint for overlay images - redirects to overlay endpoint.

    This endpoint exists for frontend compatibility.
    Frontend expects: /api/placeholder/overlay/{job_id}/{orientation}/{slice_num}.png
    """
    slice_id = f"slice_{slice_num:02d}"
    return get_overlay_image(job_id, slice_id, orientation, "overlay", None, db)
