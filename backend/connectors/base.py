"""
Abstract base class for platform connectors.

Every external data platform (Pennsieve, XNAT, Flywheel, ...) implements
this interface so the rest of the application can browse, download, and
upload data without knowing platform-specific details.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PlatformItem:
    """Unified representation of a file or directory on any platform."""

    id: str
    name: str
    path: str
    type: str  # "file" or "directory"
    size: int = 0
    modified: Optional[str] = None
    platform: str = ""
    mime_type: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "size": self.size,
            "modified": self.modified,
            "platform": self.platform,
        }
        if self.mime_type:
            d["mime_type"] = self.mime_type
        if self.extra:
            d["extra"] = self.extra
        return d


@dataclass
class PlatformDataset:
    """Top-level dataset / project on a platform."""

    id: str
    name: str
    description: str = ""
    file_count: int = 0
    size_bytes: int = 0
    platform: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "file_count": self.file_count,
            "size_bytes": self.size_bytes,
            "platform": self.platform,
        }


class BasePlatformConnector(ABC):
    """Interface that every platform connector must implement."""

    platform_name: str = "base"

    # ---- Authentication ----

    @abstractmethod
    def connect(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """Authenticate with the platform.

        Args:
            credentials: Platform-specific credential dict.
                Pennsieve: {"api_key": ..., "api_secret": ...}
                XNAT:      {"url": ..., "username": ..., "password": ...}

        Returns:
            {"connected": True, "user": "...", "workspace": "..."}
        """

    @abstractmethod
    def disconnect(self) -> None:
        """End the current session."""

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if there is an active authenticated session."""

    def status(self) -> Dict[str, Any]:
        """Return current connection status."""
        return {
            "platform": self.platform_name,
            "connected": self.is_connected(),
        }

    # ---- Browse ----

    @abstractmethod
    def list_projects(self) -> List[PlatformDataset]:
        """List top-level projects / workspaces.

        For Pennsieve this returns the single workspace's datasets.
        For XNAT this returns projects.
        """

    @abstractmethod
    def list_datasets(self, project_id: str) -> List[PlatformDataset]:
        """List datasets within a project.

        For Pennsieve: datasets in the workspace (project_id ignored).
        For XNAT: subjects within a project.
        """

    @abstractmethod
    def list_files(
        self, dataset_id: str, path: str = "/"
    ) -> List[PlatformItem]:
        """List files and folders within a dataset at the given path.

        Args:
            dataset_id: Dataset or experiment identifier.
            path: Sub-path within the dataset (default: root).

        Returns:
            List of PlatformItem representing files and directories.
        """

    # ---- Download ----

    @abstractmethod
    def download_file(self, file_id: str, local_path: str) -> str:
        """Download a single file to a local path.

        Args:
            file_id: Platform-specific file identifier.
            local_path: Destination path on the local filesystem.

        Returns:
            The absolute local path where the file was saved.
        """

    def download_bulk(
        self, file_ids: List[str], local_dir: str
    ) -> List[str]:
        """Download multiple files to a local directory.

        Default implementation calls download_file in a loop.
        Subclasses may override with platform-specific bulk APIs.

        Returns:
            List of absolute local paths.
        """
        import os

        os.makedirs(local_dir, exist_ok=True)
        paths = []
        for fid in file_ids:
            dest = os.path.join(local_dir, fid)
            paths.append(self.download_file(fid, dest))
        return paths

    @abstractmethod
    def get_download_url(self, file_id: str) -> str:
        """Get a direct (possibly presigned) download URL for a file."""

    # ---- Upload ----

    @abstractmethod
    def upload_file(
        self,
        local_path: str,
        dataset_id: str,
        remote_path: str = "/",
    ) -> Dict[str, Any]:
        """Upload a local file to a dataset on the platform.

        Args:
            local_path: Path to the file on the local filesystem.
            dataset_id: Target dataset / experiment identifier.
            remote_path: Destination path within the dataset.

        Returns:
            Platform-specific metadata about the uploaded file.
        """
