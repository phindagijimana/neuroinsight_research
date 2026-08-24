"""
Shared helpers for resumable / large-file transfer I/O.

Used by every Transfer page combination (platform↔local↔remote/HPC).
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Optional

from backend.core import transfer_settings as ts

logger = logging.getLogger(__name__)


def shell_single_quote(value: str) -> str:
    """Safe single-quoted string for remote shell commands."""
    return "'" + value.replace("'", "'\"'\"'") + "'"


def local_file_size(path: str) -> Optional[int]:
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def remote_file_size(ssh, remote_path: str) -> Optional[int]:
    """Return remote file size in bytes, or None if missing / unreadable."""
    q = shell_single_quote(remote_path)
    cmd = (
        f"if [ -f {q} ]; then "
        f"(stat -c %s {q} 2>/dev/null || stat -f %z {q} 2>/dev/null); "
        f"fi"
    )
    try:
        rc, out, _ = ssh.execute(cmd, timeout=30)
    except Exception as e:
        logger.debug("remote_file_size failed for %s: %s", remote_path, e)
        return None
    if rc != 0 or not (out or "").strip().isdigit():
        return None
    return int(out.strip())


def destination_complete(
    *,
    ssh=None,
    local_path: Optional[str] = None,
    remote_path: Optional[str] = None,
    expected_size: Optional[int] = None,
) -> bool:
    """True when destination exists and matches expected_size (if known)."""
    if not ts.SKIP_COMPLETE_FILES:
        return False

    actual: Optional[int] = None
    if local_path is not None:
        actual = local_file_size(local_path)
    elif remote_path is not None and ssh is not None:
        actual = remote_file_size(ssh, remote_path)
    else:
        return False

    if actual is None or actual <= 0:
        return False
    if expected_size is not None and expected_size > 0:
        return actual == expected_size
    return False


def resolve_expected_size(
    explicit: Optional[int],
    *,
    ssh=None,
    source_local: Optional[str] = None,
    source_remote: Optional[str] = None,
) -> Optional[int]:
    """Best-effort source size for skip-if-complete on destination."""
    if explicit is not None and explicit > 0:
        return explicit
    if source_local:
        return local_file_size(source_local)
    if source_remote and ssh is not None:
        return remote_file_size(ssh, source_remote)
    return None


def stream_download_resumable(
    client: Any,
    url: str,
    dest_path: str,
    chunk_size: Optional[int] = None,
    extra_headers: Optional[dict[str, str]] = None,
    cookies: Optional[dict[str, str]] = None,
) -> None:
    """HTTP GET with Range resume into dest_path."""
    chunk_size = chunk_size or ts.DOWNLOAD_CHUNK_BYTES
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    existing = dest.stat().st_size if dest.exists() else 0
    headers: dict[str, str] = dict(extra_headers or {})
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    with client.stream("GET", url, headers=headers, cookies=cookies) as resp:
        if resp.status_code == 416:
            return
        if existing > 0 and resp.status_code == 200:
            existing = 0
        mode = "ab" if existing > 0 and resp.status_code in (206, 416) else "wb"
        with open(dest, mode) as handle:
            for chunk in resp.iter_bytes(chunk_size=chunk_size):
                handle.write(chunk)


def platform_download_file(
    connector: Any,
    file_id: str,
    dest_path: str,
    expected_size: Optional[int] = None,
) -> None:
    """Platform -> local path with Range resume when URL + HTTP client available."""
    if destination_complete(local_path=dest_path, expected_size=expected_size):
        logger.info("Skipping complete platform download at %s", dest_path)
        return

    info: dict = {}
    if hasattr(connector, "get_download_info"):
        try:
            info = connector.get_download_info(file_id) or {}
        except Exception as e:
            logger.debug("get_download_info failed for %s: %s", file_id, e)

    url = info.get("url")
    if not url and hasattr(connector, "get_download_url"):
        try:
            url = connector.get_download_url(file_id)
        except Exception:
            url = None

    client = getattr(connector, "_client", None)
    cookies = None
    session = getattr(connector, "_session_cookie", None)
    if session:
        cookies = {"JSESSIONID": session}

    if url and client is not None:
        stream_download_resumable(client, url, dest_path, cookies=cookies)
        return

    connector.download_file(file_id, dest_path)


def curl_download_remote(
    ssh,
    *,
    url: str,
    remote_dest: str,
    timeout_sec: Optional[int] = None,
) -> tuple[bool, str]:
    """curl -C - on remote host. Returns (ok, stderr snippet)."""
    timeout_sec = timeout_sec or ts.CURL_TIMEOUT_SEC
    dest_q = shell_single_quote(remote_dest)
    url_q = shell_single_quote(url)
    cmd = f"curl -fL -C - -o {dest_q} {url_q}"
    rc, _stdout, stderr = ssh.execute(cmd, timeout=timeout_sec)
    return rc == 0, (stderr or "")[:400]


def curl_download_with_retries(
    ssh,
    *,
    url_supplier: Callable[[], str],
    remote_dest: str,
    timeout_sec: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> None:
    """Retry direct curl; fresh URL each attempt; curl -C - resumes partials."""
    timeout_sec = timeout_sec or ts.CURL_TIMEOUT_SEC
    max_retries = max_retries or ts.CURL_MAX_RETRIES
    last_err = ""
    for attempt in range(1, max_retries + 1):
        url = url_supplier()
        ok, err = curl_download_remote(
            ssh, url=url, remote_dest=remote_dest, timeout_sec=timeout_sec
        )
        if ok:
            return
        last_err = err
        logger.warning(
            "Direct curl attempt %d/%d for %s failed: %s",
            attempt,
            max_retries,
            remote_dest,
            err,
        )
    raise RuntimeError(
        f"curl failed after {max_retries} attempts for {remote_dest}: {last_err}"
    )


def scp_get_file(
    ssh,
    remote_path: str,
    local_path: str,
    expected_size: Optional[int] = None,
) -> None:
    """Remote -> local via SFTP/scp; skip when destination already complete."""
    size = resolve_expected_size(
        expected_size, ssh=ssh, source_remote=remote_path
    )
    if destination_complete(local_path=local_path, expected_size=size):
        logger.info("Skipping complete scp get %s -> %s", remote_path, local_path)
        return
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    ssh.get_file(remote_path, local_path, timeout=ts.SCP_TIMEOUT_SEC)


def scp_put_file(
    ssh,
    local_path: str,
    remote_path: str,
    expected_size: Optional[int] = None,
) -> None:
    """Local -> remote via SFTP/scp; skip when destination already complete."""
    size = resolve_expected_size(expected_size, source_local=local_path)
    if destination_complete(ssh=ssh, remote_path=remote_path, expected_size=size):
        logger.info("Skipping complete scp put %s -> %s", local_path, remote_path)
        return
    remote_dir = str(PurePosixPath(remote_path).parent)
    ssh.execute(f'mkdir -p "{remote_dir}"', timeout=30)
    ssh.put_file(local_path, remote_path, timeout=ts.SCP_TIMEOUT_SEC)


def copy_local_file(
    src_path: str,
    dest_path: str,
    expected_size: Optional[int] = None,
) -> None:
    """Local -> local copy; skip when destination already complete."""
    size = resolve_expected_size(expected_size, source_local=src_path)
    if destination_complete(local_path=dest_path, expected_size=size):
        logger.info("Skipping complete local copy %s -> %s", src_path, dest_path)
        return
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    if os.path.exists(dest_path) and os.path.exists(src_path):
        try:
            if os.path.samefile(src_path, dest_path):
                return
        except OSError:
            pass
    shutil.copy2(src_path, dest_path)


def remote_copy_file(
    ssh,
    src_remote: str,
    dest_remote: str,
    expected_size: Optional[int] = None,
) -> None:
    """Remote -> remote on the same SSH host (no orchestrator hop)."""
    size = resolve_expected_size(
        expected_size, ssh=ssh, source_remote=src_remote
    )
    if destination_complete(ssh=ssh, remote_path=dest_remote, expected_size=size):
        logger.info("Skipping complete remote cp %s -> %s", src_remote, dest_remote)
        return
    parent = str(PurePosixPath(dest_remote).parent)
    ssh.execute(f'mkdir -p {shell_single_quote(parent)}', timeout=30)
    src_q = shell_single_quote(src_remote)
    dest_q = shell_single_quote(dest_remote)
    rc, _stdout, stderr = ssh.execute(
        f"cp -f {src_q} {dest_q}", timeout=ts.SCP_TIMEOUT_SEC
    )
    if rc != 0:
        raise RuntimeError(
            f"remote cp failed ({src_remote} -> {dest_remote}): {(stderr or '')[:200]}"
        )


def log_batch_progress(label: str, index: int, total: int, name: str) -> None:
    """Periodic logging for large multi-file transfers."""
    if total <= 1:
        return
    if index == 0 or (index + 1) % ts.BATCH_LOG_EVERY == 0 or index + 1 == total:
        logger.info(
            "%s file %d/%d (%d%%): %s",
            label,
            index + 1,
            total,
            int(((index + 1) / total) * 100),
            name,
        )
