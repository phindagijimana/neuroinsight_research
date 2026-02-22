"""
Simplified MRI File Upload API

Handles uploading and initial processing of MRI files.
Supports only NIfTI (.nii, .nii.gz) files directly.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.schemas import JobCreate, JobStatus
from backend.services.job_service import JobService
from backend.services.storage_service import StorageService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/upload/")
async def upload_file(
    file: UploadFile,
    patient_data: str = Form("{}"),
    db: Session = Depends(get_db)
) -> Dict:
    """
    Upload and process an MRI file.

    Supports only:
    - .nii files (NIfTI single file)
    - .nii.gz files (compressed NIfTI)

    Args:
        file: The uploaded file
        patient_data: JSON string with patient information
        db: Database session

    Returns:
        Job information dictionary

    Raises:
        HTTPException: For various validation and processing errors
    """
    logger.info("upload_request_received", filename=file.filename, size=getattr(file, 'size', 'unknown'))

    # Validate file extension - only .nii and .nii.gz allowed
    if not file.filename.lower().endswith(('.nii', '.nii.gz')):
        raise HTTPException(
            status_code=400,
            detail="Only .nii and .nii.gz files are supported. Please convert your DICOM files to NIfTI format first."
        )

    # Read file data
    try:
        file_data = await file.read()
        logger.info("file_data_read", size=len(file_data))
    except Exception as e:
        logger.error("file_read_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    # Simple T1 filename validation only
    filename_lower = file.filename.lower()
    t1_indicators = ['t1', 't1w', 't1-weighted', 'mprage', 'spgr', 'fspgr']

    has_t1_indicator = any(indicator in filename_lower for indicator in t1_indicators)

    if not has_t1_indicator:
        logger.warning("filename_missing_t1_indicator", filename=file.filename, indicators=t1_indicators)
        # For now, allow any file - remove this warning later if you want strict validation
        # raise HTTPException(status_code=400, detail=f"Filename must contain T1 indicator: {t1_indicators}")

    logger.info("filename_validation_passed", filename=file.filename, has_t1_indicator=has_t1_indicator)

    # Determine original format for notes (basic file extension check)
    if file.filename.lower().endswith('.nii.gz'):
        original_format = "nii.gz"
    elif file.filename.lower().endswith('.nii'):
        original_format = "nii"
    else:
        original_format = "unknown"

    # Parse patient data from JSON
    try:
        patient_info = json.loads(patient_data) if patient_data else {}
        logger.info("patient_data_parsed", patient_info=patient_info)
    except json.JSONDecodeError as e:
        logger.error("patient_data_parse_failed", error=str(e), patient_data=patient_data)
        patient_info = {}

    # Extract and validate patient information
    patient_name = patient_info.get('patient_name')
    patient_id = patient_info.get('patient_id')
    age_str = patient_info.get('age')
    sex = patient_info.get('sex')
    scanner = patient_info.get('scanner')
    sequence = patient_info.get('sequence')
    notes = patient_info.get('notes')

    # Add original format information to notes
    conversion_note = f"Uploaded as {original_format} file."
    if notes:
        notes = f"{notes} | {conversion_note}"
    else:
        notes = conversion_note

    logger.info("patient_info_extracted",
               patient_name=patient_name,
               patient_id=patient_id,
               has_age=bool(age_str))

    # Validate and convert age
    patient_age = None
    if age_str is not None:
        try:
            # Handle both string and numeric inputs
            if isinstance(age_str, str):
                age_str = age_str.strip()
                if not age_str:
                    age_val = None
                else:
                    age_val = int(age_str)
            else:
                # Assume it's already numeric
                age_val = int(age_str)

            if age_val is not None and 0 <= age_val <= 150:
                patient_age = age_val
        except (ValueError, TypeError):
            pass  # Invalid age, keep as None

    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"

    # Save file using storage service: persist locally first, mirror to S3
    # Use BytesIO to create a file-like object from the cached file data
    from io import BytesIO
    file_obj = BytesIO(file_data)
    storage_service = StorageService()
    storage_path = storage_service.save_upload_local_then_s3(file_obj, unique_filename)

    # Job limits are checked before job creation above

    # Create job record
    job_data = JobCreate(
        filename=file.filename,
        file_path=storage_path,
        patient_name=patient_name,
        patient_id=patient_id,
        patient_age=patient_age,
        patient_sex=sex,
        scanner_info=scanner,
        sequence_info=sequence,
        notes=notes,
    )

    # Check queue limits before creating job
    # Maximum 1 running + 5 pending = 6 total active jobs
    # Failed jobs don't count (they can be reviewed/deleted anytime)
    running_jobs = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
    pending_jobs = JobService.count_jobs_by_status(db, [JobStatus.PENDING])

    # Check running limit (should always be 0 or 1, but double-check)
    if running_jobs >= 1 and pending_jobs >= 5:
        # Already at max capacity: 1 running + 5 pending
        # Clean up uploaded file
        if os.path.exists(storage_path):
            os.remove(storage_path)
        raise HTTPException(
            status_code=429,  # Too Many Requests
            detail="Job queue is full. Maximum 1 running job and 5 pending jobs allowed. Please wait for jobs to complete."
        )

    # If no running job, we can have up to 5 total jobs (will start immediately)
    # If 1 running job, we can have up to 5 pending jobs (will wait)
    total_active = running_jobs + pending_jobs
    if total_active >= 6:
        # Clean up uploaded file
        if os.path.exists(storage_path):
            os.remove(storage_path)
        raise HTTPException(
            status_code=429,  # Too Many Requests
            detail="Job queue is full. Maximum 1 running job and 5 pending jobs allowed. Please wait for jobs to complete."
        )

    job = JobService.create_job(db, job_data)

    # Check if we should start this job immediately or let it queue
    running_jobs = JobService.count_jobs_by_status(db, [JobStatus.RUNNING])
    if running_jobs == 0:
        # No jobs running, start this one immediately
        logger.info("starting_job_immediately_no_running_jobs", job_id=str(job.id))
        from workers.tasks.processing_web import process_mri_task
        process_mri_task.apply_async(args=[str(job.id)], routing_key='celery', exchange='celery')
    else:
        # Jobs are running, leave this one as pending - it will be auto-started when running jobs complete
        logger.info("job_queued_pending_running_jobs_exist",
                   job_id=str(job.id), running_jobs=running_jobs)

    logger.info("upload_completed", job_id=str(job.id), filename=file.filename, original_format=original_format)

    return {
        "id": str(job.id),
        "filename": job.filename,
        "file_path": job.file_path,
        "status": job.status.value,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "result_path": job.result_path,
        "progress": job.progress,
        "current_step": job.current_step,
        "patient_name": job.patient_name,
        "patient_id": job.patient_id,
        "patient_age": job.patient_age,
        "patient_sex": job.patient_sex,
        "scanner_info": job.scanner_info,
        "sequence_info": job.sequence_info,
        "notes": job.notes,
        "metrics": job.metrics or [],
    }
