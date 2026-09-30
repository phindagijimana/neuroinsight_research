"""Registry of named SSH connections that can be live at the same time.

The app has always had a single "active" SSH connection (``get_ssh_manager``)
used by Jobs, monitoring, and the legacy transfer paths. That stays exactly as
it is. This registry adds *extra* named connections alongside it so the Transfer
page can hold, say, two different HPC clusters open at once and copy directly
between them.

The active connection is exposed here under the id ``"active"`` so the Transfer
UI can list it together with the extras; the extras are independent
``SSHManager`` instances keyed by a generated id.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.core.ssh_manager import get_ssh_manager, new_ssh_manager

ACTIVE_ID = "active"
# Legacy transfer type strings that map to the single active connection.
LEGACY_IDS = {ACTIVE_ID, "hpc", "remote", "", None}


@dataclass
class ConnEntry:
    id: str
    name: str
    kind: str  # "hpc" | "remote"
    manager: object  # SSHManager or BrokerSSHManager
    work_dir: Optional[str] = None

    def to_dict(self) -> dict:
        info = {}
        try:
            info = self.manager.connection_info()
        except Exception:
            info = {}
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "host": info.get("host"),
            "username": info.get("username"),
            "port": info.get("port"),
            "connected": bool(info.get("connected")),
            "work_dir": self.work_dir,
            "is_active": self.id == ACTIVE_ID,
        }


class ConnectionRegistry:
    """Holds extra live SSH connections beside the single active one."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._extra: Dict[str, ConnEntry] = {}

    # -- active (singleton) -------------------------------------------------
    def _active_entry(self) -> Optional[ConnEntry]:
        mgr = get_ssh_manager()
        try:
            info = mgr.connection_info()
        except Exception:
            return None
        if not info.get("connected"):
            return None
        return ConnEntry(
            id=ACTIVE_ID,
            name=info.get("host") or "Active connection",
            kind="hpc",
            manager=mgr,
            work_dir=None,
        )

    # -- CRUD ---------------------------------------------------------------
    def add(
        self,
        name: str,
        host: str,
        username: str,
        port: int = 22,
        key_path: Optional[str] = None,
        password: Optional[str] = None,
        kind: str = "hpc",
        work_dir: Optional[str] = None,
    ) -> ConnEntry:
        """Create, connect, and register a new SSH connection."""
        mgr = new_ssh_manager()
        mgr.configure(host=host, username=username, port=port, key_path=key_path, password=password)
        mgr.connect()  # raises on failure; caller surfaces the error
        cid = "c_" + uuid.uuid4().hex[:10]
        entry = ConnEntry(id=cid, name=(name or host), kind=kind, manager=mgr, work_dir=work_dir)
        with self._lock:
            self._extra[cid] = entry
        return entry

    def remove(self, cid: str) -> bool:
        """Disconnect and drop an extra connection (the active one is untouched)."""
        if cid in LEGACY_IDS:
            return False
        with self._lock:
            entry = self._extra.pop(cid, None)
        if not entry:
            return False
        try:
            entry.manager.disconnect()
        except Exception:
            pass
        return True

    def get(self, cid: str) -> Optional[ConnEntry]:
        if cid in LEGACY_IDS:
            return self._active_entry()
        with self._lock:
            return self._extra.get(cid)

    def manager_for(self, cid: str):
        """Resolve a connection id to its SSHManager (active for legacy ids)."""
        entry = self.get(cid)
        return entry.manager if entry else None

    def list(self) -> List[ConnEntry]:
        out: List[ConnEntry] = []
        active = self._active_entry()
        if active:
            out.append(active)
        with self._lock:
            out.extend(self._extra.values())
        return out


_registry: Optional[ConnectionRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> ConnectionRegistry:
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = ConnectionRegistry()
        return _registry
