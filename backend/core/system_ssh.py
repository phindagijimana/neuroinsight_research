"""SystemSSHSession — drive the OS `ssh` client with ControlMaster multiplexing.

Phase 1 (this file): non-interactive (key/agent) connect + exec + listdir, with a
persistent multiplexed master so repeated operations don't re-auth. Honors
~/.ssh/config (aliases, ProxyJump, IdentityFile) when connecting by alias.

The control socket lives inside the engine (container), so there's no cross-VM
socket-sharing problem. Phase 2 will add a PTY + WebSocket relay on top of this
to support interactive MFA (password + Duo); the exec/listdir paths here stay the
same (they just attach to the already-authenticated master).
"""
import hashlib
import os
import shlex
import subprocess
import tempfile
import threading
from typing import List, Dict, Optional, Tuple


class SystemSSHError(Exception):
    pass


def _control_dir() -> str:
    for d in ("/run/nir/ssh", os.path.join(tempfile.gettempdir(), "nir-ssh")):
        try:
            os.makedirs(d, mode=0o700, exist_ok=True)
            return d
        except Exception:
            continue
    return tempfile.gettempdir()


class SystemSSHSession:
    """One persistent, multiplexed SSH master to a single target."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.target: Optional[str] = None      # "user@host" or a config alias
        self.sock: Optional[str] = None

    def _ssh_base(self) -> List[str]:
        return [
            "ssh",
            "-o", "BatchMode=yes",                       # Phase 1: no prompts (key/agent)
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"ControlPath={self.sock}",
        ]

    def open(
        self,
        *,
        host: Optional[str] = None,
        username: Optional[str] = None,
        port: int = 22,
        key_path: Optional[str] = None,
        alias: Optional[str] = None,
        persist: str = "8h",
        timeout: int = 30,
    ) -> str:
        """Open the multiplexed master. Returns the remote hostname."""
        with self._lock:
            if alias:
                target = alias                      # let ssh resolve ~/.ssh/config
            elif username:
                target = f"{username}@{host}"
            else:
                target = host or ""
            if not target:
                raise SystemSSHError("No host/alias provided")

            digest = hashlib.sha1(f"{target}:{port}".encode()).hexdigest()[:16]
            self.sock = os.path.join(_control_dir(), f"cm-{digest}")

            cmd = [
                "ssh",
                "-o", "ControlMaster=yes",
                "-o", f"ControlPersist={persist}",
                "-o", "ServerAliveInterval=30",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", f"ControlPath={self.sock}",
                "-o", f"ConnectTimeout={timeout}",
            ]
            if not alias:                            # explicit target: set port/key
                cmd += ["-p", str(port)]
                if key_path:
                    cmd += ["-i", os.path.expanduser(key_path), "-o", "IdentitiesOnly=yes"]
            cmd += [target, "echo NIR_MASTER_READY && hostname"]

            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
            except subprocess.TimeoutExpired:
                raise SystemSSHError("Connection timed out opening the SSH master")

            if "NIR_MASTER_READY" not in (p.stdout or ""):
                raise SystemSSHError((p.stderr or p.stdout or "ssh master failed").strip())

            self.target = target
            lines = [ln for ln in p.stdout.splitlines() if ln and ln != "NIR_MASTER_READY"]
            return lines[-1].strip() if lines else (host or alias or "")

    def exec(self, command: str, timeout: int = 120) -> Tuple[int, str, str]:
        if not self.target:
            raise SystemSSHError("Not connected")
        p = subprocess.run(self._ssh_base() + [self.target, command],
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def listdir(self, path: str) -> List[Dict]:
        """List a remote directory over the multiplexed connection."""
        rc, out, err = self.exec(f"ls -1Ap -- {shlex.quote(path)}")
        if rc != 0:
            raise SystemSSHError((err or out or f"cannot list {path}").strip())
        entries: List[Dict] = []
        for name in out.splitlines():
            if not name:
                continue
            is_dir = name.endswith("/")
            entries.append({"name": name.rstrip("/"), "type": "directory" if is_dir else "file"})
        return entries

    def is_alive(self) -> bool:
        if not (self.sock and self.target):
            return False
        p = subprocess.run(["ssh", "-O", "check", "-o", f"ControlPath={self.sock}", self.target],
                           capture_output=True, text=True)
        return p.returncode == 0

    def close(self) -> None:
        if self.sock and self.target:
            subprocess.run(["ssh", "-O", "exit", "-o", f"ControlPath={self.sock}", self.target],
                           capture_output=True, text=True)
        self.target = None
        self.sock = None
