"""
Tests for the plugin/workflow registry, including version management.
"""
import json
import pytest
from pathlib import Path


class TestPluginRegistry:
    """Test PluginWorkflowRegistry loading, querying, and version management."""

    def test_load_plugins(self, plugin_yaml_dir, workflow_yaml_dir):
        """Plugins load correctly from YAML files."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        assert len(registry.plugins) == 1
        plugin = registry.get_plugin("test_plugin")
        assert plugin is not None
        assert plugin.name == "Test Plugin"
        assert plugin.version == "1.0.0"
        assert plugin.container_image == "test/image:latest"
        assert plugin.domain == "testing"

    def test_plugin_command_template_extraction(self, plugin_yaml_dir, workflow_yaml_dir):
        """Command template is extracted from execution.stages[0]."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        plugin = registry.get_plugin("test_plugin")
        assert "run_pipeline" in plugin.command_template
        assert "/data/inputs" in plugin.command_template

    def test_plugin_to_api_dict(self, plugin_yaml_dir, workflow_yaml_dir):
        """Plugin serializes correctly for API responses."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        plugin = registry.get_plugin("test_plugin")
        api_dict = plugin.to_api_dict()
        assert api_dict["id"] == "test_plugin"
        assert api_dict["name"] == "Test Plugin"
        assert "required" in api_dict["inputs"]
        assert len(api_dict["parameters"]) == 1

    def test_load_workflows(self, plugin_yaml_dir, workflow_yaml_dir):
        """Workflows load and reference plugins correctly."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        assert len(registry.workflows) == 1
        workflow = registry.get_workflow("test_workflow")
        assert workflow is not None
        assert workflow.name == "Test Workflow"
        assert len(workflow.steps) == 1
        assert workflow.steps[0].uses == "test_plugin"

    def test_list_plugins_user_selectable(self, plugin_yaml_dir, workflow_yaml_dir):
        """List plugins filters by user_selectable."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        all_plugins = registry.list_plugins(user_selectable_only=False)
        selectable = registry.list_plugins(user_selectable_only=True)
        assert len(all_plugins) >= len(selectable)

    def test_get_plugin_versions(self, plugin_yaml_dir, workflow_yaml_dir):
        """Version map returns correct versions."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        versions = registry.get_plugin_versions()
        assert versions["test_plugin"] == "1.0.0"

    def test_generate_lockfile(self, plugin_yaml_dir, workflow_yaml_dir):
        """Lockfile generation captures versions and content hashes."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        lockfile = registry.generate_lockfile()
        assert "generated_at" in lockfile
        assert "test_plugin" in lockfile["plugins"]
        assert lockfile["plugins"]["test_plugin"]["version"] == "1.0.0"
        assert "content_hash" in lockfile["plugins"]["test_plugin"]
        assert "test_workflow" in lockfile["workflows"]

    def test_verify_lockfile_ok(self, plugin_yaml_dir, workflow_yaml_dir):
        """Verifying against a current lockfile returns OK."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        lockfile = registry.generate_lockfile()
        report = registry.verify_lockfile(lockfile)
        assert report["status"] == "ok"

    def test_verify_lockfile_mismatch(self, plugin_yaml_dir, workflow_yaml_dir):
        """Verifying against a modified lockfile detects mismatch."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        lockfile = registry.generate_lockfile()
        lockfile["plugins"]["test_plugin"]["version"] = "2.0.0"
        report = registry.verify_lockfile(lockfile)
        assert report["status"] == "mismatch"
        assert any(p["id"] == "test_plugin" for p in report["plugins"])

    def test_verify_lockfile_missing_plugin(self, plugin_yaml_dir, workflow_yaml_dir):
        """Verifying with an extra lockfile entry detects missing plugin."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        lockfile = registry.generate_lockfile()
        lockfile["plugins"]["nonexistent_plugin"] = {"version": "1.0.0"}
        report = registry.verify_lockfile(lockfile)
        assert report["status"] == "mismatch"

    def test_reload(self, plugin_yaml_dir, workflow_yaml_dir):
        """Registry reload re-reads plugins from disk."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(plugin_yaml_dir, workflow_yaml_dir)

        assert len(registry.plugins) == 1
        registry.reload()
        assert len(registry.plugins) == 1

    def test_empty_dirs(self, tmp_dir):
        """Registry handles empty plugin/workflow directories."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        empty_p = tmp_dir / "empty_plugins"
        empty_w = tmp_dir / "empty_workflows"
        empty_p.mkdir()
        empty_w.mkdir()
        registry = PluginWorkflowRegistry(str(empty_p), str(empty_w))
        assert len(registry.plugins) == 0
        assert len(registry.workflows) == 0

    def test_nonexistent_dirs(self, tmp_dir):
        """Registry handles non-existent directories gracefully."""
        from backend.core.plugin_registry import PluginWorkflowRegistry
        registry = PluginWorkflowRegistry(str(tmp_dir / "nope"), str(tmp_dir / "nope2"))
        assert len(registry.plugins) == 0
