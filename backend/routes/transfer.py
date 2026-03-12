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
import urllib.parse
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
    dest_path: str         # path on destination (or dataset_id[?path=/subdir] for platforms)


def _parse_pennsieve_dest_path(dest_path: str) -> tuple[str, str]:
    """Parse Pennsieve destination as dataset_id or dataset_id?path=/folder."""
    raw = (dest_path or "").strip()
    dataset_id = raw
    remote_path = "/"

    if "?path=" in raw:
        dataset_id, encoded_path = raw.split("?path=", 1)
        decoded = urllib.parse.unquote(encoded_path).strip()
        if decoded:
            remote_path = decoded if decoded.startswith("/") else f"/{decoded}"

    return dataset_id, remote_path


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

    target_path = request.target_path

    # For HPC/remote backends, resolve the target path to the HPC work
    # directory so files land on shared storage accessible by compute nodes.
    if request.target_backend in ("hpc", "remote"):
        import os, time
        work_dir = os.environ.get("HPC_WORK_DIR", "~")
        if work_dir == "~":
            work_dir = f"/home/{os.environ.get('HPC_USER', 'user')}"
        target_path = f"{work_dir}/transfers/{int(time.time() * 1000)}"

    try:
        manager = get_transfer_manager()
        transfer_id = manager.start_download(
            platform=request.platform,
            file_ids=request.file_ids,
            target_backend=request.target_backend,
            target_path=target_path,
        )
        return {"transfer_id": transfer_id, "status": "pending", "target_path": target_path}
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
    if request.dest_type == "pennsieve":
        dataset_id, _remote_path = _parse_pennsieve_dest_path(request.dest_path)
        if not dataset_id.startswith("N:dataset:"):
            raise HTTPException(
                400,
                "For Pennsieve destination, dest_path must be N:dataset:<uuid> "
                "or N:dataset:<uuid>?path=/folder",
            )
        # Fail fast before async thread starts if Pennsieve upload prerequisites
        # (agent/profile) are not ready.
        from backend.routes.platform import _get_connector
        connector = _get_connector("pennsieve")
        if not connector.is_connected():
            raise HTTPException(503, "Not connected to pennsieve. Connect first.")
        if hasattr(connector, "agent_status"):
            agent = connector.agent_status()
            if not agent.get("ready_for_upload", False):
                raise HTTPException(
                    400,
                    agent.get("error")
                    or "Pennsieve Agent is not ready for upload.",
                )

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
