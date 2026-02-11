"""
Tests for the audit logging system.
"""
import json
import tempfile
import pytest
from pathlib import Path


class TestAuditLog:
    """Test structured audit logging."""

    def test_record_and_retrieve(self, tmp_dir):
        """Audit events are recorded and can be retrieved."""
        from backend.core.audit import AuditLogger
        log = AuditLogger(log_dir=str(tmp_dir))
        log.record("test_event", user="testuser", detail="something happened")

        recent = log.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0]["event"] == "test_event"
        assert recent[0]["user"] == "testuser"
        assert "timestamp" in recent[0]

    def test_multiple_events(self, tmp_dir):
        """Multiple events are stored in order."""
        from backend.core.audit import AuditLogger
        log = AuditLogger(log_dir=str(tmp_dir))

        for i in range(5):
            log.record(f"event_{i}", index=i)

        recent = log.get_recent(limit=10)
        assert len(recent) == 5

    def test_limit_parameter(self, tmp_dir):
        """get_recent respects the limit parameter."""
        from backend.core.audit import AuditLogger
        log = AuditLogger(log_dir=str(tmp_dir))

        for i in range(20):
            log.record("bulk_event", index=i)

        recent = log.get_recent(limit=5)
        assert len(recent) == 5

    def test_event_filter(self, tmp_dir):
        """get_recent can filter by event type."""
        from backend.core.audit import AuditLogger
        log = AuditLogger(log_dir=str(tmp_dir))

        log.record("ssh_connect", host="hpc1")
        log.record("job_submit", job_id="123")
        log.record("ssh_connect", host="hpc2")

        recent = log.get_recent(limit=10, event_filter="ssh_connect")
        assert len(recent) == 2
        assert all(e["event"] == "ssh_connect" for e in recent)

    def test_json_serializable(self, tmp_dir):
        """Audit entries are valid JSON."""
        from backend.core.audit import AuditLogger
        log = AuditLogger(log_dir=str(tmp_dir))
        log.record("test_json", data={"nested": [1, 2, 3]})

        recent = log.get_recent(limit=1)
        # Should not raise
        json.dumps(recent[0])
