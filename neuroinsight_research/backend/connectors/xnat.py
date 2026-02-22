"""
XNAT platform connector.

Communicates with the XNAT REST API using httpx (no SDK dependency).
Auth: JSESSION cookie or HTTP Basic Auth.
Hierarchy: Projects -> Subjects -> Experiments -> Scans -> Resources -> Files.

Works with any XNAT instance (including CIDUR).
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from backend.connectors.base import (
    BasePlatformConnector,
    PlatformDataset,
    PlatformItem,
)

logger = logging.getLogger(__name__)


class XNATConnector(BasePlatformConnector):
    """Connector for XNAT-based data management platforms."""

    platform_name = "xnat"

    def __init__(self, api_url: Optional[str] = None):
        self._api_url = (api_url or "").rstrip("/")
        self._session_cookie: Optional[str] = None
        self._username: Optional[str] = None
        self._client = httpx.Client(timeout=60.0, verify=True)

    # ------------------------------------------------------------------ auth

    def connect(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        url = credentials.get("url", self._api_url)
        if not url:
            raise ValueError("XNAT URL is required")
        self._api_url = url.rstrip("/")

        username = credentials.get("username", "")
        password = credentials.get("password", "")
        if not username or not password:
            raise ValueError("username and password are required")

        resp = self._client.post(
            f"{self._api_url}/data/JSESSION",
            auth=(username, password),
        )
        resp.raise_for_status()
        self._session_cookie = resp.text.strip()
        self._username = username

        return {
            "connected": True,
            "user": self._username,
            "workspace": self._api_url,
            "platform": self.platform_name,
        }

    def disconnect(self) -> None:
        if self._session_cookie:
            try:
                self._client.delete(
                    f"{self._api_url}/data/JSESSION",
                    cookies={"JSESSIONID": self._session_cookie},
                )
            except Exception as e:
                logger.debug("XNAT session invalidation request failed: %s", e)
        self._session_cookie = None
        self._username = None

    def is_connected(self) -> bool:
        if not self._session_cookie:
            return False
        try:
            resp = self._get("/data/projects", params={"format": "json"})
            return isinstance(resp, dict) and "ResultSet" in resp
        except Exception:
            self._session_cookie = None
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "platform": self.platform_name,
            "connected": self._session_cookie is not None,
            "user": self._username,
            "workspace": self._api_url,
        }

    # -------------------------------------------------------------- browse

    def list_projects(self) -> List[PlatformDataset]:
        data = self._get("/data/projects", params={"format": "json"})
        results = []
        for proj in self._result_set(data):
            results.append(
                PlatformDataset(
                    id=proj.get("ID", ""),
                    name=proj.get("name", proj.get("secondary_ID", "")),
                    description=proj.get("description", ""),
                    platform=self.platform_name,
                )
            )
        return results

    def list_datasets(self, project_id: str) -> List[PlatformDataset]:
        """List subjects within a project (XNAT's second hierarchy level)."""
        data = self._get(
            f"/data/projects/{quote(project_id, safe='')}/subjects",
            params={"format": "json"},
        )
        results = []
        for subj in self._result_set(data):
            results.append(
                PlatformDataset(
                    id=subj.get("ID", ""),
                    name=subj.get("label", subj.get("ID", "")),
                    description=subj.get("group", ""),
                    platform=self.platform_name,
                    extra={"project_id": project_id},
                )
            )
        return results

    def list_files(
        self, dataset_id: str, path: str = "/"
    ) -> List[PlatformItem]:
        """Browse XNAT hierarchy based on path depth.

        path="/":                              list experiments for subject
        path="/{experiment_id}":               list scans for experiment
        path="/{experiment_id}/{scan_id}":     list resources for scan
        path="/{exp}/{scan}/{resource}":       list files in resource
        """
        parts = [p for p in path.strip("/").split("/") if p]

        if len(parts) == 0:
            return self._list_experiments(dataset_id)
        elif len(parts) == 1:
            return self._list_scans(parts[0])
        elif len(parts) == 2:
            return self._list_resources(parts[0], parts[1])
        else:
            return self._list_resource_files(parts[0], parts[1], parts[2])

    def _list_experiments(self, subject_id: str) -> List[PlatformItem]:
        data = self._get(
            f"/data/subjects/{quote(subject_id, safe='')}/experiments",
            params={"format": "json"},
        )
        items = []
        for exp in self._result_set(data):
            items.append(
                PlatformItem(
                    id=exp.get("ID", ""),
                    name=exp.get("label", exp.get("ID", "")),
                    path=f"/{exp.get('ID', '')}",
                    type="directory",
                    modified=exp.get("date", exp.get("insert_date")),
                    platform=self.platform_name,
                    extra={"xsiType": exp.get("xsiType", "")},
                )
            )
        return items

    def _list_scans(self, experiment_id: str) -> List[PlatformItem]:
        data = self._get(
            f"/data/experiments/{quote(experiment_id, safe='')}/scans",
            params={"format": "json"},
        )
        items = []
        for scan in self._result_set(data):
            scan_id = scan.get("ID", "")
            items.append(
                PlatformItem(
                    id=scan_id,
                    name=f"Scan {scan_id}: {scan.get('type', '')} - {scan.get('series_description', '')}",
                    path=f"/{experiment_id}/{scan_id}",
                    type="directory",
                    platform=self.platform_name,
                    extra={
                        "quality": scan.get("quality", ""),
                        "frames": scan.get("frames", ""),
                    },
                )
            )
        return items

    def _list_resources(
        self, experiment_id: str, scan_id: str
    ) -> List[PlatformItem]:
        data = self._get(
            f"/data/experiments/{quote(experiment_id, safe='')}/scans/{quote(scan_id, safe='')}/resources",
            params={"format": "json"},
        )
        items = []
        for res in self._result_set(data):
            label = res.get("label", res.get("xnat_abstractresource_id", ""))
            items.append(
                PlatformItem(
                    id=label,
                    name=label,
                    path=f"/{experiment_id}/{scan_id}/{label}",
                    type="directory",
                    size=int(res.get("file_size", 0) or 0),
                    platform=self.platform_name,
                    extra={"file_count": res.get("file_count", 0)},
                )
            )
        return items

    def _list_resource_files(
        self, experiment_id: str, scan_id: str, resource_label: str
    ) -> List[PlatformItem]:
        data = self._get(
            f"/data/experiments/{quote(experiment_id, safe='')}"
            f"/scans/{quote(scan_id, safe='')}"
            f"/resources/{quote(resource_label, safe='')}/files",
            params={"format": "json"},
        )
        items = []
        for f in self._result_set(data):
            name = f.get("Name", "")
            items.append(
                PlatformItem(
                    id=f.get("URI", name),
                    name=name,
                    path=f"/{experiment_id}/{scan_id}/{resource_label}/{name}",
                    type="file",
                    size=int(f.get("Size", 0) or 0),
                    platform=self.platform_name,
                    extra={
                        "uri": f.get("URI", ""),
                        "collection": f.get("collection", ""),
                    },
                )
            )
        return items

    # ------------------------------------------------------------ download

    def download_file(self, file_id: str, local_path: str) -> str:
        """file_id is the XNAT URI (e.g. /data/experiments/.../files/T1.nii.gz)."""
        url = file_id if file_id.startswith("http") else f"{self._api_url}{file_id}"
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        with self._client.stream(
            "GET", url, cookies={"JSESSIONID": self._session_cookie or ""}
        ) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        return str(Path(local_path).resolve())

    def download_bulk(
        self, file_ids: List[str], local_dir: str
    ) -> List[str]:
        """Download multiple files. If a single experiment URI is provided,
        use ?format=zip for efficiency."""
        os.makedirs(local_dir, exist_ok=True)
        paths = []
        for fid in file_ids:
            fname = fid.rsplit("/", 1)[-1] if "/" in fid else fid
            dest = os.path.join(local_dir, fname)
            paths.append(self.download_file(fid, dest))
        return paths

    def get_download_url(self, file_id: str) -> str:
        if file_id.startswith("http"):
            return file_id
        return f"{self._api_url}{file_id}"

    # -------------------------------------------------------------- upload

    def upload_file(
        self,
        local_path: str,
        dataset_id: str,
        remote_path: str = "/",
    ) -> Dict[str, Any]:
        """Upload a file to an XNAT experiment resource.

        dataset_id format: "{experiment_id}/{resource_label}"
        """
        parts = dataset_id.split("/", 1)
        experiment_id = parts[0]
        resource_label = parts[1] if len(parts) > 1 else "NEUROINSIGHT"

        fname = Path(local_path).name
        upload_url = (
            f"{self._api_url}/data/experiments/{quote(experiment_id, safe='')}"
            f"/resources/{quote(resource_label, safe='')}"
            f"/files/{quote(fname, safe='')}"
        )

        with open(local_path, "rb") as f:
            resp = self._client.put(
                upload_url,
                content=f.read(),
                cookies={"JSESSIONID": self._session_cookie or ""},
                headers={"Content-Type": "application/octet-stream"},
                params={"overwrite": "true", "extract": "false"},
            )
            resp.raise_for_status()

        return {"uploaded": fname, "url": upload_url, "status": "ok"}

    # ----------------------------------------------------------- internals

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        if not self._session_cookie:
            raise RuntimeError("Not connected to XNAT")
        resp = self._client.get(
            f"{self._api_url}{path}",
            cookies={"JSESSIONID": self._session_cookie},
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _result_set(data: Any) -> List[Dict]:
        """Extract the Result array from XNAT's standard JSON envelope."""
        if isinstance(data, dict):
            rs = data.get("ResultSet", {})
            return rs.get("Result", [])
        return data if isinstance(data, list) else []
