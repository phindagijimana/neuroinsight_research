"""
Pennsieve platform connector.

Communicates with the Pennsieve REST API using httpx.
Auth: API key + secret -> AWS Cognito -> JWT access token.
Hierarchy: Workspace -> Datasets -> Packages -> Files.
"""

import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import httpx
from jose import jwt

from backend.connectors.base import (
    BasePlatformConnector,
    PlatformDataset,
    PlatformItem,
)

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api.pennsieve.io"
_TOKEN_EXPIRY_BUFFER = 300  # refresh 5 min before expiry


class PennsieveConnector(BasePlatformConnector):
    """Connector for the Pennsieve data management platform."""

    platform_name = "pennsieve"

    def __init__(self, api_url: str = _DEFAULT_API_URL):
        self._api_url = api_url.rstrip("/")
        self._token: Optional[str] = None
        self._token_expires: float = 0
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._user: Optional[str] = None
        self._organization: Optional[str] = None
        self._org_id: Optional[str] = None
        self._client = httpx.Client(timeout=60.0)
        self._dataset_int_ids: Dict[str, int] = {}  # node_id -> intId mapping

    # ------------------------------------------------------------------ auth

    def connect(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        self._api_key = credentials.get("api_key", "")
        self._api_secret = credentials.get("api_secret", "")

        if not self._api_key or not self._api_secret:
            raise ValueError("api_key and api_secret are required")

        self._refresh_token()

        user_resp = self._get("/user/")
        self._user = user_resp.get("email") or user_resp.get("firstName", "unknown")

        orgs_resp = self._get("/organizations/")
        if isinstance(orgs_resp, list) and orgs_resp:
            org_obj = orgs_resp[0].get("organization", {})
            self._organization = org_obj.get("name", "")
            if not self._org_id:
                self._org_id = org_obj.get("id", "")

        return {
            "connected": True,
            "user": self._user,
            "workspace": self._organization or "",
            "platform": self.platform_name,
        }

    def disconnect(self) -> None:
        self._token = None
        self._token_expires = 0
        self._api_key = None
        self._api_secret = None
        self._user = None
        self._organization = None
        self._org_id = None
        self._dataset_int_ids.clear()

    def is_connected(self) -> bool:
        return self._token is not None and time.time() < self._token_expires

    def status(self) -> Dict[str, Any]:
        return {
            "platform": self.platform_name,
            "connected": self.is_connected(),
            "user": self._user,
            "workspace": self._organization,
        }

    # -------------------------------------------------------------- browse

    def list_projects(self) -> List[PlatformDataset]:
        """Pennsieve has workspaces, not projects. Returns datasets directly."""
        return self.list_datasets("")

    def list_datasets(self, project_id: str) -> List[PlatformDataset]:
        data = self._get("/datasets/")
        results = []
        for ds in data if isinstance(data, list) else []:
            content = ds.get("content", {})
            node_id = content.get("id", "")
            int_id = content.get("intId")
            if node_id and int_id:
                self._dataset_int_ids[node_id] = int_id
            results.append(
                PlatformDataset(
                    id=node_id,
                    name=content.get("name", ""),
                    description=content.get("description", ""),
                    size_bytes=ds.get("storage", 0) if isinstance(ds.get("storage"), int) else 0,
                    platform=self.platform_name,
                )
            )
        return results

    def list_files(
        self, dataset_id: str, path: str = "/"
    ) -> List[PlatformItem]:
        if path and path != "/":
            pkg_id = path.lstrip("/")
            data = self._get(f"/packages/{self._enc(pkg_id)}")
            children = data.get("children", []) if isinstance(data, dict) else []
            if children:
                return self._items_from_packages(children, dataset_id)
            return self._parse_package_children(data, dataset_id)

        data = self._list_dataset_packages(dataset_id)
        packages = data.get("packages", []) if isinstance(data, dict) else data
        return self._items_from_packages(
            packages if isinstance(packages, list) else [],
            dataset_id,
        )

    def _list_dataset_packages(self, dataset_id: str) -> Any:
        """List root packages for a dataset, trying multiple ID formats."""
        attempts = []

        # 1) URL-encoded node ID (API spec says {id} is a string)
        if dataset_id.startswith("N:"):
            attempts.append(self._enc(dataset_id))

        # 2) Cached integer ID
        int_id = self._dataset_int_ids.get(dataset_id)
        if int_id is not None:
            attempts.append(str(int_id))

        # 3) Raw value (already an integer string or other format)
        if not dataset_id.startswith("N:"):
            attempts.append(dataset_id)

        last_err: Optional[Exception] = None
        for ds_id in attempts:
            try:
                logger.debug("Trying /datasets/%s/packages", ds_id)
                return self._get(
                    f"/datasets/{ds_id}/packages", params={"pageSize": 100}
                )
            except httpx.HTTPStatusError as exc:
                logger.debug(
                    "  -> %s %s", exc.response.status_code, ds_id
                )
                last_err = exc

        raise RuntimeError(
            f"Could not list packages for dataset {dataset_id}: {last_err}"
        )

    def _items_from_packages(
        self, packages: List[Any], dataset_id: str
    ) -> List[PlatformItem]:
        items: List[PlatformItem] = []
        for pkg in packages:
            content = pkg.get("content", {})
            pkg_type = content.get("packageType", "")
            node_id = content.get("nodeId") or content.get("id", "")
            is_dir = pkg_type == "Collection"
            items.append(
                PlatformItem(
                    id=str(node_id),
                    name=content.get("name", ""),
                    path=str(node_id) if is_dir else f"/{content.get('name', '')}",
                    type="directory" if is_dir else "file",
                    size=content.get("size", 0) or 0,
                    modified=content.get("updatedAt"),
                    platform=self.platform_name,
                    extra={"packageType": pkg_type, "dataset_id": dataset_id},
                )
            )
        return items

    def _parse_package_children(
        self, data: Any, dataset_id: str
    ) -> List[PlatformItem]:
        items: List[PlatformItem] = []
        children = []
        if isinstance(data, dict):
            children = data.get("children", [])
            if not children:
                files = data.get("objects", data.get("files", []))
                for f in files if isinstance(files, list) else []:
                    content = f.get("content", f)
                    items.append(
                        PlatformItem(
                            id=content.get("id", content.get("objectKey", "")),
                            name=content.get("name", content.get("fileName", "")),
                            path=content.get("s3key", content.get("name", "")),
                            type="file",
                            size=content.get("size", 0) or 0,
                            modified=content.get("updatedAt"),
                            platform=self.platform_name,
                            extra={"dataset_id": dataset_id},
                        )
                    )
                return items

        for child in children:
            content = child.get("content", {})
            pkg_type = content.get("packageType", "")
            items.append(
                PlatformItem(
                    id=content.get("id", ""),
                    name=content.get("name", ""),
                    path=f"/{content.get('name', '')}",
                    type="directory" if pkg_type == "Collection" else "file",
                    size=content.get("size", 0) or 0,
                    modified=content.get("updatedAt"),
                    platform=self.platform_name,
                    extra={"packageType": pkg_type, "dataset_id": dataset_id},
                )
            )
        return items

    # ------------------------------------------------------------ expand

    def expand_to_files(self, package_ids: List[str]) -> List[Dict[str, str]]:
        """Recursively expand a mix of file and folder (Collection) IDs.

        Returns a flat list of ``{"id": node_id, "name": filename, "rel_path": relative_path}``
        for every downloadable file, preserving the folder hierarchy in rel_path.
        """
        results: List[Dict[str, str]] = []
        for pid in package_ids:
            self._expand_recursive(pid, "", results)
        return results

    def _expand_recursive(
        self, pkg_id: str, prefix: str, out: List[Dict[str, str]]
    ) -> None:
        try:
            data = self._get(f"/packages/{self._enc(pkg_id)}")
        except Exception as e:
            logger.warning("Could not fetch package %s: %s", pkg_id, e)
            return

        content = data.get("content", {}) if isinstance(data, dict) else {}
        pkg_type = content.get("packageType", "")
        pkg_name = content.get("name", pkg_id)

        if pkg_type != "Collection":
            out.append({
                "id": pkg_id,
                "name": pkg_name,
                "rel_path": os.path.join(prefix, pkg_name) if prefix else pkg_name,
            })
            return

        children = data.get("children", []) if isinstance(data, dict) else []
        child_prefix = os.path.join(prefix, pkg_name) if prefix else pkg_name

        for child in children:
            child_content = child.get("content", {})
            child_node_id = child_content.get("nodeId") or child_content.get("id", "")
            child_type = child_content.get("packageType", "")
            child_name = child_content.get("name", "")

            if child_type == "Collection":
                self._expand_recursive(str(child_node_id), child_prefix, out)
            else:
                out.append({
                    "id": str(child_node_id),
                    "name": child_name,
                    "rel_path": os.path.join(child_prefix, child_name),
                })

    # ------------------------------------------------------------ download

    def _get_source_files(self, package_id: str) -> List[Dict[str, Any]]:
        """Return the source-file metadata list for a package."""
        data = self._get(f"/packages/{self._enc(package_id)}/files")
        files = data if isinstance(data, list) else data.get("files", [])
        return [f for f in files if isinstance(f, dict)]

    def get_download_info(self, file_id: str) -> Dict[str, str]:
        """Return ``{"url": presigned_url, "filename": real_name}`` for a package.

        Single method so callers can resolve the URL and the original
        filename without making duplicate API calls.
        """
        source_files = self._get_source_files(file_id)
        if not source_files:
            raise ValueError(f"Package {file_id} has no source files")

        content = source_files[0].get("content", source_files[0])
        source_id = content.get("id")
        if source_id is None:
            raise ValueError(f"No source file ID in package {file_id}")

        filename = content.get("fileName", content.get("name", ""))

        url_resp = self._get(
            f"/packages/{self._enc(file_id)}/files/{source_id}"
        )
        url = url_resp.get("url", "") if isinstance(url_resp, dict) else ""
        if not url:
            raise ValueError(f"No presigned URL returned for {file_id}/files/{source_id}")
        return {"url": url, "filename": filename}

    def get_download_url(self, file_id: str) -> str:
        """Get a pre-signed S3 URL for the first source file in a package."""
        return self.get_download_info(file_id)["url"]

    def download_file(self, file_id: str, local_path: str) -> str:
        url = self.get_download_url(file_id)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        with self._client.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        return str(Path(local_path).resolve())

    def download_bulk(
        self, file_ids: List[str], local_dir: str
    ) -> List[str]:
        os.makedirs(local_dir, exist_ok=True)
        paths: List[str] = []
        for fid in file_ids:
            source_files = self._get_source_files(fid)
            for sf in source_files:
                content = sf.get("content", sf)
                fname = content.get("name", content.get("fileName", fid))
                dest = os.path.join(local_dir, fname)
                paths.append(self.download_file(fid, dest))
        return paths

    # -------------------------------------------------------------- upload

    def upload_file(
        self,
        local_path: str,
        dataset_id: str,
        remote_path: str = "/",
    ) -> Dict[str, Any]:
        self._ensure_token()
        dest_id = "" if remote_path in ("/", "") else remote_path
        with open(local_path, "rb") as f:
            resp = self._client.post(
                f"{self._api_url}/packages/upload",
                headers=self._auth_headers(),
                data={"datasetId": dataset_id, "destinationId": dest_id},
                files={"file": (Path(local_path).name, f)},
            )
            resp.raise_for_status()
            return resp.json()

    # ----------------------------------------------------------- internals

    def _refresh_token(self) -> None:
        """Authenticate via AWS Cognito using the Pennsieve API key/secret.

        Flow:
        1. GET /authentication/cognito-config  -> Cognito pool app client ID + region
        2. boto3 cognito-idp initiate_auth      -> JWT access & id tokens
        3. Extract org from id_token claims and set bearer header
        """
        cognito_cfg_resp = self._client.get(f"{self._api_url}/authentication/cognito-config")
        cognito_cfg_resp.raise_for_status()
        cognito_cfg = cognito_cfg_resp.json()

        client_id = cognito_cfg["tokenPool"]["appClientId"]
        region = cognito_cfg.get("region", "us-east-1")

        cognito_client = boto3.client(
            "cognito-idp",
            region_name=region,
            aws_access_key_id="",
            aws_secret_access_key="",
        )

        auth_result = cognito_client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": self._api_key,
                "PASSWORD": self._api_secret,
            },
            ClientId=client_id,
        )

        tokens = auth_result["AuthenticationResult"]
        self._token = tokens["AccessToken"]
        expires_in = tokens.get("ExpiresIn", 3600)
        self._token_expires = time.time() + expires_in - _TOKEN_EXPIRY_BUFFER

        try:
            id_claims = jwt.get_unverified_claims(tokens["IdToken"])
            self._org_id = id_claims.get("custom:organization_node_id")
        except Exception:
            pass

    def _ensure_token(self) -> None:
        if not self._token or time.time() >= self._token_expires:
            if not self._api_key:
                raise RuntimeError("Not connected to Pennsieve")
            self._refresh_token()

    @staticmethod
    def _enc(node_id: str) -> str:
        """URL-encode a Pennsieve node ID (e.g. N:dataset:uuid -> N%3Adataset%3Auuid)."""
        return urllib.parse.quote(node_id, safe="")

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Authorization": f"Bearer {self._token}"}
        if self._org_id:
            headers["X-ORGANIZATION-ID"] = self._org_id
        return headers

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        self._ensure_token()
        resp = self._client.get(
            f"{self._api_url}{path}",
            headers=self._auth_headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: Optional[Dict] = None) -> Any:
        self._ensure_token()
        resp = self._client.post(
            f"{self._api_url}{path}",
            headers=self._auth_headers(),
            json=json_data,
        )
        resp.raise_for_status()
        return resp.json()
