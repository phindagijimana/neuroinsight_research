"""Registry views the drafters choose from."""
from __future__ import annotations

from typing import Any, Dict, List

from backend.assistant.model import build_catalog


def available_targets(registry: Any) -> Dict[str, set]:
    return {
        "plugin": {p.id for p in registry.list_plugins()},
        "workflow": {w.id for w in registry.list_workflows()},
    }


def registry_catalog(registry: Any) -> List[Dict[str, Any]]:
    """User-selectable plugins and all workflows, trimmed for the model prompt."""
    targets: List[Dict[str, Any]] = []
    for p in registry.list_plugins(user_selectable_only=True):
        targets.append({
            "target_type": "plugin",
            "target_id": p.id,
            "name": p.name,
            "description": p.description,
            "parameters": p.parameters or [],
        })
    for w in registry.list_workflows():
        targets.append({
            "target_type": "workflow",
            "target_id": w.id,
            "name": w.name,
            "description": w.description,
            "parameters": [],
        })
    return build_catalog(targets)
