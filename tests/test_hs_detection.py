"""
Tests for the Hippocampal Sclerosis Detection package.

Covers:
  - Plugin YAML loading for freesurfer_autorecon_volonly and hs_postprocess
  - Workflow YAML loading for wf_hs_detection_v1
  - Visibility rules (user_selectable, hidden utility)
  - Command template extraction
  - Workflow step wiring
  - Threshold defaults
  - License check integration
  - JSON schema validation
"""
import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def mock_settings(monkeypatch):
    """Isolate from real DB/services."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test_hs.db")
    monkeypatch.setenv("BACKEND_TYPE", "local")
    monkeypatch.setenv("ENVIRONMENT", "development")


@pytest.fixture
def registry(mock_settings):
    from backend.core.plugin_registry import get_plugin_workflow_registry
    return get_plugin_workflow_registry()


# ---------------------------------------------------------------------------
# Plugin: freesurfer_autorecon_volonly
# ---------------------------------------------------------------------------

class TestFreeSurferVolOnly:
    """Tests for the freesurfer_autorecon_volonly plugin."""

    def test_plugin_loads(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert plugin is not None

    def test_plugin_name(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert "VolOnly" in plugin.name or "autorecon" in plugin.name.lower()

    def test_user_selectable(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert plugin.user_selectable is True

    def test_container_image(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert "freesurfer" in plugin.container_image
        assert "7.4.1" in plugin.container_image

    def test_command_template_present(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert plugin.command_template, "Should have a command_template"
        assert "autorecon1" in plugin.command_template
        assert "autorecon2-volonly" in plugin.command_template
        assert "mri_segstats" in plugin.command_template

    def test_has_t1w_input(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        required_keys = [i.get("key", "") for i in plugin.inputs_required]
        assert "T1w" in required_keys

    def test_has_input_format(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert plugin.input_format, "User-selectable plugin must have input_format"

    def test_has_resources(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        profiles = plugin.resource_profiles
        assert "default" in profiles
        assert profiles["default"]["cpus"] >= 4

    def test_domain(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        assert plugin.domain == "structural_mri"

    def test_appears_in_selectable_list(self, registry):
        plugins = registry.list_plugins(user_selectable_only=True)
        ids = [p.id for p in plugins]
        assert "freesurfer_autorecon_volonly" in ids

    def test_api_dict_has_required_fields(self, registry):
        plugin = registry.get_plugin("freesurfer_autorecon_volonly")
        api = plugin.to_api_dict()
        for field in ["id", "name", "version", "type", "container_image", "user_selectable"]:
            assert field in api, f"Missing {field} in API dict"


# ---------------------------------------------------------------------------
# Plugin: hs_postprocess (hidden utility)
# ---------------------------------------------------------------------------

class TestHSPostprocess:
    """Tests for the hs_postprocess utility plugin."""

    def test_plugin_loads(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        assert plugin is not None

    def test_hidden_from_ui(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        assert plugin.user_selectable is False

    def test_ui_category_internal(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        assert plugin.ui_category == "internal_utility"

    def test_not_in_selectable_list(self, registry):
        plugins = registry.list_plugins(user_selectable_only=True)
        ids = [p.id for p in plugins]
        assert "hs_postprocess" not in ids

    def test_in_full_list(self, registry):
        plugins = registry.list_plugins(user_selectable_only=False)
        ids = [p.id for p in plugins]
        assert "hs_postprocess" in ids

    def test_command_template_present(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        assert plugin.command_template
        assert "neuroinsight_hs.postprocess" in plugin.command_template

    def test_required_inputs(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        required_keys = [i.get("key", "") for i in plugin.inputs_required]
        assert "subject_id" in required_keys
        assert "subjects_dir" in required_keys
        assert "bundle_root" in required_keys

    def test_threshold_defaults(self, registry):
        """Verify calibrated HS thresholds are baked into defaults."""
        plugin = registry.get_plugin("hs_postprocess")
        optional = {i["key"]: i for i in plugin.inputs_optional}

        left_th = optional.get("left_hs_threshold", {})
        right_th = optional.get("right_hs_threshold", {})

        assert left_th.get("default") == pytest.approx(-0.070839747728063, abs=1e-12)
        assert right_th.get("default") == pytest.approx(0.046915816971433, abs=1e-12)

    def test_hippo_label_defaults(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        optional = {i["key"]: i for i in plugin.inputs_optional}
        assert optional["left_hippo_label"]["default"] == 17
        assert optional["right_hippo_label"]["default"] == 53

    def test_report_slices_default(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        optional = {i["key"]: i for i in plugin.inputs_optional}
        assert optional["report_slices"]["default"] == "3,4,5,6"

    def test_niivue_opacity_default(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        optional = {i["key"]: i for i in plugin.inputs_optional}
        assert optional["niivue_overlay_opacity"]["default"] == pytest.approx(0.35)

    def test_container_image(self, registry):
        plugin = registry.get_plugin("hs_postprocess")
        assert "hs-postprocess" in plugin.container_image


# ---------------------------------------------------------------------------
# Workflow: wf_hs_detection_v1
# ---------------------------------------------------------------------------

class TestHSDetectionWorkflow:
    """Tests for the HS Detection workflow."""

    def test_workflow_loads(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert wf is not None

    def test_workflow_name(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert "Hippocampal Sclerosis" in wf.name

    def test_workflow_domain(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert wf.domain == "structural_mri"

    def test_two_steps(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert len(wf.steps) == 2

    def test_step_order(self, registry):
        """Step 1 = FreeSurfer VolOnly, Step 2 = HS Postprocess."""
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert wf.steps[0].uses == "freesurfer_autorecon_volonly"
        assert wf.steps[1].uses == "hs_postprocess"

    def test_step_ids(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        step_ids = [s.id for s in wf.steps]
        assert "freesurfer_volonly" in step_ids
        assert "hs_postprocess" in step_ids

    def test_both_plugins_exist(self, registry):
        """Both plugins referenced by the workflow actually exist in registry."""
        wf = registry.get_workflow("wf_hs_detection_v1")
        for step in wf.steps:
            plugin = registry.get_plugin(step.uses)
            assert plugin is not None, f"Workflow references missing plugin: {step.uses}"

    def test_required_inputs(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        required_keys = [i.get("key", "") for i in wf.inputs_required]
        assert "T1w" in required_keys
        assert "subject_id" in required_keys

    def test_optional_inputs_include_thresholds(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        optional_keys = [i.get("key", "") for i in wf.inputs_optional]
        assert "left_hs_threshold" in optional_keys
        assert "right_hs_threshold" in optional_keys

    def test_has_input_format(self, registry):
        wf = registry.get_workflow("wf_hs_detection_v1")
        assert wf.input_format, "Workflow should have input_format"

    def test_appears_in_workflow_list(self, registry):
        workflows = registry.list_workflows()
        ids = [w.id for w in workflows]
        assert "wf_hs_detection_v1" in ids


# ---------------------------------------------------------------------------
# License check integration
# ---------------------------------------------------------------------------

class TestLicenseChecks:
    """Verify freesurfer_autorecon_volonly is in the FS license check set."""

    def test_volonly_in_fs_license_plugins(self, mock_settings):
        from backend.main import FS_LICENSE_PLUGINS
        assert "freesurfer_autorecon_volonly" in FS_LICENSE_PLUGINS

    def test_original_freesurfer_still_checked(self, mock_settings):
        from backend.main import FS_LICENSE_PLUGINS
        assert "freesurfer_recon" in FS_LICENSE_PLUGINS

    def test_hs_postprocess_not_in_fs_list(self, mock_settings):
        from backend.main import FS_LICENSE_PLUGINS
        assert "hs_postprocess" not in FS_LICENSE_PLUGINS


# ---------------------------------------------------------------------------
# JSON Schemas
# ---------------------------------------------------------------------------

class TestSchemas:
    """Verify JSON schema files are valid."""

    SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

    def test_schemas_dir_exists(self):
        assert self.SCHEMAS_DIR.exists()

    def test_hs_metrics_schema_valid_json(self):
        path = self.SCHEMAS_DIR / "hs_metrics.schema.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["type"] == "object"
        assert "subject_id" in data["properties"]
        assert "volumes_mm3" in data["properties"]
        assert "asymmetry_index" in data["properties"]
        assert "classification" in data["properties"]

    def test_hs_metrics_classification_enum(self):
        path = self.SCHEMAS_DIR / "hs_metrics.schema.json"
        data = json.loads(path.read_text())
        enum = data["properties"]["classification"]["enum"]
        assert "Left HS (Right-dominant)" in enum
        assert "Right HS (Left-dominant)" in enum
        assert "No HS (Balanced)" in enum

    def test_niivue_viewer_schema_valid_json(self):
        path = self.SCHEMAS_DIR / "niivue_viewer.schema.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["type"] == "object"
        assert "viewer_type" in data["properties"]
        assert "volumes" in data["properties"]
        assert "qc_sets" in data["properties"]

    def test_niivue_volumes_schema_structure(self):
        path = self.SCHEMAS_DIR / "niivue_viewer.schema.json"
        data = json.loads(path.read_text())
        vol_items = data["properties"]["volumes"]["items"]
        assert "role" in vol_items["properties"]
        assert set(vol_items["properties"]["role"]["enum"]) == {"anatomy", "label"}


# ---------------------------------------------------------------------------
# API endpoints for the new plugins/workflow
# ---------------------------------------------------------------------------

class TestHSDetectionAPI:
    """Test API endpoints return correct data for HS detection package."""

    @pytest.fixture
    def client(self, mock_settings):
        from unittest.mock import patch, MagicMock
        from fastapi.testclient import TestClient
        with patch("backend.core.database.engine", MagicMock()), \
             patch("backend.core.database.SessionLocal", MagicMock()), \
             patch("backend.core.storage.storage", MagicMock()):
            from backend.main import app
            yield TestClient(app)

    def test_get_volonly_plugin_detail(self, client):
        resp = client.get("/api/plugins/freesurfer_autorecon_volonly")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "freesurfer_autorecon_volonly"
        assert data["user_selectable"] is True

    def test_get_hs_postprocess_plugin_detail(self, client):
        resp = client.get("/api/plugins/hs_postprocess")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "hs_postprocess"
        assert data["user_selectable"] is False

    def test_hs_postprocess_excluded_from_default_list(self, client):
        resp = client.get("/api/plugins")
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["plugins"]]
        assert "hs_postprocess" not in ids

    def test_hs_postprocess_included_in_full_list(self, client):
        resp = client.get("/api/plugins", params={"user_selectable_only": "false"})
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()["plugins"]]
        assert "hs_postprocess" in ids

    def test_get_hs_workflow_detail(self, client):
        resp = client.get("/api/workflows/wf_hs_detection_v1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "wf_hs_detection_v1"
        assert len(data["steps"]) == 2

    def test_hs_workflow_in_list(self, client):
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        ids = [w["id"] for w in resp.json()["workflows"]]
        assert "wf_hs_detection_v1" in ids

    def test_volonly_plugin_yaml_endpoint(self, client):
        resp = client.get("/api/plugins/freesurfer_autorecon_volonly/yaml")
        assert resp.status_code == 200
        data = resp.json()
        assert "yaml" in data
        assert "autorecon" in data["yaml"]

    def test_hs_workflow_yaml_endpoint(self, client):
        resp = client.get("/api/workflows/wf_hs_detection_v1/yaml")
        assert resp.status_code == 200
        data = resp.json()
        assert "yaml" in data
        assert "hs_postprocess" in data["yaml"]

    def test_docs_all_includes_hs(self, client):
        resp = client.get("/api/docs/all")
        assert resp.status_code == 200
        data = resp.json()
        plugin_ids = [p["id"] for p in data["plugins"]]
        workflow_ids = [w["id"] for w in data["workflows"]]
        assert "freesurfer_autorecon_volonly" in plugin_ids
        assert "hs_postprocess" in plugin_ids
        assert "wf_hs_detection_v1" in workflow_ids
