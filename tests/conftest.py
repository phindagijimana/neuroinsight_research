"""
Shared pytest fixtures for NeuroInsight Research Tool tests.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Environment: override defaults so tests never hit real services
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    """Set safe environment variables for every test."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("REDIS_PASSWORD", "test")
    monkeypatch.setenv("MINIO_ENDPOINT", "localhost:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "minioadmin")
    monkeypatch.setenv("MINIO_SECRET_KEY", "minioadmin")
    monkeypatch.setenv("DATA_DIR", tempfile.mkdtemp())
    monkeypatch.setenv("UPLOAD_DIR", tempfile.mkdtemp())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_nifti(tmp_dir):
    """Create a minimal fake NIfTI file for testing."""
    nifti = tmp_dir / "test.nii.gz"
    nifti.write_bytes(b"\x1f\x8b" + b"\x00" * 100)  # gzip magic + padding
    return str(nifti)


@pytest.fixture
def sample_dicom_dir(tmp_dir):
    """Create a directory with minimal fake DICOM files."""
    dicom_dir = tmp_dir / "dicoms"
    dicom_dir.mkdir()
    for i in range(3):
        dcm = dicom_dir / f"slice_{i:03d}.dcm"
        # DICOM files start with 128-byte preamble + "DICM" magic
        dcm.write_bytes(b"\x00" * 128 + b"DICM" + b"\x00" * 50)
    return str(dicom_dir)


@pytest.fixture
def plugin_yaml_dir(tmp_dir):
    """Create a temporary plugins directory with a sample plugin YAML."""
    plugins_dir = tmp_dir / "plugins"
    plugins_dir.mkdir()
    plugin_yaml = {
        "id": "test_plugin",
        "name": "Test Plugin",
        "type": "plugin",
        "version": "1.0.0",
        "domain": "testing",
        "description": "A test plugin for unit tests",
        "visibility": {"user_selectable": True, "ui_category": "primary"},
        "container": {"image": "test/image:latest", "runtime": "docker"},
        "inputs": {
            "required": [{"id": "t1w", "label": "T1w scan", "format": ".nii.gz"}],
            "optional": [],
        },
        "parameters": [
            {"id": "threads", "label": "CPU threads", "type": "integer", "default": 4},
        ],
        "resources": {
            "default": {"cpus": 4, "memory_gb": 8, "time_hours": 2},
            "profiles": {
                "light": {"cpus": 2, "memory_gb": 4, "time_hours": 1},
                "heavy": {"cpus": 16, "memory_gb": 64, "time_hours": 12},
            },
        },
        "execution": {
            "stages": [
                {
                    "id": "main",
                    "command_template": "run_pipeline --input /data/inputs/t1w.nii.gz --output /data/outputs --threads {threads}",
                }
            ]
        },
        "outputs": [
            {"id": "brain_mask", "label": "Brain mask", "format": ".nii.gz"},
        ],
        "authors": ["Test Author"],
    }
    import yaml
    (plugins_dir / "test_plugin.yaml").write_text(yaml.dump(plugin_yaml))
    return str(plugins_dir)


@pytest.fixture
def workflow_yaml_dir(tmp_dir, plugin_yaml_dir):
    """Create a temporary workflows directory with a sample workflow YAML."""
    workflows_dir = tmp_dir / "workflows"
    workflows_dir.mkdir()
    workflow_yaml = {
        "id": "test_workflow",
        "name": "Test Workflow",
        "type": "workflow",
        "version": "1.0.0",
        "domain": "testing",
        "description": "A test workflow for unit tests",
        "inputs": {
            "required": [{"id": "t1w", "label": "T1w scan", "format": ".nii.gz"}],
        },
        "steps": [
            {"id": "step1", "uses": "test_plugin", "label": "Run Test Plugin"},
        ],
        "outputs": [
            {"id": "result", "label": "Result", "format": ".nii.gz"},
        ],
    }
    import yaml
    (workflows_dir / "test_workflow.yaml").write_text(yaml.dump(workflow_yaml))
    return str(workflows_dir)


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    client = MagicMock()
    client.images.get.return_value = MagicMock()
    client.containers.run.return_value = MagicMock(
        id="test_container_123",
        wait=MagicMock(return_value={"StatusCode": 0}),
        logs=MagicMock(return_value=b"Processing complete\n"),
        remove=MagicMock(),
    )
    return client
