#!/usr/bin/env python3
"""
Stop dev-only NeuroInsight services (port 8001).
"""

import os
import signal
from pathlib import Path

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
NC = '\033[0m'


def log_info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")


def log_success(msg):
    print(f"{GREEN}[SUCCESS]{NC} {msg}")


def log_error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")


def kill_pid(pid: int, label: str):
    try:
        os.kill(pid, signal.SIGTERM)
        log_success(f"Stopped {label} (PID: {pid})")
    except ProcessLookupError:
        log_info(f"{label} already stopped (PID: {pid})")
    except Exception as exc:
        log_error(f"Failed to stop {label} (PID: {pid}): {exc}")


def kill_from_pidfile(pidfile: str, label: str):
    path = Path(pidfile)
    if not path.exists():
        return
    try:
        pid = int(path.read_text().strip())
        kill_pid(pid, label)
        path.unlink(missing_ok=True)
    except Exception as exc:
        log_error(f"Failed to read {pidfile}: {exc}")


def kill_dev_processes_by_env():
    """Best-effort cleanup for dev processes without pidfiles."""
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.is_dir() or not proc_dir.name.isdigit():
            continue
        pid = int(proc_dir.name)
        try:
            cmdline = (proc_dir / "cmdline").read_bytes().replace(b"\x00", b" ").decode()
            if "backend/main.py" not in cmdline and "celery" not in cmdline and "job_monitor" not in cmdline:
                continue
            environ = (proc_dir / "environ").read_bytes().replace(b"\x00", b"\n").decode()
            if "PORT=8001" in environ or "API_PORT=8001" in environ or "neuroinsight_dev" in environ:
                kill_pid(pid, "dev process")
        except Exception:
            continue


def main():
    log_info("Stopping dev services on port 8001...")
    kill_from_pidfile("neuroinsight-dev.pid", "dev backend")
    kill_from_pidfile("celery-dev.pid", "dev celery")
    kill_from_pidfile("job_monitor-dev.pid", "dev job monitor")
    kill_dev_processes_by_env()
    log_success("Dev services stopped")


if __name__ == "__main__":
    main()
