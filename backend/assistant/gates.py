"""Read-only checks on a draft: SciCap invoke and SciGuard validate.

The public ``scicap`` and ``sciguard`` packages need Python 3.11+, and this
backend runs on 3.10, so they are called as CLIs from a separate venv. When a
CLI is missing the check is reported as ``not_run``; it is never shown as a
pass.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from backend.assistant.drafting import Draft

ANNOTATIONS_DIR = Path(__file__).resolve().parent / "annotations"

# Pipelines whose input matches a SciCap capability profile.
CAPABILITY_FOR_TARGET = {
    "fastsurfer": "neuro.t1.anatomical_segmentation",
    "freesurfer_recon": "neuro.t1.anatomical_segmentation",
    "freesurfer_autorecon_volonly": "neuro.t1.anatomical_segmentation",
    "hippo_subfields_t1": "neuro.t1.hippocampal_volumes",
}

SCICAP_BLOCKING = {"REJECT", "ABSTAIN"}
SCIGUARD_BLOCKING = {"FAIL"}

_TIMEOUT_S = 60


def _gates_dirs() -> List[Path]:
    dirs: List[Path] = []
    configured = os.environ.get("NIR_GATES_BIN", "")
    if not configured:
        try:
            from backend.core.config import get_settings

            configured = get_settings().assistant_gates_bin
        except Exception:
            configured = ""
    if configured:
        dirs.append(Path(configured).expanduser())
    dirs.append(Path.home() / ".venvs" / "nir-gates" / "bin")
    return dirs


def find_gate(name: str) -> Optional[str]:
    for folder in _gates_dirs():
        candidate = folder / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which(name)


def gate_status() -> Dict[str, Optional[str]]:
    return {"scicap": find_gate("scicap"), "sciguard": find_gate("sciguard")}


def _not_run(gate: str, reason: str) -> Dict[str, Any]:
    return {"gate": gate, "status": "not_run", "blocking": False, "reason": reason}


def _run_json(cmd: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_S,
        env={**os.environ, "NO_PROXY": "*"},
    )
    if proc.returncode not in (0, 1, 2):
        raise RuntimeError(proc.stderr.strip() or f"exit {proc.returncode}")
    try:
        return json.loads(proc.stdout)
    except ValueError as exc:
        raise RuntimeError(proc.stderr.strip() or "gate printed no JSON") from exc


def check_inputs(draft: Draft) -> Dict[str, Any]:
    if not draft.input_files:
        return {"gate": "inputs", "status": "FAIL", "blocking": True, "reason": "No input file selected."}
    missing = [p for p in draft.input_files if not Path(p).exists()]
    if missing:
        return {
            "gate": "inputs",
            "status": "WARN",
            "blocking": False,
            "reason": f"Not found on this machine (fine if the job runs on a remote backend): {', '.join(missing)}",
        }
    return {"gate": "inputs", "status": "PASS", "blocking": False, "reason": "Input path exists."}


def check_scicap(draft: Draft) -> Dict[str, Any]:
    capability = CAPABILITY_FOR_TARGET.get(draft.target_id)
    if not capability:
        return _not_run("scicap", f"No SciCap capability profile covers {draft.target_id}.")
    binary = find_gate("scicap")
    if not binary:
        return _not_run("scicap", "scicap CLI not installed (set NIR_GATES_BIN).")

    instance = {k: v for k, v in draft.instance.items() if v not in (None, "")}
    instance.setdefault("instance_id", f"assistant.{draft.target_id}")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(instance, fh)
        instance_path = fh.name
    try:
        result = _run_json([binary, "invoke", capability, "--instance", instance_path])
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return _not_run("scicap", f"scicap failed to run: {exc}")
    finally:
        os.unlink(instance_path)

    decision = result.get("decision", "not_run")
    return {
        "gate": "scicap",
        "status": decision,
        "blocking": decision in SCICAP_BLOCKING,
        "reason": result.get("reason", ""),
        "capability": capability,
        "missing": result.get("missing", []),
        "interpretation_limits": result.get("interpretation_limits", []),
    }


def _load_annotation(target_id: str, annotations_dir: Path) -> Optional[Dict[str, Any]]:
    path = annotations_dir / f"{target_id}.yaml"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _bind_annotation(annotation: Dict[str, Any], draft: Draft) -> Dict[str, Any]:
    bound = copy.deepcopy(annotation)
    subject = draft.instance.get("subject")
    if subject:
        for edge in bound.get("edges", []):
            artifact = edge.get("artifact", {})
            if artifact.get("subject") == "{subject}":
                artifact["subject"] = subject
    return bound


def check_sciguard(draft: Draft, annotations_dir: Path = ANNOTATIONS_DIR) -> Dict[str, Any]:
    annotation = _load_annotation(draft.target_id, annotations_dir)
    if annotation is None:
        return _not_run("sciguard", f"No workflow-edge annotation for {draft.target_id}; no spatial edges to check.")
    binary = find_gate("sciguard")
    if not binary:
        return _not_run("sciguard", "sciguard CLI not installed (set NIR_GATES_BIN).")

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        yaml.safe_dump(_bind_annotation(annotation, draft), fh, sort_keys=False)
        workflow_path = fh.name
    try:
        result = _run_json([binary, "validate", workflow_path])
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return _not_run("sciguard", f"sciguard failed to run: {exc}")
    finally:
        os.unlink(workflow_path)

    edges = result.get("edges", [])
    failing = [e for e in edges if e.get("status") in SCIGUARD_BLOCKING]
    statuses = {e.get("status") for e in edges}
    if failing:
        status = "FAIL"
    elif statuses & {"UNKNOWN", "NEEDS_REVIEW"}:
        status = "NEEDS_REVIEW" if "NEEDS_REVIEW" in statuses else "UNKNOWN"
    elif edges:
        status = "PASS"
    else:
        status = "UNKNOWN"
    reason = "; ".join(f"{e.get('rule')}: {e.get('reason')}" for e in (failing or edges)[:3])
    return {
        "gate": "sciguard",
        "status": status,
        "blocking": status in SCIGUARD_BLOCKING,
        "reason": reason,
        "graph_status": result.get("graph_status"),
        "rules_not_run": result.get("rules_not_run", []),
        "edges": edges,
    }


def run_checks(draft: Draft, annotations_dir: Path = ANNOTATIONS_DIR) -> List[Dict[str, Any]]:
    return [
        check_inputs(draft),
        check_scicap(draft),
        check_sciguard(draft, annotations_dir),
    ]


def is_blocked(checks: List[Dict[str, Any]]) -> bool:
    return any(c.get("blocking") for c in checks)
