"""
Transfer Manager -- orchestrates data movement between platforms and backends.

NIR acts as an orchestrator, keeping data off the NIR server when possible:

  Platform -> Local:       connector.download_file() -> local filesystem
  Platform -> Remote/HPC:  pre-signed URL + curl on HPC (direct, data bypasses NIR)
                           fallback: connector.download_file() -> temp -> SFTP
  Local -> Platform:       connector.upload_file() from local path
  Remote/HPC -> Platform:  SFTP one file at a time -> connector.upload_file()
"""

import logging
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _should_skip_work_path(path: str) -> bool:
    """Skip transient workflow working directories from platform uploads."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    return "work" in parts


class TransferRecord:
    """Tracks the state of a single transfer operation."""

    def __init__(
        self,
        transfer_id: str,
        direction: str,
        platform: str,
        file_ids: Optional[List[str]] = None,
        target_backend: str = "local",
        target_path: str = "",
        source_path: str = "",
        dataset_id: str = "",
    ):
        self.id = transfer_id
        self.direction = direction  # "download" or "upload"
        self.platform = platform
        self.file_ids = file_ids or []
        self.target_backend = target_backend
        self.target_path = target_path
        self.source_path = source_path
        self.dataset_id = dataset_id

        self.status = "pending"
        self.progress_percent = 0.0
        self.bytes_transferred = 0
        self.total_bytes = 0
        self.files_completed = 0
        self.total_files = len(self.file_ids) if self.file_ids else 0
        self.error: Optional[str] = None
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.local_paths: List[str] = []
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True
        self.status = "cancelled"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "direction": self.direction,
            "platform": self.platform,
            "progress_percent": round(self.progress_percent, 1),
            "bytes_transferred": self.bytes_transferred,
            "total_bytes": self.total_bytes,
            "files_completed": self.files_completed,
            "total_files": self.total_files,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "local_paths": self.local_paths,
            "target_path": self.target_path,
        }


class TransferManager:
    """Manages data transfers between platforms and processing backends."""

    def __init__(self):
        self._transfers: Dict[str, TransferRecord] = {}
        self._lock = threading.Lock()

    def start_download(
        self,
        platform: str,
        file_ids: List[str],
        target_backend: str,
        target_path: str,
    ) -> str:
        """Start an async download from platform to processing backend."""
        transfer_id = str(uuid.uuid4())
        record = TransferRecord(
            transfer_id=transfer_id,
            direction="download",
            platform=platform,
            file_ids=file_ids,
            target_backend=target_backend,
            target_path=target_path,
        )

        with self._lock:
            self._transfers[transfer_id] = record

        thread = threading.Thread(
            target=self._execute_download,
            args=(record,),
            daemon=True,
        )
        thread.start()

        return transfer_id

    def start_upload(
        self,
        source_backend: str,
        source_path: str,
        platform: str,
        dataset_id: str,
    ) -> str:
        """Start an async upload from processing backend to platform."""
        transfer_id = str(uuid.uuid4())

        files_to_upload = []
        if source_backend == "local":
            if os.path.isdir(source_path):
                for root, _dirs, filenames in os.walk(source_path):
                    for fname in filenames:
                        files_to_upload.append(os.path.join(root, fname))
            elif os.path.isfile(source_path):
                files_to_upload.append(source_path)

        record = TransferRecord(
            transfer_id=transfer_id,
            direction="upload",
            platform=platform,
            file_ids=files_to_upload,
            target_backend=source_backend,
            source_path=source_path,
            dataset_id=dataset_id,
        )
        record.total_files = len(files_to_upload)

        with self._lock:
            self._transfers[transfer_id] = record

        thread = threading.Thread(
            target=self._execute_upload,
            args=(record,),
            daemon=True,
        )
        thread.start()

        return transfer_id

    def get_progress(self, transfer_id: str) -> Optional[Dict[str, Any]]:
        record = self._transfers.get(transfer_id)
        if record is None:
            return None
        return record.to_dict()

    def cancel(self, transfer_id: str) -> None:
        record = self._transfers.get(transfer_id)
        if record:
            record.cancel()

    def list_transfers(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in sorted(
                self._transfers.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )[:50]]

    def start_move(
        self,
        source_type: str,
        source_path: str,
        source_file_ids: List[str],
        dest_type: str,
        dest_path: str,
    ) -> str:
        """Generic move: any source -> any destination."""
        transfer_id = str(uuid.uuid4())
        record = TransferRecord(
            transfer_id=transfer_id,
            direction="move",
            platform=f"{source_type}->{dest_type}",
            file_ids=source_file_ids or [],
            target_backend=dest_type,
            target_path=dest_path,
            source_path=source_path,
            dataset_id=dest_path,
        )
        record._source_type = source_type  # type: ignore[attr-defined]
        record._dest_type = dest_type  # type: ignore[attr-defined]

        with self._lock:
            self._transfers[transfer_id] = record

        thread = threading.Thread(
            target=self._execute_move,
            args=(record,),
            daemon=True,
        )
        thread.start()
        return transfer_id

    # -------------------------------------------------------- download logic

    def _execute_download(self, record: TransferRecord) -> None:
        """Download files from platform to processing backend."""
        try:
            record.status = "downloading"
            connector = self._get_connector(record.platform)

            self._expand_folders(record, connector)

            if record.target_backend == "local":
                self._download_to_local(record, connector)
            else:
                self._download_to_remote(record, connector)

            if not record.cancelled:
                record.status = "completed"
                record.progress_percent = 100
                record.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error("Transfer %s failed: %s", record.id, e)
            record.status = "failed"
            record.error = str(e)
            record.completed_at = datetime.utcnow()

    @staticmethod
    def _expand_folders(record: TransferRecord, connector) -> None:
        """Expand any folder IDs into individual file entries.

        If the connector supports ``expand_to_files`` (Pennsieve), any
        Collection/folder IDs are recursively resolved to their contained
        files.  The resolved file list replaces ``record.file_ids`` and a
        mapping of id -> relative path is stored so downloads preserve the
        directory hierarchy.
        """
        expand_fn = getattr(connector, "expand_to_files", None)
        if not expand_fn:
            return

        try:
            expanded = expand_fn(record.file_ids)
        except Exception as e:
            logger.warning("Folder expansion failed, transferring as-is: %s", e)
            return

        if not expanded:
            return

        record.file_ids = [entry["id"] for entry in expanded]
        record.total_files = len(record.file_ids)
        record._expanded_names = {  # type: ignore[attr-defined]
            entry["id"]: entry["rel_path"] for entry in expanded
        }
        logger.info(
            "Expanded %d selected items to %d files",
            len(set(record.file_ids)), len(expanded),
        )

    @staticmethod
    def _filename_from_id(file_id: str, index: int) -> str:
        """Extract a human-readable filename from a platform file_id."""
        basename = os.path.basename(file_id.rstrip("/"))
        if basename and not basename.startswith("N:") and len(basename) < 200:
            return basename
        return f"file_{index}"

    def _resolve_filename(self, connector, file_id: str, index: int) -> str:
        """Get the real filename from the connector, falling back to file_id."""
        try:
            info = connector.get_download_info(file_id)
            name = info.get("filename", "")
            if name:
                return name
        except Exception:
            pass
        return self._filename_from_id(file_id, index)

    def _download_to_local(self, record: TransferRecord, connector) -> None:
        """Platform -> local filesystem."""
        expanded = getattr(record, "_expanded_names", None)
        os.makedirs(record.target_path, exist_ok=True)
        for i, file_id in enumerate(record.file_ids):
            if record.cancelled:
                return
            try:
                info = self._get_download_info(connector, file_id, i, expanded)
                dest = os.path.join(record.target_path, info["fname"])
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                if info.get("url"):
                    with connector._client.stream("GET", info["url"]) as resp:
                        resp.raise_for_status()
                        with open(dest, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=65536):
                                f.write(chunk)
                    path = str(Path(dest).resolve())
                else:
                    path = connector.download_file(file_id, dest)
                record.local_paths.append(path)
            except Exception as e:
                logger.warning("Failed to download %s: %s", file_id, e)
            record.files_completed = i + 1
            record.progress_percent = ((i + 1) / record.total_files) * 100

    def _download_to_remote(self, record: TransferRecord, connector) -> None:
        """Platform -> HPC/remote.

        For platforms with pre-signed/public URLs (e.g. Pennsieve), NIR
        instructs the HPC to curl the file directly so data bypasses NIR.

        For session-authenticated platforms (XNAT) or URLs behind SSH tunnels,
        direct curl from HPC will fail, so we go straight to indirect:
        download to NIR temp -> SFTP to HPC.
        """
        from backend.core.ssh_manager import get_ssh_manager

        ssh = get_ssh_manager()

        try:
            ssh.execute(f'mkdir -p "{record.target_path}"')
        except Exception:
            pass

        expanded = getattr(record, "_expanded_names", None)

        # XNAT uses JSESSION cookies and is often behind an SSH tunnel
        # that only exists on the NIR server, so direct curl from HPC
        # cannot work.  Skip the attempt entirely.
        skip_direct = record.platform == "xnat"

        for i, file_id in enumerate(record.file_ids):
            if record.cancelled:
                return
            try:
                info = self._get_download_info(connector, file_id, i, expanded)
                fname = info["fname"]
                remote_dest = os.path.join(record.target_path, fname)

                remote_parent = os.path.dirname(remote_dest)
                if remote_parent != record.target_path:
                    try:
                        ssh.execute(f'mkdir -p "{remote_parent}"')
                    except Exception:
                        pass

                downloaded = False

                if not skip_direct:
                    try:
                        url = info.get("url") or connector.get_download_url(file_id)
                        exit_code, stdout, stderr = ssh.execute(
                            f'curl -fsSL -o "{remote_dest}" "{url}"',
                            timeout=600,
                        )
                        if exit_code == 0:
                            record.local_paths.append(remote_dest)
                            logger.info(
                                "Direct download %s -> %s complete",
                                fname, remote_dest,
                            )
                            downloaded = True
                        else:
                            raise RuntimeError(
                                f"curl failed (exit {exit_code}): {stderr[:200]}"
                            )
                    except Exception as direct_err:
                        logger.info(
                            "Direct download failed for %s, falling back to indirect: %s",
                            fname, direct_err,
                        )

                if not downloaded:
                    self._indirect_download_single(
                        connector, ssh, file_id, fname, remote_dest
                    )
                    record.local_paths.append(remote_dest)

            except Exception as e:
                logger.warning("Failed to transfer %s: %s", file_id, e)

            record.files_completed = i + 1
            record.progress_percent = ((i + 1) / record.total_files) * 100

    @staticmethod
    def _get_download_info(connector, file_id: str, index: int, expanded_names: dict | None = None) -> dict:
        """Get filename (with relative path) and URL from connector."""
        rel_path = (expanded_names or {}).get(file_id, "")

        try:
            info = connector.get_download_info(file_id)
            fname = rel_path or info.get("filename", "") or f"file_{index}"
            return {"fname": fname, "url": info.get("url", "")}
        except Exception:
            if not rel_path:
                fallback = os.path.basename(file_id.rstrip("/"))
                if not fallback or fallback.startswith("N:") or len(fallback) >= 200:
                    fallback = f"file_{index}"
                rel_path = fallback
            return {"fname": rel_path, "url": ""}

    @staticmethod
    def _indirect_download_single(connector, ssh, file_id, fname, remote_dest):
        """Fallback: platform -> NIR temp -> SFTP to remote."""
        with tempfile.TemporaryDirectory(prefix="neuroinsight_xfer_") as tmpdir:
            local_tmp = os.path.join(tmpdir, fname)
            connector.download_file(file_id, local_tmp)
            ssh.put_file(local_tmp, remote_dest)

    # ---------------------------------------------------------- upload logic

    def _execute_upload(self, record: TransferRecord) -> None:
        """Upload files from processing backend to platform."""
        try:
            record.status = "uploading"
            connector = self._get_connector(record.platform)

            if record.target_backend == "local":
                self._upload_from_local(record, connector)
            else:
                self._upload_from_remote(record, connector)

            if not record.cancelled:
                record.status = "completed"
                record.progress_percent = 100
                record.completed_at = datetime.utcnow()

        except Exception as e:
            logger.error("Upload %s failed: %s", record.id, e)
            record.status = "failed"
            record.error = str(e)
            record.completed_at = datetime.utcnow()

    def _upload_from_local(self, record: TransferRecord, connector) -> None:
        """Local filesystem -> platform."""
        local_files: list[str] = []
        if record.file_ids:
            for p in record.file_ids:
                if os.path.isdir(p):
                    if _should_skip_work_path(p):
                        continue
                    for root, dirs, filenames in os.walk(p):
                        dirs[:] = [d for d in dirs if d != "work"]
                        for fname in filenames:
                            fpath = os.path.join(root, fname)
                            if _should_skip_work_path(fpath):
                                continue
                            local_files.append(fpath)
                elif os.path.isfile(p):
                    if _should_skip_work_path(p):
                        continue
                    local_files.append(p)
        else:
            if os.path.isdir(record.source_path):
                for root, dirs, filenames in os.walk(record.source_path):
                    dirs[:] = [d for d in dirs if d != "work"]
                    for fname in filenames:
                        fpath = os.path.join(root, fname)
                        if _should_skip_work_path(fpath):
                            continue
                        local_files.append(fpath)
            elif os.path.isfile(record.source_path):
                if _should_skip_work_path(record.source_path):
                    record.source_path = ""
                else:
                    local_files.append(record.source_path)

        record.total_files = len(local_files)
        if record.total_files == 0:
            raise RuntimeError(
                f"No files found to upload from local path: {record.source_path}"
            )

        failed: list[str] = []
        for i, fpath in enumerate(local_files):
            if record.cancelled:
                return
            try:
                connector.upload_file(fpath, record.dataset_id)
            except Exception as e:
                logger.warning("Failed to upload %s: %s", fpath, e)
                failed.append(f"{fpath}: {e}")
            record.files_completed = i + 1
            record.progress_percent = ((i + 1) / record.total_files) * 100

        if failed:
            preview = "; ".join(failed[:3])
            raise RuntimeError(
                f"Failed to upload {len(failed)}/{record.total_files} files. {preview}"
            )

    def _upload_from_remote(self, record: TransferRecord, connector) -> None:
        """Remote/HPC -> platform.

        Pennsieve requires multipart upload via its API, so data must pass
        through NIR.  We stream each file individually via SFTP to a temp
        file, upload it, then immediately delete the temp copy to keep disk
        usage minimal (one file at a time instead of all at once).
        """
        from backend.core.ssh_manager import get_ssh_manager

        ssh = get_ssh_manager()

        upload_items: list[tuple[str, str]] = []
        remote_archives_to_cleanup: list[str] = []
        if record.file_ids:
            for p in record.file_ids:
                try:
                    if _should_skip_work_path(p):
                        continue
                    # Resolve path type robustly via shell test to avoid SFTP
                    # "Failure" ambiguity for symlinks/permission edge cases.
                    check_cmd = (
                        f'if [ -d "{p}" ]; then echo dir; '
                        f'elif [ -f "{p}" ]; then echo file; '
                        f'else echo missing; fi'
                    )
                    exit_code, stdout, _stderr = ssh.execute(check_cmd, timeout=60)
                    ptype = (stdout or "").strip() if exit_code == 0 else "missing"

                    if ptype == "dir":
                        # For selected folders, upload as archive to preserve
                        # structure and avoid thousands of tiny API calls.
                        token = uuid.uuid4().hex[:8]
                        base = os.path.basename(p.rstrip("/")) or "folder"
                        parent = os.path.dirname(p.rstrip("/")) or "/"
                        remote_archive = f"/tmp/neuroinsight_sel_{token}_{base}.tar.gz"
                        cmd = (
                            f'tar -C "{parent}" -czf "{remote_archive}" '
                            f'--exclude="{base}/work" "{base}"'
                        )
                        arc_code, _arc_out, arc_err = ssh.execute(cmd, timeout=1800)
                        if arc_code != 0:
                            raise RuntimeError(
                                f"Failed to archive selected folder {p}: {arc_err[:200]}"
                            )
                        upload_items.append((remote_archive, f"{base}.tar.gz"))
                        remote_archives_to_cleanup.append(remote_archive)
                    elif ptype == "file":
                        upload_items.append((p, os.path.basename(p)))
                except Exception as e:
                    logger.warning("Could not prepare selected path %s: %s", p, e)
        elif record.source_path:
            try:
                output_archives = self._build_output_archives_for_upload(ssh, record.source_path)
                if output_archives:
                    upload_items = output_archives
                    remote_archives_to_cleanup = [p for p, _ in output_archives]
                else:
                    remote_files = self._collect_remote_files_recursive(ssh, record.source_path)
                    upload_items = [(p, os.path.basename(p)) for p in remote_files]
            except Exception as e:
                logger.debug(
                    "Could not list remote dir %s, treating as single file: %s",
                    record.source_path, e,
                )
                upload_items = [(record.source_path, os.path.basename(record.source_path))]

        record.total_files = len(upload_items)
        if record.total_files == 0:
            raise RuntimeError(
                f"No files found to upload from remote path: {record.source_path}"
            )

        failed: list[str] = []
        completed_units = 0
        try:
            for remote_path, upload_name in upload_items:
                if record.cancelled:
                    return
                try:
                    # Preserve upload_name in platform by staging with that filename.
                    with tempfile.TemporaryDirectory(prefix="neuroinsight_up_") as tmpdir:
                        local_tmp = os.path.join(tmpdir, upload_name)
                        ssh.get_file(remote_path, local_tmp)
                        uploaded_units = self._upload_with_fallbacks(
                            connector, local_tmp, record.dataset_id
                        )
                        if uploaded_units > 1:
                            record.total_files += (uploaded_units - 1)
                        completed_units += uploaded_units
                except Exception as e:
                    logger.warning("Failed to upload %s: %s", remote_path, e)
                    failed.append(f"{remote_path}: {e}")
                    completed_units += 1

                record.files_completed = completed_units
                record.progress_percent = (
                    completed_units / max(record.total_files, 1)
                ) * 100

            if failed:
                preview = "; ".join(failed[:3])
                raise RuntimeError(
                    f"Failed to upload {len(failed)}/{record.total_files} files. {preview}"
                )
        finally:
            for archive_path in remote_archives_to_cleanup:
                try:
                    ssh.execute(f'rm -f "{archive_path}"', timeout=60)
                except Exception:
                    pass

    @staticmethod
    def _collect_remote_files_recursive(ssh, root_path: str) -> list[str]:
        """Return all files under remote root_path (recursive).

        If root_path itself is a file, returns [root_path].
        """
        stack = [root_path]
        files: list[str] = []

        while stack:
            current = stack.pop()
            listing = ssh.list_dir(current)
            if not listing:
                continue
            for entry in listing:
                entry_type = entry.get("type")
                entry_path = entry.get("path")
                if not entry_path:
                    continue
                if entry_type == "directory":
                    if entry.get("name") == "work":
                        continue
                    stack.append(entry_path)
                elif entry_type == "file":
                    if _should_skip_work_path(entry_path):
                        continue
                    files.append(entry_path)

        return files

    @staticmethod
    def _build_output_archives_for_upload(
        ssh, source_path: str
    ) -> list[tuple[str, str]]:
        """Build bundle/native/work archives when source_path is outputs directory."""
        preferred_dirs = ("bundle", "native")
        listing = ssh.list_dir(source_path)
        if not listing:
            return []

        present = {
            entry.get("name")
            for entry in listing
            if entry.get("type") == "directory" and entry.get("name") in preferred_dirs
        }
        if not present:
            return []

        token = uuid.uuid4().hex[:8]
        archives: list[tuple[str, str]] = []
        for folder in preferred_dirs:
            if folder not in present:
                continue
            remote_archive = f"/tmp/neuroinsight_{token}_{folder}.tar.gz"
            cmd = (
                f'tar -C "{source_path}" -czf "{remote_archive}" "{folder}"'
            )
            exit_code, _stdout, stderr = ssh.execute(cmd, timeout=1800)
            if exit_code != 0:
                raise RuntimeError(
                    f"Failed to archive {folder} for upload: {stderr[:200]}"
                )
            archives.append((remote_archive, f"{folder}.tar.gz"))

        return archives

    @staticmethod
    def _upload_with_fallbacks(connector, local_path: str, dataset_id: str) -> int:
        """Upload file with retries for common Pennsieve API limits.

        Returns number of uploaded units (1 for normal upload, N for split parts).
        """
        try:
            TransferManager._upload_with_405_retry(connector, local_path, dataset_id)
            return 1
        except Exception as first_err:
            err_text = str(first_err)

            # 413 is payload too large; split into 100 MB chunks and upload parts.
            if " 413" in err_text or "413 " in err_text:
                parts = TransferManager._split_file(local_path, 100 * 1024 * 1024)
                try:
                    for part in parts:
                        TransferManager._upload_with_405_retry(connector, part, dataset_id)
                    return len(parts)
                finally:
                    for part in parts:
                        try:
                            os.remove(part)
                        except Exception:
                            pass

            raise

    @staticmethod
    def _split_file(local_path: str, chunk_bytes: int) -> list[str]:
        """Split local_path into numbered part files and return their paths."""
        part_paths: list[str] = []
        part_idx = 1
        token = uuid.uuid4().hex[:8]
        with open(local_path, "rb") as src:
            while True:
                chunk = src.read(chunk_bytes)
                if not chunk:
                    break
                part_path = f"{local_path}.{token}.part{part_idx:03d}"
                with open(part_path, "wb") as dst:
                    dst.write(chunk)
                part_paths.append(part_path)
                part_idx += 1
        return part_paths

    @staticmethod
    def _upload_with_405_retry(connector, local_path: str, dataset_id: str) -> None:
        """Upload file and retry once with unique name on HTTP 405."""
        try:
            connector.upload_file(local_path, dataset_id)
            return
        except Exception as e:
            err_text = str(e)
            if " 405" not in err_text and "405 " not in err_text:
                raise

        parent = os.path.dirname(local_path)
        stem, ext = os.path.splitext(os.path.basename(local_path))
        unique_path = os.path.join(parent, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        shutil.copy2(local_path, unique_path)
        try:
            connector.upload_file(unique_path, dataset_id)
        finally:
            try:
                os.remove(unique_path)
            except Exception:
                pass

    # -------------------------------------------------- generic move logic

    BACKEND_TYPES = {"local", "remote", "hpc"}
    EXTERNAL_TYPES = {"pennsieve", "xnat"}

    def _execute_move(self, record: TransferRecord) -> None:
        """Route a move through the appropriate path."""
        try:
            record.status = "transferring"
            src = record._source_type  # type: ignore[attr-defined]
            dst = record._dest_type  # type: ignore[attr-defined]

            if src in self.EXTERNAL_TYPES and dst in self.BACKEND_TYPES:
                record.direction = "download"
                record.platform = src
                record.target_backend = dst
                self._execute_download(record)
                return
            if src in self.BACKEND_TYPES and dst in self.EXTERNAL_TYPES:
                record.direction = "upload"
                record.platform = dst
                record.target_backend = src
                self._execute_upload(record)
                return
            if src in self.EXTERNAL_TYPES and dst in self.EXTERNAL_TYPES:
                self._move_platform_to_platform(record, src, dst)
                return
            if src in self.BACKEND_TYPES and dst in self.BACKEND_TYPES:
                self._move_backend_to_backend(record, src, dst)
                return

            raise RuntimeError(f"Unsupported transfer path: {src} -> {dst}")

        except Exception as e:
            logger.error("Move %s failed: %s", record.id, e)
            record.status = "failed"
            record.error = str(e)
            record.completed_at = datetime.utcnow()

    def _move_platform_to_platform(
        self, record: TransferRecord, src_platform: str, dst_platform: str
    ) -> None:
        """Platform -> temp local -> Platform."""
        src_connector = self._get_connector(src_platform)
        dst_connector = self._get_connector(dst_platform)

        with tempfile.TemporaryDirectory(prefix="neuroinsight_p2p_") as tmpdir:
            file_ids = record.file_ids
            record.total_files = len(file_ids)

            for i, fid in enumerate(file_ids):
                if record.cancelled:
                    return
                try:
                    fname = self._filename_from_id(fid, i)
                    tmp_path = os.path.join(tmpdir, fname)
                    src_connector.download_file(fid, tmp_path)
                    dst_connector.upload_file(tmp_path, record.dataset_id)
                except Exception as e:
                    logger.warning("P2P transfer file %s: %s", fid, e)

                record.files_completed = i + 1
                record.progress_percent = ((i + 1) / max(record.total_files, 1)) * 100

            if not record.cancelled:
                record.status = "completed"
                record.progress_percent = 100
                record.completed_at = datetime.utcnow()

    def _move_backend_to_backend(
        self, record: TransferRecord, src_backend: str, dst_backend: str
    ) -> None:
        """Backend -> Backend via SSH/local copy."""
        from backend.core.ssh_manager import get_ssh_manager

        ssh = get_ssh_manager()

        src_files: List[str] = []
        if src_backend == "local":
            if os.path.isdir(record.source_path):
                for root, _dirs, filenames in os.walk(record.source_path):
                    for fname in filenames:
                        src_files.append(os.path.join(root, fname))
            elif os.path.isfile(record.source_path):
                src_files.append(record.source_path)
        else:
            try:
                listing = ssh.list_dir(record.source_path)
                src_files = [f["path"] for f in listing if f.get("type") == "file"]
            except Exception as e:
                logger.debug("Could not list source dir %s, treating as single file: %s", record.source_path, e)
                src_files = [record.source_path]

        record.total_files = len(src_files)

        with tempfile.TemporaryDirectory(prefix="neuroinsight_b2b_") as tmpdir:
            for i, fpath in enumerate(src_files):
                if record.cancelled:
                    return
                try:
                    fname = os.path.basename(fpath)
                    if src_backend != "local":
                        local_tmp = os.path.join(tmpdir, fname)
                        ssh.get_file(fpath, local_tmp)
                    else:
                        local_tmp = fpath

                    if dst_backend == "local":
                        os.makedirs(record.target_path, exist_ok=True)
                        dest = os.path.join(record.target_path, fname)
                        if local_tmp != dest:
                            import shutil
                            shutil.copy2(local_tmp, dest)
                    else:
                        remote_dest = os.path.join(record.target_path, fname)
                        ssh.put_file(local_tmp, remote_dest)
                except Exception as e:
                    logger.warning("B2B transfer file %s: %s", fpath, e)

                record.files_completed = i + 1
                record.progress_percent = ((i + 1) / max(record.total_files, 1)) * 100

            if not record.cancelled:
                record.status = "completed"
                record.progress_percent = 100
                record.completed_at = datetime.utcnow()

    # ----------------------------------------------------------- helpers

    def _get_connector(self, platform: str):
        from backend.routes.platform import _get_connector as get_conn

        connector = get_conn(platform)
        if not connector.is_connected():
            raise RuntimeError(f"Not connected to {platform}")
        return connector


@lru_cache()
def get_transfer_manager() -> TransferManager:
    """Get the singleton TransferManager."""
    return TransferManager()
