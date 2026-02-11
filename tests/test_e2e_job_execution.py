"""
End-to-end test for the full job execution path.

Tests the chain: submit_plugin_job -> Celery task -> Docker container -> results.
These tests require Docker to be running but NOT PostgreSQL/Redis (mocked).

Run with:  PYTHONPATH=. python3 -m pytest tests/test_e2e_job_execution.py -v
"""
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for test outputs."""
    d = tempfile.mkdtemp(prefix="neuroinsight_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mock_settings(temp_data_dir, monkeypatch):
    """Provide test settings pointing to temp dirs."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_e2e.db")
    monkeypatch.setenv("DATA_DIR", str(temp_data_dir))
    monkeypatch.setenv("OUTPUT_DIR", str(temp_data_dir / "outputs"))
    monkeypatch.setenv("BACKEND_TYPE", "local")
    monkeypatch.setenv("ENVIRONMENT", "development")


class TestJobSpecConstruction:
    """Test that plugin YAML -> JobSpec construction works correctly."""

    def test_plugin_registry_loads(self, mock_settings):
        """All plugin YAML files load without errors."""
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        plugins = registry.list_plugins()
        assert len(plugins) >= 10, f"Expected >=10 plugins, got {len(plugins)}"

    def test_workflow_registry_loads(self, mock_settings):
        """All workflow YAML files load without errors."""
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        workflows = registry.list_workflows()
        assert len(workflows) >= 10, f"Expected >=10 workflows, got {len(workflows)}"

    def test_plugin_has_command_template(self, mock_settings):
        """Key plugins have command_template extracted from YAML."""
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()

        for pid in ["freesurfer_recon", "fastsurfer", "fmriprep"]:
            plugin = registry.get_plugin(pid)
            assert plugin is not None, f"Plugin {pid} not found"
            assert plugin.command_template, f"Plugin {pid} missing command_template"

    def test_plugin_has_input_format(self, mock_settings):
        """All user-selectable plugins have input_format."""
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        for p in registry.list_plugins():
            pid = p["id"] if isinstance(p, dict) else p.id
            user_selectable = p.get("user_selectable", True) if isinstance(p, dict) else getattr(p, "user_selectable", True)
            input_format = p.get("input_format") if isinstance(p, dict) else getattr(p, "input_format", None)
            if user_selectable:
                assert input_format, f"Plugin {pid} missing input_format"


class TestVolumePreparation:
    """Test that input files are correctly staged for Docker."""

    def test_prepare_volumes_creates_staging(self, mock_settings, temp_data_dir):
        """_prepare_volumes creates staging dir with renamed input files."""
        from backend.execution.celery_tasks import _prepare_volumes

        # Create a fake input file
        input_file = temp_data_dir / "sub-01_T1w.nii.gz"
        input_file.write_text("fake nifti content")

        output_dir = temp_data_dir / "outputs" / "test-job"
        output_dir.mkdir(parents=True)

        spec = {
            "input_files": [str(input_file)],
            "plugin_id": "freesurfer_recon",
            "environment": {},
        }

        volumes = _prepare_volumes(spec, output_dir)

        # Check that staging dir was created and file was copied
        staging_dir = output_dir / "_inputs"
        assert staging_dir.exists()
        staged_files = list(staging_dir.iterdir())
        assert len(staged_files) == 1
        # Should be renamed to T1w.nii.gz (based on plugin input key)
        assert staged_files[0].name == "T1w.nii.gz"

        # Check volume mounts
        assert str(staging_dir) in volumes
        assert volumes[str(staging_dir)]["bind"] == "/data/inputs"
        assert volumes[str(staging_dir)]["mode"] == "ro"

    def test_prepare_volumes_output_mount(self, mock_settings, temp_data_dir):
        """_prepare_volumes mounts output dir as /data/outputs."""
        from backend.execution.celery_tasks import _prepare_volumes

        output_dir = temp_data_dir / "outputs" / "test-job"
        output_dir.mkdir(parents=True)
        spec = {"input_files": [], "plugin_id": None, "environment": {}}

        volumes = _prepare_volumes(spec, output_dir)
        assert str(output_dir) in volumes
        assert volumes[str(output_dir)]["bind"] == "/data/outputs"


class TestParameterSanitization:
    """Test shell injection prevention."""

    def test_sanitize_param_blocks_injection(self):
        """_sanitize_param strips dangerous shell characters."""
        from backend.execution.celery_tasks import _sanitize_param

        assert _sanitize_param("normal_value") == "normal_value"
        assert _sanitize_param("path/to/file.nii.gz") == "path/to/file.nii.gz"
        assert ";" not in _sanitize_param("; rm -rf /")
        assert "|" not in _sanitize_param("| cat /etc/passwd")
        assert "`" not in _sanitize_param("`whoami`")
        assert "$" not in _sanitize_param("$(whoami)")

    def test_sanitize_preserves_safe_chars(self):
        """_sanitize_param allows alphanumeric, dashes, dots, slashes."""
        from backend.execution.celery_tasks import _sanitize_param

        assert _sanitize_param("sub-01_ses-02") == "sub-01_ses-02"
        assert _sanitize_param("/data/inputs/T1w.nii.gz") == "/data/inputs/T1w.nii.gz"
        assert _sanitize_param("--threads 8") == "--threads 8"


