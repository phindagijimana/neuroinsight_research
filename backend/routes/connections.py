"""Named SSH connections API.

Lets the Transfer page hold several HPC/remote hosts open at once (beside the
single active connection managed under /api/hpc) so data can move directly
between two different clusters. See backend/core/connection_registry.py.
"""

import logging
from pathlib import PurePosixPath
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.connection_registry import get_registry

router = APIRouter(prefix="/api/connections", tags=["connections"])
logger = logging.getLogger(__name__)


class AddConnectionRequest(BaseModel):
    name: str
    host: str
    username: str
    port: int = 22
    key_path: Optional[str] = None
    # Password / keyboard-interactive (Duo) clusters; used only to connect.
    password: Optional[str] = None
    kind: str = "hpc"  # "hpc" | "remote"
    work_dir: Optional[str] = None


@router.get("")
def list_connections():
    """All live connections: the active one plus any extras."""
    return {"connections": [e.to_dict() for e in get_registry().list()]}


@router.post("")
def add_connection(req: AddConnectionRequest):
    """Connect to a host and register it as an additional live connection."""
    try:
        entry = get_registry().add(
            name=req.name,
            host=req.host,
            username=req.username,
            port=req.port,
            key_path=req.key_path,
            password=req.password,
            kind=req.kind,
            work_dir=req.work_dir,
        )
    except Exception as e:  # noqa: BLE001 - surface the connect error to the UI
        logger.warning("Add connection to %s failed: %s", req.host, e)
        raise HTTPException(status_code=400, detail=f"Could not connect to {req.host}: {e}")
    return entry.to_dict()


@router.delete("/{conn_id}")
def remove_connection(conn_id: str):
    """Disconnect and drop an extra connection (the active one is not removable here)."""
    if not get_registry().remove(conn_id):
        raise HTTPException(status_code=404, detail="Connection not found, or it is the active connection")
    return {"removed": True, "id": conn_id}


@router.get("/{conn_id}/browse")
def browse_connection(conn_id: str, path: str = "~"):
    """List a directory on a specific connection (for the Transfer file panes)."""
    mgr = get_registry().manager_for(conn_id)
    if mgr is None:
        raise HTTPException(status_code=404, detail=f"No such connection: {conn_id}")
    try:
        info = mgr.connection_info()
    except Exception:
        info = {}
    if not info.get("connected"):
        raise HTTPException(status_code=503, detail="Connection is not live")

    if path.startswith("~"):
        try:
            _, home_dir, _ = mgr.execute("echo $HOME", timeout=5)
            path = path.replace("~", home_dir.strip(), 1)
        except Exception as e:
            logger.debug("home '~' expansion failed on %s: %s", conn_id, e)

    try:
        entries = mgr.list_dir(path)
        directories = [e for e in entries if e.get("type") == "directory"]
        files = [e for e in entries if e.get("type") == "file"]
        nifti_files = [e for e in files if e["name"].endswith((".nii", ".nii.gz"))]
        return {
            "path": path,
            "parent": str(PurePosixPath(path).parent),
            "directories": directories,
            "files": files,
            "nifti_files": nifti_files,
            "total_files": len(files),
            "total_directories": len(directories),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to browse: {e}")
