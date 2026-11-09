"""Assistant routes: draft, re-check, explain, and human approval.

Draft/recheck/explain are read-only. ``approve`` is the only route that can
start a job: it re-runs every check on the (possibly user-edited) draft,
refuses with 409 if any check blocks, and otherwise calls the same submit
function the manual job form uses.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.assistant import draft_job, explain_target, gate_status, run_checks
from backend.assistant import feedback
from backend.assistant.catalog import available_targets, registry_catalog
from backend.assistant.drafting import Draft
from backend.assistant.gates import is_blocked
from backend.assistant.model import make_proposer, model_status
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.plugin_registry import get_plugin_workflow_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class DraftRequest(BaseModel):
    request: str = ""
    input_path: str = ""
    instance_overrides: Optional[Dict[str, Any]] = None


class DraftBody(BaseModel):
    draft: Dict[str, Any]


class ApproveBody(BaseModel):
    draft: Dict[str, Any]
    approved_by: str = "local-user"
    custom_resources: Optional[Dict[str, Any]] = None
    # The draft as the assistant first proposed it, and the user's opt-in to
    # keep a local record of what they changed.
    original_draft: Optional[Dict[str, Any]] = None
    save_feedback: bool = False


def _require_enabled() -> None:
    if not get_settings().assistant_enabled:
        raise HTTPException(status_code=404, detail="Assistant is turned off")


def _available() -> Dict[str, set]:
    return available_targets(get_plugin_workflow_registry())


def _parse_draft(data: Dict[str, Any]) -> Draft:
    draft = Draft.from_dict(data)
    if draft.target_type not in ("plugin", "workflow"):
        raise HTTPException(status_code=400, detail="target_type must be 'plugin' or 'workflow'")
    if draft.target_id not in _available()[draft.target_type]:
        raise HTTPException(status_code=404, detail=f"{draft.target_type} '{draft.target_id}' not found")
    return draft


def _response(draft: Draft) -> Dict[str, Any]:
    checks = run_checks(draft)
    return {"draft": draft.to_dict(), "checks": checks, "blocked": is_blocked(checks)}


@router.get("/status")
def assistant_status() -> Dict[str, Any]:
    settings = get_settings()
    model = model_status()
    return {
        "enabled": settings.assistant_enabled,
        "mode": "local_model" if model["backend"] and model["name"] else "rules",
        "model": model,
        "model_api": None,
        "gates": gate_status(),
        "can_submit": False,
        "note": "The assistant drafts and checks. Only a human Approve submits a job.",
    }


@router.post("/draft")
def assistant_draft(body: DraftRequest) -> Dict[str, Any]:
    _require_enabled()
    proposer = make_proposer()
    catalog = registry_catalog(get_plugin_workflow_registry()) if proposer else None
    draft = draft_job(
        body.request, body.input_path, _available(), body.instance_overrides,
        proposer=proposer, catalog=catalog,
    )
    return _response(draft)


@router.post("/recheck")
def assistant_recheck(body: DraftBody) -> Dict[str, Any]:
    _require_enabled()
    return _response(_parse_draft(body.draft))


@router.get("/explain/{target_type}/{target_id}")
def assistant_explain(target_type: str, target_id: str) -> Dict[str, Any]:
    _require_enabled()
    from backend.main import FS_LICENSE_PLUGINS

    registry = get_plugin_workflow_registry()
    if target_type == "workflow":
        wf = registry.get_workflow(target_id)
        plugin_ids = [s.uses for s in wf.steps] if wf else []
    else:
        plugin_ids = [target_id]
    needs_fs = any(pid in FS_LICENSE_PLUGINS for pid in plugin_ids)
    info = explain_target(registry, target_type, target_id, needs_fs_license=needs_fs)
    if info is None:
        raise HTTPException(status_code=404, detail=f"{target_type} '{target_id}' not found")
    return info


def _record(event: str, **details: Any) -> None:
    try:
        from backend.core.audit import audit_log

        audit_log.record(event, **details)
    except Exception as exc:
        logger.debug("Audit log unavailable: %s", exc)


@router.post("/approve")
def assistant_approve(body: ApproveBody, db: Session = Depends(get_db)) -> Dict[str, Any]:
    _require_enabled()
    draft = _parse_draft(body.draft)
    checks = run_checks(draft)
    summary: List[Dict[str, Any]] = [
        {"gate": c["gate"], "status": c["status"], "blocking": c["blocking"]} for c in checks
    ]
    if is_blocked(checks):
        _record(
            "assistant_approve_refused",
            target_id=draft.target_id,
            approved_by=body.approved_by,
            checks=summary,
        )
        raise HTTPException(
            status_code=409,
            detail={"message": "Checks block this job. Fix the draft and re-check.", "checks": checks},
        )

    from backend.main import (
        PluginJobSubmitRequest,
        WorkflowJobSubmitRequest,
        submit_plugin_job,
        submit_workflow_job,
    )

    params = dict(draft.parameters)
    params["_proposer"] = "assistant"
    params["_drafted_by"] = draft.drafted_by
    params["_drafted_by"] = draft.drafted_by
    params["_approved_by"] = body.approved_by
    params["_assistant_checks"] = summary

    if draft.target_type == "workflow":
        result = submit_workflow_job(
            draft.target_id,
            WorkflowJobSubmitRequest(
                input_files=draft.input_files,
                parameters=params,
                custom_resources=body.custom_resources,
            ),
            db,
        )
    else:
        result = submit_plugin_job(
            draft.target_id,
            PluginJobSubmitRequest(
                input_files=draft.input_files,
                parameters=params,
                custom_resources=body.custom_resources,
            ),
            db,
        )

    _record(
        "assistant_draft_approved",
        job_id=result.get("job_id"),
        target_id=draft.target_id,
        proposer="assistant",
        drafted_by=draft.drafted_by,
        approved_by=body.approved_by,
        checks=summary,
    )

    if body.save_feedback:
        try:
            original = Draft.from_dict(body.original_draft) if body.original_draft else None
            feedback.append(
                feedback.build_record(original, draft, result.get("job_id")),
                feedback.feedback_path(get_settings().data_dir),
            )
        except Exception as exc:
            logger.warning("Could not save assistant feedback: %s", exc)
    return {**result, "proposer": "assistant", "approved_by": body.approved_by, "checks": checks}
