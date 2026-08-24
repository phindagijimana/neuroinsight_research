"""
Environment-driven settings for large data transfers (multi-GB / 300GB+).

Transfers run file-by-file (each file is one batch unit). Timeouts are per
file operation, not for the whole folder. Re-run or retry skips files that
already match the expected size on the destination.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


# Per-file curl on HPC/remote (Pennsieve -> cluster direct path). Default 24h.
CURL_TIMEOUT_SEC = _int_env("NIR_TRANSFER_CURL_TIMEOUT_SEC", 86400, minimum=60)

# Per-file scp/sftp via SSH broker or paramiko. Default 24h.
SCP_TIMEOUT_SEC = _int_env("NIR_TRANSFER_SCP_TIMEOUT_SEC", 86400, minimum=60)

# Retries per file for direct curl (fresh presigned URL each attempt; curl -C - resumes).
CURL_MAX_RETRIES = _int_env("NIR_TRANSFER_CURL_RETRIES", 3, minimum=1)

# Skip destination files that already match expected byte size (re-run / continue).
SKIP_COMPLETE_FILES = _bool_env("NIR_TRANSFER_SKIP_COMPLETE", True)

# Stream chunk size for platform -> local downloads.
DOWNLOAD_CHUNK_BYTES = _int_env("NIR_TRANSFER_CHUNK_BYTES", 1024 * 1024, minimum=65536)

# Log progress every N files in large folder transfers.
BATCH_LOG_EVERY = _int_env("NIR_TRANSFER_BATCH_LOG_EVERY", 25, minimum=1)
