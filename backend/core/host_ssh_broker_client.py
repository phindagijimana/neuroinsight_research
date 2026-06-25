"""
Broker-backed SSH manager (engine side).

A drop-in replacement for :class:`SSHManager` that performs no SSH itself.
Instead it proxies every operation to the host-side SSH broker
(`desktop/app/src/sshBroker.js`) over a token-protected HTTP call. The broker
runs the OS ``ssh`` client with ControlMaster on the host, so the connection
inherits the host's working auth (agent key, ``~/.ssh/config``, Kerberos,
ProxyJump) — which the container cannot do itself.

Activated transparently by :func:`backend.core.ssh_manager.get_ssh_manager`
when ``NIR_SSH_BROKER_URL`` is set. Same public surface as ``SSHManager`` so the
SLURM / remote-docker backends and HPC routes use it unchanged.

File transfers rely on ``/data`` being bind-mounted from the host (the broker
translates container ``/data/...`` paths to the host path for scp). Small writes
go through a shared ``/data`` temp file.
"""
import json
import logging
import os
import stat as _stat
import threading
import time
import uuid
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

from backend.core.ssh_manager import SSHConnectionError, SSHCommandError

logger = logging.getLogger(__name__)

# Where the container sees the shared host-mounted data dir.
_DATA_DIR = os.getenv("NIR_CONTAINER_DATA_DIR", "/data")


