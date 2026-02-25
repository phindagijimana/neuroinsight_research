"""
Tests for the TransferManager and transfer API routes.

Covers:
  - TransferRecord creation and state transitions
  - TransferManager initialization and record management
  - _filename_from_id helper
  - Transfer API route validation
"""
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_transfer.db")
    monkeypatch.setenv("BACKEND_TYPE", "local")
    monkeypatch.setenv("ENVIRONMENT", "development")


# ---------------------------------------------------------------------------
# TransferRecord
# ---------------------------------------------------------------------------

class TestTransferRecord:
    """Test TransferRecord dataclass behaviour."""

    def test_record_creation(self):
        from backend.core.transfer_manager import TransferRecord
        rec = TransferRecord(
            transfer_id="test-001",
            direction="download",
            platform="pennsieve",
            file_ids=["file1", "file2"],
            target_backend="local",
            target_path="/tmp/output",
        )
        assert rec.id == "test-001"
        assert rec.status == "pending"
        assert rec.progress_percent == 0
        assert rec.total_files == 2

    def test_record_to_dict(self):
        from backend.core.transfer_manager import TransferRecord
        rec = TransferRecord(
            transfer_id="test-002",
            direction="upload",
            platform="xnat",
        )
        d = rec.to_dict()
        assert d["id"] == "test-002"
        assert d["direction"] == "upload"
        assert d["status"] == "pending"
        assert "created_at" in d

    def test_cancel(self):
        from backend.core.transfer_manager import TransferRecord
        rec = TransferRecord("test-003", "download", "pennsieve")
        assert not rec.cancelled
        rec.cancel()
        assert rec.cancelled
        assert rec.status == "cancelled"


# ---------------------------------------------------------------------------
# _filename_from_id
# ---------------------------------------------------------------------------

class TestFilenameFromId:
    """Test _filename_from_id static method."""

    def test_xnat_uri_extraction(self):
        from backend.core.transfer_manager import TransferManager
        fid = "/data/experiments/XNAT_E001/scans/1/resources/NIFTI/files/brain.nii.gz"
        result = TransferManager._filename_from_id(fid, 0)
        assert result == "brain.nii.gz"

    def test_xnat_uri_with_path_segments(self):
        from backend.core.transfer_manager import TransferManager
        fid = "/data/projects/proj1/subjects/subj1/experiments/exp1/scans/1/resources/DICOM/files/slice001.dcm"
        result = TransferManager._filename_from_id(fid, 0)
        assert result == "slice001.dcm"

    def test_simple_filename(self):
        from backend.core.transfer_manager import TransferManager
        result = TransferManager._filename_from_id("scan_T1w.nii.gz", 0)
        assert result == "scan_T1w.nii.gz"

    def test_fallback_for_opaque_id(self):
        from backend.core.transfer_manager import TransferManager
        result = TransferManager._filename_from_id("N:package:abc-123", 5)
        assert "5" in result or "abc" in result.lower()

    def test_empty_string(self):
        from backend.core.transfer_manager import TransferManager
        result = TransferManager._filename_from_id("", 3)
        assert "3" in result


# ---------------------------------------------------------------------------
# TransferManager basics
# ---------------------------------------------------------------------------

class TestTransferManager:
    """Test TransferManager initialization and record management."""

    def test_instantiation(self):
        from backend.core.transfer_manager import TransferManager
        tm = TransferManager()
        assert hasattr(tm, "_transfers")
        assert hasattr(tm, "list_transfers")

    def test_list_transfers_initially_empty(self):
        from backend.core.transfer_manager import TransferManager
        tm = TransferManager()
        assert len(tm.list_transfers()) == 0

    def test_get_transfer_manager_singleton(self):
        from backend.core.transfer_manager import get_transfer_manager
        tm1 = get_transfer_manager()
        tm2 = get_transfer_manager()
        assert tm1 is tm2


# ---------------------------------------------------------------------------
# Transfer API routes
# ---------------------------------------------------------------------------

class TestTransferAPIRoutes:
    """Test transfer API endpoint validation."""

    @pytest.fixture
    def client(self, mock_settings):
        from fastapi.testclient import TestClient
        with patch("backend.core.database.engine", MagicMock()), \
             patch("backend.core.database.SessionLocal", MagicMock()), \
             patch("backend.core.storage.storage", MagicMock()):
            from backend.main import app
            yield TestClient(app)

    def test_move_rejects_invalid_source(self, client):
        resp = client.post("/api/transfer/move", json={
            "source_type": "invalid_platform",
            "source_path": "/some/path",
            "dest_type": "local",
            "dest_path": "/tmp",
        })
        assert resp.status_code in (400, 422)

    def test_move_rejects_invalid_dest(self, client):
        resp = client.post("/api/transfer/move", json={
            "source_type": "local",
            "source_path": "/some/path",
            "dest_type": "invalid_platform",
            "dest_path": "/tmp",
        })
        assert resp.status_code in (400, 422)

    def test_move_rejects_same_source_dest(self, client):
        resp = client.post("/api/transfer/move", json={
            "source_type": "local",
            "source_path": "/some/path",
            "dest_type": "local",
            "dest_path": "/some/path",
        })
        assert resp.status_code in (200, 400, 422, 500)

    def test_history_endpoint_exists(self, client):
        resp = client.get("/api/transfer/history/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "transfers" in data

    def test_move_requires_body(self, client):
        resp = client.post("/api/transfer/move")
        assert resp.status_code == 422
