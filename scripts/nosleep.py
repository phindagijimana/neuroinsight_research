#!/usr/bin/env python3
"""
NeuroInsight no-sleep helper using systemd-inhibit.
Keeps the machine awake while jobs run.
"""

import os
import signal
import shutil
import subprocess
import sys
from pathlib import Path

PID_FILE = Path("nosleep.pid")


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start() -> None:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if _is_running(pid):
                print(f"No-sleep already running (PID: {pid})")
                return
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)

    if not shutil.which("systemd-inhibit"):
        print("systemd-inhibit not available; cannot enable no-sleep mode.")
        sys.exit(1)

    cmd = [
        "systemd-inhibit",
        "--what=sleep",
        "--why=NeuroInsight processing",
        "--mode=block",
        "bash",
        "-c",
        "while true; do sleep 60; done",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PID_FILE.write_text(str(proc.pid))
    print(f"No-sleep enabled (PID: {proc.pid})")


def stop() -> None:
    if not PID_FILE.exists():
        print("No-sleep not running.")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        print("No-sleep pid file invalid; cleaned up.")
        return

    if _is_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as exc:
            print(f"Failed to stop no-sleep (PID: {pid}): {exc}")
    PID_FILE.unlink(missing_ok=True)
    print("No-sleep disabled.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: nosleep.py {start|stop}")
        sys.exit(1)

    action = sys.argv[1].lower()
    if action == "start":
        start()
    elif action == "stop":
        stop()
    else:
        print("Usage: nosleep.py {start|stop}")
        sys.exit(1)

