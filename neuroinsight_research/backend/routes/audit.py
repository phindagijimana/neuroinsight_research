"""
Audit Log API Routes

Endpoints for viewing the audit trail.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    event: Optional[str] = Query(default=None, description="Filter by event type"),
):
    """Get recent audit log entries.

    Returns structured JSON entries with timestamps, event types, and metadata.
    Newest entries first.
    """
    from backend.core.audit import get_audit_logger

    audit = get_audit_logger()
    entries = audit.get_recent(limit=limit, event_filter=event)
    return {"entries": entries, "total": len(entries)}


@router.get("/events")
def list_event_types():
    """List all known audit event types."""
    return {
        "event_types": [
            {"event": "job_submitted", "description": "New job submitted for execution"},
            {"event": "job_completed", "description": "Job finished successfully"},
            {"event": "job_failed", "description": "Job execution failed"},
            {"event": "job_cancelled", "description": "Job cancelled by user"},
            {"event": "ssh_connected", "description": "SSH connection established to HPC"},
            {"event": "ssh_disconnected", "description": "SSH connection closed"},
            {"event": "backend_switched", "description": "Execution backend changed"},
            {"event": "file_uploaded", "description": "File uploaded to server"},
            {"event": "file_downloaded", "description": "File downloaded from results"},
        ]
    }