class BrokerSSHManager:
    """SSHManager-compatible facade that proxies to the host SSH broker."""

    def __init__(self, broker_url: Optional[str] = None, token: Optional[str] = None):
        self._url = (broker_url or os.getenv("NIR_SSH_BROKER_URL", "")).rstrip("/")
        self._token = token or os.getenv("NIR_SSH_BROKER_TOKEN", "")
        self._lock = threading.RLock()
        self.host: Optional[str] = None
        self.username: Optional[str] = None
        self.port: int = 22
        self._password: Optional[str] = None  # in-memory only, for Duo clusters
        self._connect_time: Optional[float] = None

    # ------------------------------------------------------------------
    # transport
    # ------------------------------------------------------------------
    def _call(self, op: str, body: dict, timeout: int = 130) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self._url}/{op}",
            data=data,
            headers={"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:  # noqa: BLE001 - surface as our connection error
            raise SSHConnectionError(f"SSH broker call '{op}' failed: {e}")

    def _target(self) -> dict:
        if not self.host or not self.username:
            raise SSHConnectionError("SSH not configured. Call configure(host, username) first.")
        return {"host": self.host, "user": self.username, "port": self.port}

    # ------------------------------------------------------------------
    # configuration / lifecycle
    # ------------------------------------------------------------------
    def configure(self, host: str, username: str, port: int = 22,
                  key_path: Optional[str] = None, password: Optional[str] = None,
                  **_ignored) -> None:
        # key_path is ignored (the host broker owns key/agent/Kerberos auth).
        # password, when given, is used for interactive (password + Duo) clusters
        # that reject keys; held in memory only.
        with self._lock:
            self.host = host
            self.username = username
            self.port = port
            self._password = password

    def connect(self) -> None:
        with self._lock:
            if self._password:
                # Duo approval can take ~a minute; allow time on the HTTP call.
                res = self._call(
                    "connect-interactive",
                    {**self._target(), "password": self._password},
                    timeout=130,
                )
            else:
                res = self._call("connect", self._target(), timeout=45)
            if not res.get("connected"):
                if res.get("needsInteractive"):
                    raise SSHConnectionError(
                        f"{self.host} requires interactive login (password + Duo). "
                        f"Provide your password to connect."
                    )
                raise SSHConnectionError(
                    f"Broker could not connect to {self.username}@{self.host}: {res.get('error', 'unknown')}"
                )
            self._connect_time = time.time()

    @property
    def is_connected(self) -> bool:
        try:
            if not self.host:
                return False
            return bool(self._call("check", self._target(), timeout=12).get("alive"))
        except Exception:
            return False

    def disconnect(self) -> None:
        with self._lock:
            try:
                if self.host:
                    self._call("disconnect", self._target(), timeout=12)
            finally:
                self._connect_time = None

    def _ensure_connected(self) -> None:
        if not self.is_connected:
            self.connect()

    # ------------------------------------------------------------------
    # command execution
    # ------------------------------------------------------------------
    def execute(self, command: str, timeout: Optional[int] = None,
                check: bool = False) -> Tuple[int, str, str]:
        timeout = timeout or 120
        res = self._call(
            "exec", {**self._target(), "command": command, "timeout": timeout},
            timeout=timeout + 15,
        )
        rc, out, err = int(res.get("rc", 255)), res.get("stdout", ""), res.get("stderr", "")
        if check and rc != 0:
            raise SSHCommandError(
                f"Command failed (exit {rc}): {command}\nstderr: {err[:500]}",
                exit_code=rc, stderr=err,
            )
        return rc, out, err

    def execute_check(self, command: str, timeout: Optional[int] = None) -> str:
        _, out, _ = self.execute(command, timeout=timeout, check=True)
        return out

    # ------------------------------------------------------------------
    # file operations
    # ------------------------------------------------------------------
    def put_file(self, local_path: str, remote_path: str) -> None:
        remote_dir = str(PurePosixPath(remote_path).parent)
        self.execute(f'mkdir -p "{remote_dir}"', timeout=30)
        res = self._call("put", {**self._target(), "localPath": local_path, "remotePath": remote_path},
                         timeout=1800)
        if not res.get("ok"):
            raise SSHConnectionError(f"put_file {local_path} -> {remote_path} failed: {res.get('error')}")

    def get_file(self, remote_path: str, local_path: str) -> None:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        res = self._call("get", {**self._target(), "remotePath": remote_path, "localPath": local_path},
                         timeout=1800)
        if not res.get("ok"):
            raise SSHConnectionError(f"get_file {remote_path} -> {local_path} failed: {res.get('error')}")

    def write_file(self, remote_path: str, content: str, mode: int = 0o644) -> None:
        # Stage through a shared /data temp file the broker can read, then scp.
        tmp_dir = Path(_DATA_DIR) / ".nir_broker_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"w-{uuid.uuid4().hex}"
        try:
            tmp.write_text(content)
            self.put_file(str(tmp), remote_path)
            self.execute(f'chmod {oct(mode)[2:]} "{remote_path}"', timeout=30)
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass

    def read_file(self, remote_path: str) -> str:
        rc, out, err = self.execute(f'cat -- "{remote_path}"', timeout=60)
        if rc != 0:
            raise SSHConnectionError(f"read_file {remote_path} failed: {err[:200]}")
        return out

    def file_exists(self, remote_path: str) -> bool:
        rc, out, _ = self.execute(f'test -e "{remote_path}" && echo 1 || echo 0', timeout=20)
        return out.strip() == "1"

    def list_dir(self, remote_path: str) -> List[Dict]:
        # GNU find on the cluster gives type/size/mtime/name in one shot.
        cmd = (
            f'find "{remote_path}" -maxdepth 1 -mindepth 1 '
            r"-printf '%y\t%s\t%T@\t%f\n'"
        )
        rc, out, err = self.execute(cmd, timeout=30)
        if rc != 0:
            raise SSHConnectionError(f"list_dir {remote_path} failed: {err[:200]}")
        entries = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            ftype, size, mtime, name = parts
            entries.append({
                "name": name,
                "path": str(PurePosixPath(remote_path) / name),
                "type": "directory" if ftype == "d" else "file",
                "size": int(size) if size.isdigit() else 0,
                "modified": float(mtime) if mtime.replace(".", "", 1).isdigit() else 0,
            })
        entries.sort(key=lambda e: (0 if e["type"] == "directory" else 1, e["name"].lower()))
        return entries

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    @property
    def connection_info(self) -> dict:
        connected = self.is_connected
        return {
            "connected": connected,
            "host": self.host,
            "username": self.username,
            "port": self.port,
            "uptime_seconds": int(time.time() - self._connect_time) if self._connect_time and connected else 0,
            "via": "host-ssh-broker",
        }

    def health_check(self) -> dict:
        if not self.host or not self.username:
            return {"healthy": False, "message": "SSH not configured", "details": {"configured": False}}
        try:
            rc, out, _ = self.execute("echo OK && hostname", timeout=15)
            hostname = out.strip().split("\n")[-1] if rc == 0 else "unknown"
            return {
                "healthy": rc == 0,
                "message": f"Connected to {hostname}" if rc == 0 else "Connection test failed",
                "details": {**self.connection_info, "remote_hostname": hostname},
            }
        except Exception as e:  # noqa: BLE001
            return {"healthy": False, "message": f"Connection test failed: {e}", "details": self.connection_info}
