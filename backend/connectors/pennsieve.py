"""
Pennsieve platform connector.

Communicates with the Pennsieve REST API using httpx.
Auth: API key + secret -> AWS Cognito -> JWT access token.
Hierarchy: Workspace -> Datasets -> Packages -> Files.
"""

import logging
import os
import re
import shutil
import socket
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import httpx
from jose import jwt
from httpx import HTTPStatusError

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
        self._dataset_packages_cache: Dict[str, Tuple[float, List[Any]]] = {}
        self._dataset_packages_cache_ttl_sec: int = 20
        self._agent_target: str = os.getenv("PENNSIEVE_AGENT_TARGET", "localhost:9000")

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

        # Best-effort: prepare/start local agent during connect so users do not
        # need a separate manual step.
        prepared_target, _prep_err = self._prepare_agent_target(self._agent_target)
        self._set_agent_target(prepared_target)
        _chosen, _auto_err = self._maybe_autostart_agent(prepared_target)
        if _chosen:
            self._set_agent_target(_chosen)

        agent = self.agent_status()
        return {
            "connected": True,
            "user": self._user,
            "workspace": self._organization or "",
            "platform": self.platform_name,
            "agent_target": agent.get("agent_target"),
            "agent_ready_for_upload": agent.get("ready_for_upload", False),
            "agent_error": agent.get("error"),
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
        self._dataset_packages_cache.clear()
        self._agent_target = os.getenv("PENNSIEVE_AGENT_TARGET", "localhost:9000")

    def is_connected(self) -> bool:
        return self._token is not None and time.time() < self._token_expires

    def status(self) -> Dict[str, Any]:
        return {
            "platform": self.platform_name,
            "connected": self.is_connected(),
            "user": self._user,
            "workspace": self._organization,
            "agent_target": self._agent_target,
        }

    def agent_status(self) -> Dict[str, Any]:
        """Return Pennsieve Agent readiness for manifest uploads."""
        agent_target, target_err = self._prepare_agent_target(self._agent_target)
        status: Dict[str, Any] = {
            "agent_target": agent_target,
            "agent_reachable": False,
            "profile_available": False,
            "ready_for_upload": False,
            "error": None,
        }
        if target_err:
            status["error"] = target_err
            return status

        host, port = self._parse_agent_target(agent_target)
        status["agent_reachable"] = self._is_tcp_reachable(host, port)
        if not status["agent_reachable"]:
            chosen_target, auto_err = self._maybe_autostart_agent(agent_target)
            if chosen_target:
                self._set_agent_target(chosen_target)
                agent_target = chosen_target
                status["agent_target"] = agent_target
                host, port = self._parse_agent_target(agent_target)
                status["agent_reachable"] = self._is_tcp_reachable(host, port)
            if not status["agent_reachable"]:
                status["error"] = auto_err or f"Could not connect to Pennsieve Agent at {agent_target}"
                return status

        # Lightweight profile check for readiness display.
        cfg = Path.home() / ".pennsieve" / "config.ini"
        status["profile_available"] = cfg.exists() and cfg.is_file() and cfg.stat().st_size > 0
        if not status["profile_available"]:
            status["error"] = (
                "Pennsieve profile/config unavailable. Run `pennsieve config wizard` once."
            )
            return status

        status["ready_for_upload"] = True

        return status

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
        # Pennsieve dataset package listings are flat and can include both
        # folders and files from many levels. At root view we only show
        # top-level folders (Collections) so files stay inside folders until
        # users navigate into them.
        if isinstance(packages, list):
            # Keep only true top-level folders at dataset root. Pennsieve's
            # dataset package listing is flat and can contain nested folders
            # and files; top-level items are marked with parentId=None.
            packages = [
                pkg
                for pkg in packages
                if (pkg.get("content", {}) or {}).get("packageType") == "Collection"
                and ((pkg.get("content", {}) or {}).get("parentId") is None)
            ]
        return self._items_from_packages(
            packages if isinstance(packages, list) else [],
            dataset_id,
        )

    def _list_dataset_packages(self, dataset_id: str) -> Any:
        """List all dataset packages, trying multiple ID formats."""
        now = time.time()
        cached = self._dataset_packages_cache.get(dataset_id)
        if cached and (now - cached[0]) <= self._dataset_packages_cache_ttl_sec:
            return {"packages": cached[1]}

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
                all_packages: List[Any] = []
                cursor: Optional[str] = None
                seen_cursors: set[str] = set()
                while True:
                    params: Dict[str, Any] = {"pageSize": 100}
                    if cursor:
                        params["cursor"] = cursor
                    page = self._get(f"/datasets/{ds_id}/packages", params=params)
                    if isinstance(page, dict):
                        page_packages = page.get("packages", [])
                        if isinstance(page_packages, list):
                            all_packages.extend(page_packages)
                        next_cursor = page.get("cursor")
                        if not isinstance(next_cursor, str) or not next_cursor:
                            break
                        if next_cursor in seen_cursors:
                            break
                        seen_cursors.add(next_cursor)
                        cursor = next_cursor
                        continue
                    if isinstance(page, list):
                        all_packages.extend(page)
                    break
                self._dataset_packages_cache[dataset_id] = (time.time(), all_packages)
                return {"packages": all_packages}
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
            if str(content.get("state", "")).upper() == "DELETED":
                continue
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
            if str(content.get("state", "")).upper() == "DELETED":
                continue
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
        agent_error: Optional[Exception] = None
        upload_mode = os.getenv("PENNSIEVE_UPLOAD_MODE", "agent_first").strip().lower()

        # Primary path: agent/manifest upload.
        if upload_mode != "direct":
            try:
                return self._upload_file_via_agent_manifest(local_path, dataset_id, remote_path)
            except Exception as e:
                agent_error = e
                logger.warning("Pennsieve agent/manifest upload unavailable: %s", e)

        # Legacy fallback path: direct API upload.
        self._ensure_token()
        payload = {"datasetId": dataset_id}
        if remote_path not in ("/", ""):
            payload["destinationId"] = remote_path
        with open(local_path, "rb") as f:
            resp = self._client.post(
                f"{self._api_url}/packages/upload",
                headers=self._auth_headers(),
                data=payload,
                files={"file": (Path(local_path).name, f)},
            )
            try:
                resp.raise_for_status()
                return resp.json()
            except HTTPStatusError as e:
                # Pennsieve API in many workspaces no longer accepts POST on
                # /packages/upload (returns 405 with Allow: GET, PUT, HEAD).
                # Surface a precise message so users know this is an upstream
                # API mode mismatch, not a bad file selection in NIR.
                if resp.status_code == 405:
                    allow = resp.headers.get("allow", "")
                    if agent_error:
                        raise RuntimeError(
                            "Pennsieve direct API upload endpoint rejected POST "
                            f"(HTTP 405, Allow: {allow or 'unknown'}). "
                            "Agent/manifest fallback also failed: "
                            f"{agent_error}"
                        ) from e
                    raise RuntimeError(
                        "Pennsieve direct API upload endpoint rejected POST "
                        f"(HTTP 405, Allow: {allow or 'unknown'}). "
                        "This workspace requires Agent/manifest-based uploads."
                    ) from e
                raise

    def _upload_file_via_agent_manifest(
        self,
        local_path: str,
        dataset_id: str,
        remote_path: str = "/",
    ) -> Dict[str, Any]:
        """Upload one file via Pennsieve Agent manifest workflow."""
        target_base_path = (remote_path or "").strip()
        if target_base_path in ("", "/"):
            target_base_path = ""
        else:
            if not target_base_path.startswith("/"):
                target_base_path = f"/{target_base_path}"

        agent = self.agent_status()
        agent_target = str(agent.get("agent_target") or self._agent_target)
        if not agent.get("ready_for_upload", False):
            raise RuntimeError(
                str(agent.get("error") or f"Pennsieve Agent is not ready at {agent_target}.")
            )

        abs_path = str(Path(local_path).resolve())
        if not os.path.isfile(abs_path):
            raise RuntimeError(f"Upload source is not a file: {abs_path}")

        file_name = os.path.basename(abs_path)
        host, port = self._parse_agent_target(agent_target)
        if host not in {"localhost", "127.0.0.1"}:
            raise RuntimeError(
                f"Pennsieve CLI upload requires local agent target, got {agent_target}"
            )

        env = os.environ.copy()
        env["PENNSIEVE_AGENT_PORT"] = str(port)

        if shutil.which("pennsieve") is None:
            raise RuntimeError("Pennsieve CLI not found on PATH.")

        try:
            subprocess.run(
                ["pennsieve", "dataset", "use", dataset_id],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=60,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            raise RuntimeError(f"Failed to select Pennsieve dataset {dataset_id}: {detail}") from e

        create_cmd = ["pennsieve", "manifest", "create"]
        if target_base_path:
            create_cmd.extend(["--target_path", target_base_path])
        create_cmd.append(abs_path)

        try:
            create = subprocess.run(
                create_cmd,
                check=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            raise RuntimeError(f"Failed to create Pennsieve manifest: {detail}") from e

        output = (create.stdout or "") + "\n" + (create.stderr or "")
        m = re.search(r"Manifest ID:\s*([0-9]+)", output)
        if not m:
            raise RuntimeError(f"Could not parse Pennsieve manifest ID from output: {output.strip()}")
        manifest_id = int(m.group(1))

        try:
            subprocess.run(
                ["pennsieve", "upload", "manifest", str(manifest_id)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=int(os.getenv("PENNSIEVE_AGENT_UPLOAD_TIMEOUT_SEC", "1800")),
            )
            subprocess.run(
                ["pennsieve", "manifest", "sync", str(manifest_id)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
                timeout=600,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            raise RuntimeError(
                f"Pennsieve manifest upload/sync failed for {manifest_id}: {detail}"
            ) from e
        finally:
            try:
                subprocess.run(
                    ["pennsieve", "manifest", "delete", str(manifest_id)],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=30,
                )
            except Exception:
                pass

        return {
            "status": "uploaded_via_agent",
            "manifest_id": manifest_id,
            "dataset_id": dataset_id,
            "file": file_name,
            "agent_target": agent_target,
        }

    @staticmethod
    def _assert_agent_target_not_minio(agent_target: str) -> None:
        """Detect common local port conflict where MinIO occupies agent port."""
        host, sep, port_str = agent_target.partition(":")
        if not sep:
            host = "localhost"
            port_str = agent_target
        try:
            port = int(port_str)
        except Exception:
            return

        try:
            with socket.create_connection((host, port), timeout=1.0) as sock:
                sock.sendall(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
                banner = sock.recv(256).decode("latin-1", errors="ignore")
        except Exception:
            return

        if "MinIO" in banner:
            raise RuntimeError(
                f"PENNSIEVE_AGENT_TARGET points to MinIO at {agent_target}. "
                "Run Pennsieve Agent on another port and set PENNSIEVE_AGENT_TARGET "
                "(for example: 127.0.0.1:11235)."
            )

    @staticmethod
    def _maybe_autostart_agent(agent_target: str) -> Tuple[str, Optional[str]]:
        """Best-effort local auto-start for Pennsieve Agent.

        Returns (chosen_target, error_message). On success, error_message is None.
        """
        autostart = os.getenv("PENNSIEVE_AGENT_AUTOSTART", "1").strip().lower()
        if autostart in {"0", "false", "no", "off"}:
            return (
                agent_target,
                (
                    f"Pennsieve Agent is not reachable at {agent_target}. "
                    "Auto-start is disabled (PENNSIEVE_AGENT_AUTOSTART=0)."
                ),
            )

        host, port = PennsieveConnector._parse_agent_target(agent_target)
        if host not in {"localhost", "127.0.0.1"}:
            return (
                agent_target,
                (
                    f"Pennsieve Agent is not reachable at {agent_target}. "
                    "Auto-start only supports local targets."
                ),
            )

        if shutil.which("pennsieve") is None:
            return (
                agent_target,
                (
                    "Pennsieve CLI not found on PATH. Install it to enable "
                    "automatic Pennsieve Agent startup."
                ),
            )

        candidate_target = f"127.0.0.1:{port}"
        if not PennsieveConnector._is_local_port_available(port):
            free_port = PennsieveConnector._find_free_local_port(9000, 9100)
            if free_port is None:
                return (
                    agent_target,
                    "No free local port found for Pennsieve Agent in range 9000-9100.",
                )
            candidate_target = f"127.0.0.1:{free_port}"
            port = free_port

        env = os.environ.copy()
        env["PENNSIEVE_AGENT_PORT"] = str(port)
        try:
            subprocess.Popen(
                ["pennsieve", "agent"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
        except Exception as e:
            return (agent_target, f"Failed to auto-start Pennsieve Agent: {e}")

        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                    return (candidate_target, None)
            except Exception:
                time.sleep(0.4)

        return (
            candidate_target,
            f"Pennsieve Agent did not become ready at {candidate_target} after auto-start attempt.",
        )

    @staticmethod
    def _parse_agent_target(agent_target: str) -> Tuple[str, int]:
        host, sep, port_str = (agent_target or "").partition(":")
        if not sep:
            host = "localhost"
            port_str = (agent_target or "").strip()
        host = host or "localhost"
        if not port_str:
            port_str = "9000"
        return host, int(port_str)

    @staticmethod
    def _is_local_port_available(port: int) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    @staticmethod
    def _find_free_local_port(start: int, end: int) -> Optional[int]:
        for port in range(start, end + 1):
            if PennsieveConnector._is_local_port_available(port):
                return port
        return None

    @staticmethod
    def _find_reachable_agent_target(pennsieve_cls) -> Optional[str]:
        """Find an already running local agent between ports 9000-9100."""
        for port in range(9000, 9101):
            target = f"127.0.0.1:{port}"
            try:
                if not PennsieveConnector._is_tcp_reachable("127.0.0.1", port):
                    continue
                PennsieveConnector._assert_agent_target_not_minio(target)
                pennsieve_cls(connect=True, target=target)
                return target
            except Exception:
                continue
        return None

    @staticmethod
    def _is_tcp_reachable(host: str, port: int, timeout: float = 0.75) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _prepare_agent_target(self, current_target: str) -> Tuple[str, Optional[str]]:
        """Normalize agent target and switch away from MinIO/invalid defaults."""
        target = (current_target or "").strip() or os.getenv(
            "PENNSIEVE_AGENT_TARGET", "localhost:9000"
        )
        try:
            host, port = self._parse_agent_target(target)
        except Exception:
            return target, f"Invalid PENNSIEVE_AGENT_TARGET '{target}'"

        if host not in {"localhost", "127.0.0.1"}:
            self._set_agent_target(target)
            return target, None

        local_target = f"127.0.0.1:{port}"
        try:
            self._assert_agent_target_not_minio(local_target)
            self._set_agent_target(local_target)
            return local_target, None
        except Exception:
            free_port = self._find_free_local_port(9000, 9100)
            if free_port is None:
                return (
                    local_target,
                    "Could not find free agent port in range 9000-9100.",
                )
            chosen = f"127.0.0.1:{free_port}"
            self._set_agent_target(chosen)
            return chosen, None

    def _set_agent_target(self, target: str) -> None:
        self._agent_target = target
        os.environ["PENNSIEVE_AGENT_TARGET"] = target

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
