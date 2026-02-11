"""
SSH Connection Manager

Thread-safe SSH connection pool using paramiko for HPC communication.
Supports SSH agent authentication, key-based auth, and keepalive.

Usage:
    from backend.core.ssh_manager import get_ssh_manager

    mgr = get_ssh_manager()
    mgr.configure(host="hpc.university.edu", username="user01")
    mgr.connect()

    # Execute remote commands
    exit_code, stdout, stderr = mgr.execute("squeue -u $USER")

    # SFTP file operations
    mgr.put_file("/local/script.sh", "/scratch/user01/script.sh")
    content = mgr.read_file("/scratch/user01/output.log")

    mgr.disconnect()
"""
import io
import logging
import os
import stat
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple

import paramiko

logger = logging.getLogger(__name__)

# Connection timeout defaults
DEFAULT_CONNECT_TIMEOUT = 15  # seconds
DEFAULT_COMMAND_TIMEOUT = 120  # seconds
DEFAULT_KEEPALIVE_INTERVAL = 30  # seconds
DEFAULT_IDLE_TIMEOUT = 1800  # 30 minutes -- auto-disconnect after idle


class SSHConnectionError(Exception):
    """Raised when SSH connection fails."""


class SSHCommandError(Exception):
    """Raised when a remote command fails."""

    def __init__(self, message: str, exit_code: int = -1, stderr: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.stderr = stderr


class SSHManager:
    """Thread-safe SSH connection manager with connection reuse and SFTP.

    Features:
    - SSH agent authentication (preferred)
    - Key file authentication (fallback)
    - Connection pooling with automatic reconnect
    - Keepalive to prevent idle disconnects
    - Thread-safe command execution
    - SFTP file upload/download/read/write/list
    """

    def __init__(self):
        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._lock = threading.RLock()

        # Connection configuration
        self.host: Optional[str] = None
        self.username: Optional[str] = None
        self.port: int = 22
        self.key_path: Optional[str] = None
        self.connect_timeout: int = DEFAULT_CONNECT_TIMEOUT
        self.command_timeout: int = DEFAULT_COMMAND_TIMEOUT
        self.keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL

        # Session timeout
        self.idle_timeout: int = DEFAULT_IDLE_TIMEOUT
        self._idle_timer: Optional[threading.Timer] = None

        # Connection state
        self._connected = False
        self._last_activity: float = 0
        self._connect_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(
        self,
        host: str,
        username: str,
        port: int = 22,
        key_path: Optional[str] = None,
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
        command_timeout: int = DEFAULT_COMMAND_TIMEOUT,
        keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL,
        idle_timeout: int = DEFAULT_IDLE_TIMEOUT,
    ) -> None:
        """Set SSH connection parameters.

        Args:
            host: HPC hostname or IP
            username: SSH username
            port: SSH port (default 22)
            key_path: Path to SSH private key (None = use agent)
            connect_timeout: Connection timeout in seconds
            command_timeout: Default command execution timeout
            keepalive_interval: Seconds between keepalive packets
            idle_timeout: Auto-disconnect after this many idle seconds (0 = disabled)
        """
        with self._lock:
            # If connected to a different host, disconnect first
            if self._connected and (self.host != host or self.username != username or self.port != port):
                self.disconnect()

            self.host = host
            self.username = username
            self.port = port
            self.key_path = key_path
            self.connect_timeout = connect_timeout
            self.command_timeout = command_timeout
            self.keepalive_interval = keepalive_interval
            self.idle_timeout = idle_timeout

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish SSH connection using agent or key file auth.

        Authentication priority:
        1. SSH agent (if running and has keys)
        2. Specified key file
        3. Default key locations (~/.ssh/id_rsa, id_ed25519)

        Raises:
            SSHConnectionError: If connection cannot be established
        """
        with self._lock:
            if self._connected and self._is_alive():
                logger.debug("SSH already connected, reusing")
                return

            if not self.host or not self.username:
                raise SSHConnectionError(
                    "SSH not configured. Call configure(host, username) first."
                )

            # Close any stale connection
            self._close_internal()

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            try:
                # Build connection kwargs
                connect_kwargs = {
                    "hostname": self.host,
                    "port": self.port,
                    "username": self.username,
                    "timeout": self.connect_timeout,
                    "allow_agent": True,
                    "look_for_keys": True,
                }

                # Use specific key file if provided
                if self.key_path:
                    key_path = os.path.expanduser(self.key_path)
                    if os.path.isfile(key_path):
                        connect_kwargs["key_filename"] = key_path
                        connect_kwargs["allow_agent"] = False
                        connect_kwargs["look_for_keys"] = False

                logger.info(f"Connecting to {self.username}@{self.host}:{self.port}")
                client.connect(**connect_kwargs)

                # Set keepalive
                transport = client.get_transport()
                if transport:
                    transport.set_keepalive(self.keepalive_interval)

                self._client = client
                self._connected = True
                self._connect_time = time.time()
                self._last_activity = time.time()
                self._reset_idle_timer()

                logger.info(f"SSH connected to {self.username}@{self.host}")

            except paramiko.AuthenticationException as e:
                raise SSHConnectionError(
                    f"Authentication failed for {self.username}@{self.host}. "
                    f"Ensure your SSH key is loaded (ssh-add) or specify key_path. "
                    f"Error: {e}"
                )
            except paramiko.SSHException as e:
                raise SSHConnectionError(
                    f"SSH protocol error connecting to {self.host}: {e}"
                )
            except Exception as e:
                raise SSHConnectionError(
                    f"Cannot connect to {self.host}:{self.port}: {e}"
                )

    def _reset_idle_timer(self) -> None:
        """Reset the idle-disconnect timer. Called on every activity."""
        if self._idle_timer:
            self._idle_timer.cancel()
            self._idle_timer = None
        if self.idle_timeout > 0 and self._connected:
            self._idle_timer = threading.Timer(self.idle_timeout, self._idle_disconnect)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _idle_disconnect(self) -> None:
        """Called by timer when session has been idle too long."""
        idle_seconds = int(time.time() - self._last_activity) if self._last_activity else 0
        logger.info(
            f"SSH session idle for {idle_seconds}s (timeout={self.idle_timeout}s), auto-disconnecting"
        )
        try:
            from backend.core.audit import audit_log
            audit_log.record("ssh_idle_timeout", host=self.host, idle_seconds=idle_seconds)
        except Exception:
            pass
        self.disconnect()

    def disconnect(self) -> None:
        """Close SSH connection and SFTP channel."""
        with self._lock:
            if self._idle_timer:
                self._idle_timer.cancel()
                self._idle_timer = None
            self._close_internal()
            logger.info("SSH disconnected")

    def _close_internal(self) -> None:
        """Internal close without lock (caller must hold lock)."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        self._connected = False
        self._connect_time = None

    def _is_alive(self) -> bool:
        """Check if the SSH transport is still active."""
        if not self._client:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    def _ensure_connected(self) -> None:
        """Ensure we have a live connection, reconnecting if needed."""
        if not self._connected or not self._is_alive():
            if not self.host or not self.username:
                raise SSHConnectionError("SSH not configured")
            logger.info("SSH connection lost, reconnecting...")
            self.connect()

    @property
    def is_connected(self) -> bool:
        """Check if SSH is currently connected."""
        with self._lock:
            return self._connected and self._is_alive()

    @property
    def connection_info(self) -> dict:
        """Get current connection info."""
        with self._lock:
            connected = self._connected and self._is_alive()
            idle_seconds = int(time.time() - self._last_activity) if self._last_activity else None
            return {
                "connected": connected,
                "host": self.host,
                "username": self.username,
                "port": self.port,
                "uptime_seconds": int(time.time() - self._connect_time) if self._connect_time and connected else 0,
                "last_activity_seconds_ago": idle_seconds,
                "idle_timeout_seconds": self.idle_timeout,
                "idle_timeout_remaining": max(0, self.idle_timeout - idle_seconds) if connected and idle_seconds is not None else None,
            }

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        check: bool = False,
    ) -> Tuple[int, str, str]:
        """Execute a command on the remote host.

        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds (None = use default)
            check: If True, raise SSHCommandError on non-zero exit

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            SSHConnectionError: If not connected
            SSHCommandError: If check=True and command returns non-zero
        """
        if timeout is None:
            timeout = self.command_timeout

        with self._lock:
            self._ensure_connected()
            self._last_activity = time.time()
            self._reset_idle_timer()

            try:
                stdin, stdout_ch, stderr_ch = self._client.exec_command(
                    command, timeout=timeout
                )

                stdout_text = stdout_ch.read().decode("utf-8", errors="replace")
                stderr_text = stderr_ch.read().decode("utf-8", errors="replace")
                exit_code = stdout_ch.channel.recv_exit_status()

                logger.debug(
                    f"SSH exec: '{command[:80]}...' -> exit={exit_code}"
                )

                if check and exit_code != 0:
                    raise SSHCommandError(
                        f"Command failed (exit {exit_code}): {command}\n"
                        f"stderr: {stderr_text[:500]}",
                        exit_code=exit_code,
                        stderr=stderr_text,
                    )

                return exit_code, stdout_text, stderr_text

            except SSHCommandError:
                raise
            except Exception as e:
                raise SSHConnectionError(f"Command execution failed: {e}")

    def execute_check(self, command: str, timeout: Optional[int] = None) -> str:
        """Execute command and return stdout, raising on non-zero exit.

        Convenience wrapper around execute(check=True).
        """
        _, stdout, _ = self.execute(command, timeout=timeout, check=True)
        return stdout

    # ------------------------------------------------------------------
    # SFTP operations
    # ------------------------------------------------------------------

    def _get_sftp(self) -> paramiko.SFTPClient:
        """Get or create SFTP channel."""
        self._ensure_connected()
        if self._sftp is None:
            self._sftp = self._client.open_sftp()
        self._reset_idle_timer()
        return self._sftp

    def put_file(self, local_path: str, remote_path: str) -> None:
        """Upload a local file to the remote host.

        Args:
            local_path: Path to local file
            remote_path: Destination path on remote
        """
        with self._lock:
            sftp = self._get_sftp()
            self._last_activity = time.time()

            # Ensure remote directory exists
            remote_dir = str(PurePosixPath(remote_path).parent)
            self._mkdir_p(sftp, remote_dir)

            sftp.put(local_path, remote_path)
            logger.debug(f"SFTP put: {local_path} -> {remote_path}")

    def get_file(self, remote_path: str, local_path: str) -> None:
        """Download a file from the remote host.

        Args:
            remote_path: Path on remote host
            local_path: Destination path on local
        """
        with self._lock:
            sftp = self._get_sftp()
            self._last_activity = time.time()

            # Ensure local directory exists
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)

            sftp.get(remote_path, local_path)
            logger.debug(f"SFTP get: {remote_path} -> {local_path}")

    def write_file(self, remote_path: str, content: str, mode: int = 0o644) -> None:
        """Write string content to a remote file.

        Args:
            remote_path: Destination path on remote
            content: Text content to write
            mode: File permission mode
        """
        with self._lock:
            sftp = self._get_sftp()
            self._last_activity = time.time()

            remote_dir = str(PurePosixPath(remote_path).parent)
            self._mkdir_p(sftp, remote_dir)

            with sftp.open(remote_path, "w") as f:
                f.write(content)
            sftp.chmod(remote_path, mode)
            logger.debug(f"SFTP write: {remote_path} ({len(content)} bytes)")

    def read_file(self, remote_path: str) -> str:
        """Read content of a remote file.

        Args:
            remote_path: Path on remote host

        Returns:
            File contents as string
        """
        with self._lock:
            sftp = self._get_sftp()
            self._last_activity = time.time()

            with sftp.open(remote_path, "r") as f:
                data = f.read()
                if isinstance(data, bytes):
                    return data.decode("utf-8", errors="replace")
                return str(data)

    def list_dir(self, remote_path: str) -> List[Dict]:
        """List directory contents on remote host.

        Args:
            remote_path: Directory path on remote

        Returns:
            List of dicts with name, path, type, size, modified
        """
        with self._lock:
            sftp = self._get_sftp()
            self._last_activity = time.time()

            entries = []
            for attr in sftp.listdir_attr(remote_path):
                is_dir = stat.S_ISDIR(attr.st_mode) if attr.st_mode else False
                entry = {
                    "name": attr.filename,
                    "path": str(PurePosixPath(remote_path) / attr.filename),
                    "type": "directory" if is_dir else "file",
                    "size": attr.st_size or 0,
                    "modified": attr.st_mtime,
                }
                entries.append(entry)

            # Sort: directories first, then by name
            entries.sort(key=lambda e: (0 if e["type"] == "directory" else 1, e["name"].lower()))
            return entries

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file or directory exists on the remote host."""
        with self._lock:
            sftp = self._get_sftp()
            try:
                sftp.stat(remote_path)
                return True
            except FileNotFoundError:
                return False

    def remove_file(self, remote_path: str) -> None:
        """Remove a file on the remote host."""
        with self._lock:
            sftp = self._get_sftp()
            sftp.remove(remote_path)

    @staticmethod
    def _mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        """Recursively create remote directory (like mkdir -p)."""
        if remote_dir in ("", "/", "."):
            return
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parent = str(PurePosixPath(remote_dir).parent)
            SSHManager._mkdir_p(sftp, parent)
            try:
                sftp.mkdir(remote_dir)
            except IOError:
                pass  # May already exist from race condition

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Check SSH connection health.

        Returns:
            Dict with healthy status and details
        """
        if not self.host or not self.username:
            return {
                "healthy": False,
                "message": "SSH not configured",
                "details": {"configured": False},
            }

        if not self.is_connected:
            return {
                "healthy": False,
                "message": f"Not connected to {self.host}",
                "details": {
                    "configured": True,
                    "host": self.host,
                    "username": self.username,
                },
            }

        try:
            exit_code, stdout, _ = self.execute("echo OK && hostname", timeout=10)
            hostname = stdout.strip().split("\n")[-1] if exit_code == 0 else "unknown"
            return {
                "healthy": exit_code == 0,
                "message": f"Connected to {hostname}" if exit_code == 0 else "Connection test failed",
                "details": {
                    **self.connection_info,
                    "remote_hostname": hostname,
                },
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Connection test failed: {e}",
                "details": self.connection_info,
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ssh_manager: Optional[SSHManager] = None
_ssh_lock = threading.Lock()


def get_ssh_manager() -> SSHManager:
    """Get global SSH manager instance (singleton)."""
    global _ssh_manager
    with _ssh_lock:
        if _ssh_manager is None:
            _ssh_manager = SSHManager()
        return _ssh_manager
