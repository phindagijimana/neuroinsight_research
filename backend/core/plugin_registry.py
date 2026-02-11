"""
Plugin & Workflow Registry

Loads and manages plugins and workflows from YAML definitions.
Plugins are single-tool execution units; workflows are curated sequences.

Key design:
- Plugins define execution (container, command, inputs, outputs)
- Workflows define scientific intent (step ordering, dependency wiring)
- Hidden utility plugins (user_selectable=false) are only used by workflows
- All computation is in plugins; workflows only orchestrate
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PluginDefinition:
    """A single-tool execution unit loaded from YAML."""
    id: str
    name: str
    version: str = "1.0.0"
    type: str = "plugin"
    domain: str = ""
    description: str = ""
    user_selectable: bool = True
    ui_category: str = "primary"
    ui_label: str = ""
    container_image: str = ""
    container_digest: str = ""
    container_runtime: str = "docker"
    inputs_required: List[Dict[str, Any]] = field(default_factory=list)
    inputs_optional: List[Dict[str, Any]] = field(default_factory=list)
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    resource_profiles: Dict[str, Any] = field(default_factory=dict)
    parallelization: Dict[str, Any] = field(default_factory=dict)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    input_format: Dict[str, Any] = field(default_factory=dict)
    command: str = ""
    command_template: str = ""
    execution_stages: List[Dict[str, Any]] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    raw_yaml: Dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "domain": self.domain,
            "description": self.description,
            "user_selectable": self.user_selectable,
            "ui_category": self.ui_category,
            "ui_label": self.ui_label,
            "container_image": self.container_image,
            "container_digest": self.container_digest,
            "inputs": {"required": self.inputs_required, "optional": self.inputs_optional},
            "parameters": self.parameters,
            "resources": self.resources,
            "resource_profiles": self.resource_profiles,
            "parallelization": self.parallelization,
            "outputs": self.outputs,
            "input_format": self.input_format,
            "authors": self.authors,
            "references": self.references,
        }


@dataclass
class WorkflowStep:
    """A single step in a workflow, referencing a plugin."""
    id: str
    uses: str  # plugin_id
    label: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)


@dataclass
class WorkflowDefinition:
    """A curated sequence of plugin steps loaded from YAML."""
    id: str
    name: str
    version: str = "1.0.0"
    type: str = "workflow"
    domain: str = ""
    description: str = ""
    inputs_required: List[Dict[str, Any]] = field(default_factory=list)
    inputs_optional: List[Dict[str, Any]] = field(default_factory=list)
    input_format: Dict[str, Any] = field(default_factory=dict)
    steps: List[WorkflowStep] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    raw_yaml: Dict[str, Any] = field(default_factory=dict)

    def to_api_dict(self, plugin_registry: Optional[Dict[str, "PluginDefinition"]] = None) -> Dict[str, Any]:
        """Serialize for API response, enriching steps with plugin metadata."""
        steps_list = []
        for step in self.steps:
            step_dict = {
                "id": step.id,
                "uses": step.uses,
                "label": step.label,
                "inputs": step.inputs,
                "parameters": step.parameters,
                "depends_on": step.depends_on,
            }
            if plugin_registry and step.uses in plugin_registry:
                plugin = plugin_registry[step.uses]
                step_dict["plugin_name"] = plugin.name
                step_dict["plugin_description"] = plugin.description
            steps_list.append(step_dict)

        # Extract flat list of plugin IDs referenced by steps
        plugin_ids = [step.uses for step in self.steps if step.uses]

        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "domain": self.domain,
            "description": self.description,
            "inputs": {"required": self.inputs_required, "optional": self.inputs_optional},
            "input_format": self.input_format,
            "steps": steps_list,
            "plugin_ids": plugin_ids,
            "outputs": self.outputs,
            "authors": self.authors,
            "references": self.references,
        }


class PluginWorkflowRegistry:
    """Registry that loads and manages plugins and workflows."""

    def __init__(self, plugins_dir, workflows_dir):
        self.plugins_dir = Path(plugins_dir)
        self.workflows_dir = Path(workflows_dir)
        self.plugins: Dict[str, PluginDefinition] = {}
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self._load_plugins()
        self._load_workflows()
        self._validate_workflows()
        logger.info(
            f"PluginWorkflowRegistry initialized: "
            f"{len(self.plugins)} plugins, {len(self.workflows)} workflows"
        )

    def _load_plugins(self) -> None:
        """Load all plugin YAMLs from plugins directory."""
        if not self.plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {self.plugins_dir}")
            return
        yaml_files = list(self.plugins_dir.glob("*.yaml")) + list(self.plugins_dir.glob("*.yml"))
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    continue
                # Skip non-plugin types
                if data.get("type") != "plugin":
                    continue

                plugin_id = data.get("id", yaml_file.stem)
                visibility = data.get("visibility", {})
                container = data.get("container", {})
                resources = data.get("resources", {})

                # Extract command_template from multiple locations (in priority order):
                #   1. execution.stages[0].command_template  (stage-based plugins)
                #   2. execution.command_template             (single-stage plugins)
                #   3. top-level "command"                    (legacy fallback)
                execution_block = data.get("execution", {})
                execution_stages = execution_block.get("stages", [])
                command_template = ""
                if execution_stages and isinstance(execution_stages[0], dict):
                    command_template = execution_stages[0].get("command_template", "")
                if not command_template:
                    command_template = execution_block.get("command_template", "")

                # Fall back to top-level command if no stage template
                top_level_command = data.get("command", "")
                effective_command = command_template or top_level_command

                plugin = PluginDefinition(
                    id=plugin_id,
                    name=data.get("name", plugin_id),
                    version=data.get("version", "1.0.0"),
                    type="plugin",
                    domain=data.get("domain", ""),
                    description=data.get("description", ""),
                    user_selectable=visibility.get("user_selectable", True),
                    ui_category=visibility.get("ui_category", "primary"),
                    ui_label=visibility.get("ui_label", ""),
                    container_image=container.get("image", ""),
                    container_digest=container.get("digest", "") or "",
                    container_runtime=container.get("runtime", "docker"),
                    inputs_required=data.get("inputs", {}).get("required", []),
                    inputs_optional=data.get("inputs", {}).get("optional", []),
                    parameters=data.get("parameters", []),
                    resources=resources.get("default", resources),
                    resource_profiles=resources.get("profiles", {}),
                    parallelization=resources.get("parallelization", {}),
                    outputs=data.get("outputs", []),
                    input_format=data.get("input_format", {}),
                    command=effective_command,
                    command_template=command_template,
                    execution_stages=[s for s in execution_stages if isinstance(s, dict)],
                    authors=data.get("authors", []),
                    references=data.get("references", []),
                    raw_yaml=data,
                )
                self.plugins[plugin_id] = plugin
                logger.debug(f"Loaded plugin: {plugin_id}")
            except Exception as e:
                logger.error(f"Failed to load plugin from {yaml_file}: {e}")

    def _load_workflows(self) -> None:
        """Load all workflow YAMLs from workflows directory."""
        if not self.workflows_dir.exists():
            logger.warning(f"Workflows directory not found: {self.workflows_dir}")
            return
        yaml_files = list(self.workflows_dir.glob("*.yaml")) + list(self.workflows_dir.glob("*.yml"))
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    continue
                if data.get("type") != "workflow":
                    continue

                wf_id = data.get("id", yaml_file.stem)

                # Parse steps
                steps = []
                for step_data in data.get("steps", []):
                    if isinstance(step_data, dict):
                        steps.append(WorkflowStep(
                            id=step_data.get("id", ""),
                            uses=step_data.get("uses", ""),
                            label=step_data.get("label", ""),
                            inputs=step_data.get("inputs", {}),
                            parameters=step_data.get("parameters", {}),
                            depends_on=step_data.get("depends_on", []),
                        ))

                workflow = WorkflowDefinition(
                    id=wf_id,
                    name=data.get("name", wf_id),
                    version=data.get("version", "1.0.0"),
                    type="workflow",
                    domain=data.get("domain", ""),
                    description=data.get("description", ""),
                    inputs_required=data.get("inputs", {}).get("required", []),
                    inputs_optional=data.get("inputs", {}).get("optional", []),
                    input_format=data.get("input_format", {}),
                    steps=steps,
                    outputs=data.get("outputs", []),
                    authors=data.get("authors", []),
                    references=data.get("references", []),
                    raw_yaml=data,
                )
                self.workflows[wf_id] = workflow
                logger.debug(f"Loaded workflow: {wf_id}")
            except Exception as e:
                logger.error(f"Failed to load workflow from {yaml_file}: {e}")

    def _validate_workflows(self) -> None:
        """Validate that all workflow steps reference existing plugins."""
        for wf_id, workflow in self.workflows.items():
            for step in workflow.steps:
                if step.uses not in self.plugins:
                    logger.warning(
                        f"Workflow '{wf_id}' step '{step.id}' "
                        f"references unknown plugin '{step.uses}'"
                    )

    def get_plugin(self, plugin_id: str) -> Optional[PluginDefinition]:
        return self.plugins.get(plugin_id)

    def list_plugins(self, user_selectable_only: bool = False) -> List[PluginDefinition]:
        plugins = list(self.plugins.values())
        if user_selectable_only:
            plugins = [p for p in plugins if p.user_selectable]
        return plugins

    def get_plugin_ids(self) -> List[str]:
        return sorted(self.plugins.keys())

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[WorkflowDefinition]:
        return list(self.workflows.values())

    def get_workflow_ids(self) -> List[str]:
        return sorted(self.workflows.keys())

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def get_plugin_versions(self) -> Dict[str, str]:
        """Get a mapping of plugin_id -> version for all loaded plugins."""
        return {pid: p.version for pid, p in self.plugins.items()}

    def get_workflow_versions(self) -> Dict[str, str]:
        """Get a mapping of workflow_id -> version for all loaded workflows."""
        return {wid: w.version for wid, w in self.workflows.items()}

    def generate_lockfile(self) -> Dict[str, Any]:
        """Generate a lockfile dict capturing all current plugin/workflow versions.

        This is useful for reproducibility: a job can record exactly which
        plugin and workflow versions were used.
        """
        import hashlib
        import json as _json

        lockfile = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "plugins": {},
            "workflows": {},
        }
        for pid, p in sorted(self.plugins.items()):
            # Hash the raw YAML content for integrity verification
            yaml_str = _json.dumps(p.raw_yaml, sort_keys=True, default=str)
            content_hash = hashlib.sha256(yaml_str.encode()).hexdigest()[:16]
            lockfile["plugins"][pid] = {
                "version": p.version,
                "container_image": p.container_image,
                "content_hash": content_hash,
            }
        for wid, w in sorted(self.workflows.items()):
            yaml_str = _json.dumps(w.raw_yaml, sort_keys=True, default=str)
            content_hash = hashlib.sha256(yaml_str.encode()).hexdigest()[:16]
            step_plugins = [s.uses for s in w.steps]
            lockfile["workflows"][wid] = {
                "version": w.version,
                "step_plugins": step_plugins,
                "content_hash": content_hash,
            }
        return lockfile

    def verify_lockfile(self, lockfile: Dict[str, Any]) -> Dict[str, Any]:
        """Verify current registry against a lockfile.

        Returns a report of mismatches (version changes, missing items).
        """
        import hashlib
        import json as _json

        report: Dict[str, Any] = {"plugins": [], "workflows": [], "status": "ok"}

        for pid, lock_info in lockfile.get("plugins", {}).items():
            plugin = self.plugins.get(pid)
            if not plugin:
                report["plugins"].append({"id": pid, "issue": "missing"})
                report["status"] = "mismatch"
            elif plugin.version != lock_info.get("version"):
                report["plugins"].append({
                    "id": pid,
                    "issue": "version_changed",
                    "expected": lock_info["version"],
                    "actual": plugin.version,
                })
                report["status"] = "mismatch"
            else:
                yaml_str = _json.dumps(plugin.raw_yaml, sort_keys=True, default=str)
                content_hash = hashlib.sha256(yaml_str.encode()).hexdigest()[:16]
                if content_hash != lock_info.get("content_hash"):
                    report["plugins"].append({
                        "id": pid,
                        "issue": "content_changed",
                        "expected_hash": lock_info.get("content_hash"),
                        "actual_hash": content_hash,
                    })
                    report["status"] = "mismatch"

        for wid, lock_info in lockfile.get("workflows", {}).items():
            workflow = self.workflows.get(wid)
            if not workflow:
                report["workflows"].append({"id": wid, "issue": "missing"})
                report["status"] = "mismatch"
            elif workflow.version != lock_info.get("version"):
                report["workflows"].append({
                    "id": wid,
                    "issue": "version_changed",
                    "expected": lock_info["version"],
                    "actual": workflow.version,
                })
                report["status"] = "mismatch"

        return report

    def reload(self) -> None:
        """Reload all plugins and workflows from disk."""
        logger.info("Reloading plugin/workflow registry...")
        self.plugins.clear()
        self.workflows.clear()
        self._load_plugins()
        self._load_workflows()
        self._validate_workflows()

    def __repr__(self) -> str:
        return f"PluginWorkflowRegistry({len(self.plugins)} plugins, {len(self.workflows)} workflows)"


_pw_registry: Optional[PluginWorkflowRegistry] = None


def get_plugin_workflow_registry(plugins_dir=None, workflows_dir=None) -> PluginWorkflowRegistry:
    """Get global plugin/workflow registry instance (singleton)."""
    global _pw_registry
    if _pw_registry is None:
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        if workflows_dir is None:
            workflows_dir = Path(__file__).parent.parent.parent / "workflows"
        _pw_registry = PluginWorkflowRegistry(plugins_dir, workflows_dir)
    return _pw_registry
