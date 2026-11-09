"""Opt-in local log of what the user changed before approving a draft.

Written only when the user has turned on "save my edits" in Settings, and only
to a JSONL file in the local data folder. File paths and subject IDs are
dropped; the request text is kept because it is what drafting is evaluated on.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from backend.assistant.drafting import Draft

_DROP_INSTANCE_KEYS = {"path", "subject"}
_lock = threading.Lock()


def _form(draft: Draft) -> Dict[str, Any]:
    return {
        "target_type": draft.target_type,
        "target_id": draft.target_id,
        "parameters": {k: v for k, v in draft.parameters.items() if not str(k).startswith("_") and k != "subject_id"},
        "instance": {k: v for k, v in draft.instance.items() if k not in _DROP_INSTANCE_KEYS},
    }


def edited_fields(original: Dict[str, Any], final: Dict[str, Any]) -> List[str]:
    changed: List[str] = []
    if (original["target_type"], original["target_id"]) != (final["target_type"], final["target_id"]):
        changed.append("target_id")
    for section in ("parameters", "instance"):
        keys = set(original[section]) | set(final[section])
        changed.extend(f"{section}.{k}" for k in sorted(keys) if original[section].get(k) != final[section].get(k))
    return changed


def build_record(original: Optional[Draft], final: Draft, job_id: Optional[str]) -> Dict[str, Any]:
    final_form = _form(final)
    original_form = _form(original) if original else final_form
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request": final.request or (original.request if original else ""),
        "drafted_by": (original or final).drafted_by,
        "proposals": (original or final).proposals,
        "original": original_form,
        "final": final_form,
        "edited_fields": edited_fields(original_form, final_form),
        "job_id": job_id,
    }


def feedback_path(data_dir: str) -> Path:
    return Path(data_dir) / "assistant" / "feedback.jsonl"


def append(record: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def load(path: Path) -> Iterator[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
