"""
Audit Logging System

Records security-relevant events for compliance and debugging.
Writes structured JSON log entries to a dedicated audit log file.

Events tracked:
- Job submission, completion, failure, cancellation
- Backend switches (local <-> SLURM)
- SSH connections and disconnections
- File uploads and downloads
- Configuration changes
- Authentication events

Usage:
    from backend.core.audit import audit_log

    audit_log.record("job_submitted", job_id="abc", plugin_id="fastsurfer")
    audit_log.record("ssh_connected", host="hpc.university.edu", username="user01")
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Structured audit logger writing JSON lines to a file.

    Thread-safe. Each entry includes timestamp, event type, and metadata.
    """

    def __init__(self, log_dir: str = "./data/audit", max_file_size_mb: int = 50):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self._lock = threading.Lock()
        self._current_file: Optional[str] = None
        self._rotate_if_needed()

    def _get_log_path(self) -> Path:
        """Get current audit log file path."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"audit-{today}.jsonl"

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds max size."""
        path = self._get_log_path()
        if path.exists() and path.stat().st_size > self.max_file_size:
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            rotated = path.with_name(f"{path.stem}-{ts}{path.suffix}")
            path.rename(rotated)

    def record(
        self,
        event: str,
        severity: str = "info",
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        **details: Any,
    ) -> None:
        """Record an audit event.

        Args:
            event: Event type (e.g., "job_submitted", "ssh_connected")
            severity: Log severity: info, warning, error, critical
            user: Username associated with the event
            ip_address: Client IP address
            **details: Additional event-specific metadata
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "severity": severity,
            "user": user,
            "ip_address": ip_address,
            "details": details,
        }

        # Remove None values for cleaner logs
        entry = {k: v for k, v in entry.items() if v is not None}

        with self._lock:
            try:
                self._rotate_if_needed()
                path = self._get_log_path()
                with open(path, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

    def get_recent(self, limit: int = 100, event_filter: Optional[str] = None) -> list:
        """Read recent audit entries.

        Args:
            limit: Max entries to return
            event_filter: Optional event type filter

        Returns:
            List of audit entry dicts, newest first
        """
        entries = []
        try:
            # Read today's log and yesterday's if needed
            for days_back in range(2):
                dt = datetime.now(timezone.utc)
                if days_back > 0:
                    from datetime import timedelta
                    dt = dt - timedelta(days=days_back)
                path = self.log_dir / f"audit-{dt.strftime('%Y-%m-%d')}.jsonl"
                if path.exists():
                    with open(path, "r") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                entry = json.loads(line)
                                if event_filter and entry.get("event") != event_filter:
                                    continue
                                entries.append(entry)
                            except json.JSONDecodeError:
                                continue

                if len(entries) >= limit:
                    break

        except Exception as e:
            logger.error(f"Failed to read audit log: {e}")

        # Return newest first, limited
        entries.reverse()
        return entries[:limit]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_log: Optional[AuditLogger] = None
_audit_lock = threading.Lock()


def get_audit_logger(log_dir: str = "./data/audit") -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_log
    with _audit_lock:
        if _audit_log is None:
            _audit_log = AuditLogger(log_dir=log_dir)
        return _audit_log


# Convenience alias
audit_log = get_audit_logger()
