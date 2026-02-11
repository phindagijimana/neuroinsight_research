"""
Integration tests for the FastAPI application.

Tests the API endpoints with the TestClient (no real Docker/Redis needed).
"""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create a FastAPI TestClient."""
    from fastapi.testclient import TestClient
    # Mock heavy dependencies before importing the app
    with patch("backend.core.database.engine", MagicMock()), \
         patch("backend.core.database.SessionLocal", MagicMock()), \
         patch("backend.core.storage.storage", MagicMock()):
        from backend.main import app
        yield TestClient(app)


class TestHealthEndpoints:
    """Test system health and status endpoints."""

    def test_health_check(self, client):
        """GET /health returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

    def test_system_resources(self, client):
        """GET /api/system/resources returns CPU/memory info."""
        resp = client.get("/api/system/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert "cpu" in data or "cpus" in data or "resources" in data


class TestPluginEndpoints:
    """Test plugin/workflow API endpoints."""

    def test_list_plugins(self, client):
        """GET /api/plugins returns plugin list."""
        resp = client.get("/api/plugins")
        assert resp.status_code == 200
        data = resp.json()
        assert "plugins" in data
        assert "total" in data

    def test_list_workflows(self, client):
        """GET /api/workflows returns workflow list."""
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data

    def test_get_nonexistent_plugin(self, client):
        """GET /api/plugins/nonexistent returns 404."""
        resp = client.get("/api/plugins/this_does_not_exist")
        assert resp.status_code == 404


class TestVersionManagementEndpoints:
    """Test version management API endpoints."""

    def test_get_versions(self, client):
        """GET /api/registry/versions returns version info."""
        resp = client.get("/api/registry/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "plugins" in data
        assert "workflows" in data

    def test_get_lockfile(self, client):
        """GET /api/registry/lockfile returns a lockfile."""
        resp = client.get("/api/registry/lockfile")
        assert resp.status_code == 200
        data = resp.json()
        assert "generated_at" in data
        assert "plugins" in data

    def test_reload_registry(self, client):
        """POST /api/registry/reload reloads plugins."""
        resp = client.post("/api/registry/reload")
        assert resp.status_code == 200
        data = resp.json()
        assert "plugins" in data
        assert "message" in data


class TestDocumentation:
    """Test documentation endpoints."""

    def test_get_all_docs(self, client):
        """GET /api/docs/all returns documentation."""
        resp = client.get("/api/docs/all")
        assert resp.status_code == 200
        data = resp.json()
        assert "plugins" in data or "total" in data


class TestBrowseEndpoint:
    """Test file browsing endpoint."""

    def test_browse_root(self, client):
        """GET /api/browse with default path returns directory listing."""
        resp = client.get("/api/browse", params={"path": "."})
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert "directories" in data

    def test_browse_nonexistent(self, client):
        """GET /api/browse with bad path returns 404."""
        resp = client.get("/api/browse", params={"path": "/nonexistent/path/xyz"})
        assert resp.status_code == 404


class TestDicomEndpoint:
    """Test DICOM de-identification endpoint."""

    def test_deidentify_nonexistent_dir(self, client):
        """POST /api/dicom/deidentify with bad input returns 404."""
        resp = client.post("/api/dicom/deidentify", json={
            "input_dir": "/nonexistent/dicom/dir",
        })
        assert resp.status_code == 404
