"""
Data transfer routes -- move data between any two platforms/backends.

POST /api/transfer/download  -- platform -> processing backend
POST /api/transfer/upload    -- processing backend -> platform
POST /api/transfer/move      -- any source -> any destination
GET  /api/transfer/{id}      -- check progress
POST /api/transfer/{id}/cancel -- cancel
GET  /api/transfer/history   -- recent transfers
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transfer", tags=["transfer"])

ALL_PLATFORMS = {"local", "remote", "hpc", "pennsieve", "xnat"}
BACKEND_PLATFORMS = {"local", "remote", "hpc"}
EXTERNAL_PLATFORMS = {"pennsieve", "xnat"}


class DownloadRequest(BaseModel):
    platform: str  # "pennsieve" or "xnat"
    file_ids: List[str]
    target_backend: str  # "local", "remote", "hpc"
    target_path: str


class UploadRequest(BaseModel):
    source_backend: str  # "local", "remote", "hpc"
    source_path: str
    platform: str
    dataset_id: str


class MoveRequest(BaseModel):
    """Transfer data between any two platforms."""
    source_type: str       # "local", "remote", "hpc", "pennsieve", "xnat"
    source_path: str       # path on source (or "" for platform file_ids)
    source_file_ids: Optional[List[str]] = None  # platform file IDs
    dest_type: str         # "local", "remote", "hpc", "pennsieve", "xnat"
    dest_path: str         # path on destination (or dataset_id for platforms)


class TransferInfo(BaseModel):
    id: str
    status: str  # pending, downloading, uploading, completed, failed, cancelled
    direction: str  # "download", "upload", or "move"
    platform: str
    progress_percent: float = 0
    bytes_transferred: int = 0
    total_bytes: int = 0
    files_completed: int = 0
    total_files: int = 0
    error: Optional[str] = None


@router.post("/download")
def start_download(request: DownloadRequest):
    """Start async download from platform to processing backend."""
    from backend.core.transfer_manager import get_transfer_manager

    try:
        manager = get_transfer_manager()
        transfer_id = manager.start_download(
            platform=request.platform,
            file_ids=request.file_ids,
            target_backend=request.target_backend,
            target_path=request.target_path,
        )
        return {"transfer_id": transfer_id, "status": "pending"}
    except Exception as e:
        logger.error("start_download failed: %s", e)
        raise HTTPException(500, f"Failed to start download: {e}")


@router.post("/upload")
def start_upload(request: UploadRequest):
    """Start async upload from processing backend to platform."""
    from backend.core.transfer_manager import get_transfer_manager

    try:
        manager = get_transfer_manager()
        transfer_id = manager.start_upload(
            source_backend=request.source_backend,
            source_path=request.source_path,
            platform=request.platform,
            dataset_id=request.dataset_id,
        )
        return {"transfer_id": transfer_id, "status": "pending"}
    except Exception as e:
        logger.error("start_upload failed: %s", e)
        raise HTTPException(500, f"Failed to start upload: {e}")


@router.post("/move")
def start_move(request: MoveRequest):
    """Transfer data between any two platforms/backends."""
    if request.source_type not in ALL_PLATFORMS:
        raise HTTPException(400, f"Invalid source_type: {request.source_type}")
    if request.dest_type not in ALL_PLATFORMS:
        raise HTTPException(400, f"Invalid dest_type: {request.dest_type}")
    if request.source_type == request.dest_type:
        raise HTTPException(400, "Source and destination cannot be the same")

    from backend.core.transfer_manager import get_transfer_manager

    try:
        manager = get_transfer_manager()
        transfer_id = manager.start_move(
            source_type=request.source_type,
            source_path=request.source_path,
            source_file_ids=request.source_file_ids or [],
            dest_type=request.dest_type,
            dest_path=request.dest_path,
        )
        return {"transfer_id": transfer_id, "status": "pending"}
    except Exception as e:
        logger.error("start_move failed: %s", e)
        raise HTTPException(500, f"Failed to start transfer: {e}")


@router.get("/{transfer_id}")
def get_transfer_progress(transfer_id: str):
    """Get transfer progress."""
    from backend.core.transfer_manager import get_transfer_manager

    manager = get_transfer_manager()
    progress = manager.get_progress(transfer_id)
    if progress is None:
        raise HTTPException(404, f"Transfer {transfer_id} not found")
    return progress


@router.post("/{transfer_id}/cancel")
def cancel_transfer(transfer_id: str):
    """Cancel an in-progress transfer."""
    from backend.core.transfer_manager import get_transfer_manager

    manager = get_transfer_manager()
    try:
        manager.cancel(transfer_id)
        return {"transfer_id": transfer_id, "status": "cancelled"}
    except Exception as e:
        raise HTTPException(500, f"Failed to cancel transfer: {e}")


@router.get("/history/list")
def transfer_history():
    """List recent transfers."""
    from backend.core.transfer_manager import get_transfer_manager

    manager = get_transfer_manager()
    return {"transfers": manager.list_transfers()}
