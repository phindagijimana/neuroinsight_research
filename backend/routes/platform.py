"""
Platform API routes -- connect/browse/disconnect for external data platforms.

Supports Pennsieve and XNAT (including CIDUR).
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.connectors.base import BasePlatformConnector
from backend.connectors.pennsieve import PennsieveConnector
from backend.connectors.xnat import XNATConnector
from backend.core.config import get_settings
from backend.core.platform_config_store import (
    clear_platform_config,
    load_platform_config,
    save_platform_config,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/platforms", tags=["platforms"])

# In-memory connector instances (one per platform, per server process)
_connectors: dict[str, BasePlatformConnector] = {}

SUPPORTED_PLATFORMS = {"pennsieve", "xnat"}


def _get_connector(platform: str) -> BasePlatformConnector:
    """Get or create a connector for the given platform."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {platform}. Supported: {', '.join(SUPPORTED_PLATFORMS)}",
        )

    if platform not in _connectors:
        settings = get_settings()
        if platform == "pennsieve":
            _connectors[platform] = PennsieveConnector(
                api_url=settings.pennsieve_api_url
            )
        elif platform == "xnat":
            _connectors[platform] = XNATConnector(
                api_url=settings.xnat_api_url
            )

    connector = _connectors[platform]

    # Connections are in-memory per worker process; restore from persisted
    # credentials when available so subsequent requests (e.g. transfer upload)
    # do not depend on landing on the same worker as /connect.
    if not connector.is_connected():
        saved_creds = load_platform_config(platform)
        if saved_creds:
            try:
                connector.connect(saved_creds)
                logger.info("Auto-restored %s platform session from saved config", platform)
            except Exception as e:
                logger.warning("Could not auto-restore %s session: %s", platform, e)

    return connector


def _require_connected(connector: BasePlatformConnector) -> None:
    if not connector.is_connected():
        raise HTTPException(
            status_code=503,
            detail=f"Not connected to {connector.platform_name}. Call /connect first.",
        )


# ---------------------------------------------------------------- models

class PennsieveCredentials(BaseModel):
    api_key: str
    api_secret: str


class XNATCredentials(BaseModel):
    url: str
    username: str
    password: str


class ConnectRequest(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    verify_ssl: Optional[bool] = True


# ------------------------------------------------------------- endpoints

@router.post("/{platform}/connect")
def platform_connect(platform: str, request: ConnectRequest):
    """Authenticate with a platform."""
    connector = _get_connector(platform)

    creds: dict = {}
    if platform == "pennsieve":
        if not request.api_key or not request.api_secret:
            raise HTTPException(400, "api_key and api_secret are required for Pennsieve")
        creds = {"api_key": request.api_key, "api_secret": request.api_secret}
    elif platform == "xnat":
        if not request.url or not request.username or not request.password:
            raise HTTPException(400, "url, username, and password are required for XNAT")
        creds = {
            "url": request.url,
            "username": request.username,
            "password": request.password,
            "verify_ssl": str(request.verify_ssl).lower(),
        }

    try:
        result = connector.connect(creds)
        save_platform_config(platform, creds)
        return result
    except ConnectionError as e:
        logger.warning("Platform connect - network error: %s", e)
        raise HTTPException(502, str(e))
    except PermissionError as e:
        logger.warning("Platform connect - auth error: %s", e)
        raise HTTPException(401, str(e))
    except ValueError as e:
        logger.warning("Platform connect - validation: %s", e)
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("Platform connect failed: %s", e)
        raise HTTPException(502, f"Connection failed: {e}")


@router.post("/{platform}/disconnect")
def platform_disconnect(platform: str):
    """End session with a platform."""
    connector = _get_connector(platform)
    connector.disconnect()
    clear_platform_config(platform)
    return {"disconnected": True, "platform": platform}


@router.get("/{platform}/status")
def platform_status(platform: str):
    """Check connection status."""
    connector = _get_connector(platform)
    return connector.status()


@router.get("/pennsieve/agent-status")
def pennsieve_agent_status():
    """Check Pennsieve Agent readiness required for uploads."""
    connector = _get_connector("pennsieve")
    _require_connected(connector)
    if not isinstance(connector, PennsieveConnector):
        raise HTTPException(500, "Pennsieve connector is not available")
    try:
        return connector.agent_status()
    except Exception as e:
        logger.error("pennsieve agent-status failed: %s", e)
        raise HTTPException(502, f"Failed to check Pennsieve Agent status: {e}")


@router.get("/{platform}/projects")
def platform_list_projects(platform: str):
    """List top-level projects / workspaces."""
    connector = _get_connector(platform)
    _require_connected(connector)
    try:
        projects = connector.list_projects()
        return {"projects": [p.to_dict() for p in projects]}
    except Exception as e:
        logger.error("list_projects failed: %s", e)
        raise HTTPException(502, f"Failed to list projects: {e}")


@router.get("/{platform}/datasets")
def platform_list_datasets(
    platform: str,
    project_id: str = Query("", description="Project/workspace ID"),
):
    """List datasets within a project."""
    connector = _get_connector(platform)
    _require_connected(connector)
    try:
        datasets = connector.list_datasets(project_id)
        return {"datasets": [d.to_dict() for d in datasets]}
    except Exception as e:
        logger.error("list_datasets failed: %s", e)
        raise HTTPException(502, f"Failed to list datasets: {e}")


@router.get("/{platform}/browse")
def platform_browse(
    platform: str,
    dataset_id: str = Query(..., description="Dataset or experiment ID"),
    path: str = Query("/", description="Sub-path within the dataset"),
):
    """List files and folders within a dataset at the given path."""
    connector = _get_connector(platform)
    _require_connected(connector)
    try:
        items = connector.list_files(dataset_id, path)
        return {
            "items": [item.to_dict() for item in items],
            "dataset_id": dataset_id,
            "path": path,
            "total": len(items),
        }
    except Exception as e:
        logger.error("browse failed: %s", e)
        raise HTTPException(502, f"Failed to browse: {e}")
