"""Tests for the multi-host connection registry.

Uses fake SSH managers so no real network/SSH is needed. Covers the active
(singleton) connection appearing in the list, adding/removing extras, and
legacy-id resolution to the active connection.
"""

import backend.core.connection_registry as reg
from backend.core.connection_registry import ConnectionRegistry, ACTIVE_ID


class FakeManager:
    def __init__(self, host="host", user="u", connected=True):
        self._host, self._user, self._connected = host, user, connected
        self.configured = None
        self.connected_called = False
        self.disconnected = False

    def configure(self, **kw):
        self.configured = kw

    def connect(self):
        self.connected_called = True
        self._connected = True

    def disconnect(self):
        self.disconnected = True
        self._connected = False

    def connection_info(self):
        return {
            "connected": self._connected,
            "host": self._host,
            "username": self._user,
            "port": 22,
        }


def test_no_active_connection_lists_empty(monkeypatch):
    monkeypatch.setattr(reg, "get_ssh_manager", lambda: FakeManager(connected=False))
    r = ConnectionRegistry()
    assert r.list() == []
    # legacy ids resolve to the (absent) active -> None
    assert r.manager_for("hpc") is None


def test_active_connection_appears(monkeypatch):
    active = FakeManager(host="bluehive3.circ.rochester.edu")
    monkeypatch.setattr(reg, "get_ssh_manager", lambda: active)
    r = ConnectionRegistry()
    listed = r.list()
    assert len(listed) == 1
    d = listed[0].to_dict()
    assert d["id"] == ACTIVE_ID and d["is_active"] is True
    assert d["host"] == "bluehive3.circ.rochester.edu"
    # legacy strings all resolve to the active manager
    for legacy in ("active", "hpc", "remote", ""):
        assert r.manager_for(legacy) is active


def test_add_and_remove_extra(monkeypatch):
    active = FakeManager(host="bluehive3")
    extra = FakeManager(host="ondemand")
    monkeypatch.setattr(reg, "get_ssh_manager", lambda: active)
    monkeypatch.setattr(reg, "new_ssh_manager", lambda: extra)
    r = ConnectionRegistry()

    entry = r.add(name="OOD", host="ondemand.circ.rochester.edu", username="pndagiji", port=22)
    assert extra.connected_called and extra.configured["host"] == "ondemand.circ.rochester.edu"
    assert entry.id.startswith("c_")

    ids = {e.id for e in r.list()}
    assert ACTIVE_ID in ids and entry.id in ids  # both live at once
    assert r.manager_for(entry.id) is extra

    assert r.remove(entry.id) is True
    assert extra.disconnected is True
    assert entry.id not in {e.id for e in r.list()}


def test_remove_active_or_unknown_refused(monkeypatch):
    monkeypatch.setattr(reg, "get_ssh_manager", lambda: FakeManager())
    r = ConnectionRegistry()
    assert r.remove("active") is False
    assert r.remove("hpc") is False
    assert r.remove("c_doesnotexist") is False
