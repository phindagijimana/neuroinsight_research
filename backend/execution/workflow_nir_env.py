"""Shared NIR_INPUT_ROOT adjustments for multi-step workflows (SLURM + local Docker)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from backend.core.execution import JobSpec

logger = logging.getLogger(__name__)


def resolve_workflow_directory_input_container_root(wf_id: str) -> Optional[str]:
    """Return e.g. /data/inputs/input_dir when the workflow declares a directory input key."""
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry

        registry = get_plugin_workflow_registry()
        wf = registry.get_workflow(wf_id)
        if not wf:
            return None
        dir_keys: List[str] = []
        for inp in wf.inputs_required or []:
            if isinstance(inp, dict):
                key, typ = inp.get("key"), inp.get("type", "")
            else:
                key, typ = getattr(inp, "key", ""), getattr(inp, "type", "")
            if typ == "directory" and key:
                dir_keys.append(key)
        if not dir_keys:
            return None
        chosen = "input_dir" if "input_dir" in dir_keys else dir_keys[0]
        return f"/data/inputs/{chosen}"
    except Exception as e:
        logger.debug("Could not resolve workflow directory input root: %s", e)
        return None


def apply_workflow_nir_input_root_command_overrides(
    *,
    workflow_steps: List[str],
    step_idx: int,
    step_plugin_id: str,
    wf_id: Optional[str],
    cmd_script: str,
) -> str:
    """Adjust export NIR_INPUT_ROOT in plugin command templates for workflow staging."""
    if not workflow_steps or not cmd_script:
        return cmd_script
    if step_idx == 0:
        if wf_id:
            root = resolve_workflow_directory_input_container_root(wf_id)
            if root:
                cmd_script = cmd_script.replace(
                    "export NIR_INPUT_ROOT=/data/inputs",
                    f"export NIR_INPUT_ROOT={root}",
                )
        return cmd_script
    def _chain_eeg_preprocessing_root(script: str) -> str:
        if "/data/inputs/eeg_preprocessing" not in script:
            script = (
                "# NIR workflow chain: /data/inputs/eeg_preprocessing\n" + script
            )
        return script.replace(
            "export NIR_INPUT_ROOT=/data/inputs",
            "export NIR_INPUT_ROOT=/data/inputs/eeg_preprocessing",
        )

    prev = workflow_steps[step_idx - 1]
    # Spike reads clean_raw.fif from preprocessing output (SLURM bind: .../eeg_preprocessing).
    if prev == "eeg_preprocessing" and step_plugin_id == "spike_detection":
        cmd_script = _chain_eeg_preprocessing_root(cmd_script)
    # Coreg reads the same clean_raw.fif but follows spike_detection; still mount preprocessing.
    elif step_plugin_id == "eeg_mri_coregistration":
        cmd_script = _chain_eeg_preprocessing_root(cmd_script)
    elif step_plugin_id == "forward_model":
        if "/data/inputs/forward_merge" not in cmd_script:
            cmd_script = (
                "# NIR workflow chain: /data/inputs/forward_merge\n" + cmd_script
            )
        cmd_script = cmd_script.replace(
            "export NIR_INPUT_ROOT=/data/inputs",
            "export NIR_INPUT_ROOT=/data/inputs/forward_merge",
        )
    elif step_plugin_id == "source_localization":
        if "/data/inputs/source_merge" not in cmd_script:
            cmd_script = (
                "# NIR workflow chain: /data/inputs/source_merge\n" + cmd_script
            )
        cmd_script = cmd_script.replace(
            "export NIR_INPUT_ROOT=/data/inputs",
            "export NIR_INPUT_ROOT=/data/inputs/source_merge",
        )
    return cmd_script