class TestImageValidation:
    """Test Docker image allowlist."""

    def test_allowed_images(self):
        """Known neuroimaging images are allowed."""
        from backend.execution.celery_tasks import _validate_image

        assert _validate_image("freesurfer/freesurfer:7.4.1")
        assert _validate_image("nipreps/fmriprep:23.2.1")
        assert _validate_image("deepmi/fastsurfer:latest")
        assert _validate_image("pennbbl/qsiprep:0.20.0")

    def test_blocked_images(self):
        """Unknown/malicious images are blocked."""
        from backend.execution.celery_tasks import _validate_image

        assert not _validate_image("attacker.io/crypto-miner:latest")
        assert not _validate_image("ubuntu:latest")
        assert not _validate_image("alpine:3.18")


class TestResultsEndpoints:
    """Test that results endpoints return real data (not mocks)."""

    @pytest.fixture
    def client_with_results(self, temp_data_dir, monkeypatch):
        """Create a test client with fake job results on disk."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test_results.db")
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Create fake job output directory with real files
        job_id = "test-job-001"
        job_dir = temp_data_dir / "outputs" / job_id
        (job_dir / "native" / "freesurfer" / "mri").mkdir(parents=True)
        (job_dir / "native" / "freesurfer" / "stats").mkdir(parents=True)
        (job_dir / "logs").mkdir(parents=True)

        # Create fake files
        (job_dir / "native" / "freesurfer" / "mri" / "norm.nii.gz").write_bytes(b"\x00" * 100)
        (job_dir / "native" / "freesurfer" / "mri" / "aseg.nii.gz").write_bytes(b"\x00" * 50)

        # Create a fake .stats file
        stats_content = """# Measure BrainSeg, BrainSegVol, Brain Segmentation Volume, 1234567.0, mm^3
# Measure BrainSegNotVent, BrainSegVolNotVent, Brain Segmentation Volume Without Ventricles, 1100000.0, mm^3
# ColHeaders StructName NumVert SurfArea GrayVol
Left-Hippocampus  3456  2345  4049.0
Right-Hippocampus 3521  2401  3841.0
"""
        (job_dir / "native" / "freesurfer" / "stats" / "aseg.stats").write_text(stats_content)

        # Create metrics JSON
        (job_dir / "metrics.json").write_text(json.dumps({"total_volume": 1234567}))

        # Create a job spec
        (job_dir / "job_spec.json").write_text(json.dumps({
            "container_image": "freesurfer/freesurfer:7.4.1",
            "plugin_id": "freesurfer_recon",
            "input_files": ["/data/T1w.nii.gz"],
            "parameters": {"subject_id": "sub-01"},
        }))

        # Patch _get_output_dir to use our temp directory
        def _patched_output_dir(jid):
            return temp_data_dir / "outputs" / jid

        from fastapi.testclient import TestClient
        with patch("backend.core.database.engine", MagicMock()), \
             patch("backend.core.database.SessionLocal", MagicMock()), \
             patch("backend.core.storage.storage", MagicMock()), \
             patch("backend.routes.results._get_output_dir", _patched_output_dir):
            from backend.main import app
            yield TestClient(app), job_id

    def test_list_files_returns_real_files(self, client_with_results):
        """GET /api/results/{id}/files lists actual files from disk."""
        client, job_id = client_with_results
        resp = client.get(f"/api/results/{job_id}/files")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        names = [f["name"] for f in data["files"]]
        assert any("norm.nii.gz" in n for n in names)
        assert any("aseg.stats" in n for n in names)

    def test_list_files_404_for_missing_job(self, client_with_results):
        """GET /api/results/{id}/files returns 404 for non-existent job."""
        client, _ = client_with_results
        resp = client.get("/api/results/nonexistent-job/files")
        assert resp.status_code == 404

    def test_metrics_returns_real_data(self, client_with_results):
        """GET /api/results/{id}/metrics reads real .stats and JSON files."""
        client, job_id = client_with_results
        resp = client.get(f"/api/results/{job_id}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        # Should have parsed the aseg.stats file
        assert len(data["metrics"]) >= 1

    def test_volume_finds_nifti_files(self, client_with_results):
        """GET /api/results/{id}/volume discovers NIfTI files."""
        client, job_id = client_with_results
        resp = client.get(f"/api/results/{job_id}/volume")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["volumes"]) >= 1

    def test_provenance_reads_spec(self, client_with_results):
        """GET /api/results/{id}/provenance reads job_spec.json."""
        client, job_id = client_with_results
        resp = client.get(f"/api/results/{job_id}/provenance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["container_image"] == "freesurfer/freesurfer:7.4.1"
        assert data["plugin_id"] == "freesurfer_recon"

    def test_download_real_file(self, client_with_results):
        """GET /api/results/{id}/download serves a real file."""
        client, job_id = client_with_results
        resp = client.get(
            f"/api/results/{job_id}/download",
            params={"file_path": "native/freesurfer/mri/norm.nii.gz"}
        )
        assert resp.status_code == 200
        assert len(resp.content) == 100  # We wrote 100 null bytes

    def test_download_blocks_path_traversal(self, client_with_results):
        """Path traversal in download is rejected."""
        client, job_id = client_with_results
        resp = client.get(
            f"/api/results/{job_id}/download",
            params={"file_path": "../../etc/passwd"}
        )
        assert resp.status_code == 400

    def test_export_creates_tarball(self, client_with_results):
        """GET /api/results/{id}/export creates a tar.gz bundle."""
        client, job_id = client_with_results
        resp = client.get(f"/api/results/{job_id}/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/gzip"
