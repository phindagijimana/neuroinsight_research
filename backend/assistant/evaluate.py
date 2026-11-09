"""Compare keyword rules and the optional local model on recorded requests.

Usage:
    python -m backend.assistant.evaluate FILE.jsonl|FILE.yaml [--model] [--out report.json]

Each record needs ``request`` and ``final.target_id`` (what the user approved).
The feedback log written on approval has this shape; so does the authored
smoke set ``backend/assistant/eval_cases.yaml``. Scores are computed here from
the inputs given; nothing is assumed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import yaml

from backend.assistant.catalog import available_targets, registry_catalog
from backend.assistant.drafting import draft_job
from backend.assistant.feedback import load
from backend.assistant.model import make_proposer


def load_records(path: Path) -> List[Dict[str, Any]]:
    if path.suffix in (".yaml", ".yml"):
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return list(data.get("cases", []))
    return list(load(path))


def _score(drafter: str, records: Iterable[Dict[str, Any]], draft_fn: Callable[[str], Any]) -> Dict[str, Any]:
    rows = []
    for rec in records:
        expected = rec["final"]
        draft = draft_fn(rec["request"])
        expected_params = dict(expected.get("parameters") or {})
        rows.append({
            "request": rec["request"],
            "expected": expected["target_id"],
            "got": draft.target_id,
            "target_match": draft.target_id == expected["target_id"],
            "params_match": all(draft.parameters.get(k) == v for k, v in expected_params.items()),
            "drafted_by": draft.drafted_by,
            "fallback_reason": draft.fallback_reason,
            "extra_params": sorted(set(draft.parameters) - set(expected_params) - {"subject_id"}),
        })
    n = len(rows)
    return {
        "drafter": drafter,
        "n": n,
        "target_match": sum(r["target_match"] for r in rows),
        "target_and_params_match": sum(r["target_match"] and r["params_match"] for r in rows),
        "fell_back_to_rules": sum(r["drafted_by"] != "model" for r in rows) if drafter == "model" else None,
        "rows": rows,
    }


def evaluate(records: List[Dict[str, Any]], registry: Any, proposer: Optional[Callable] = None) -> Dict[str, Any]:
    available = available_targets(registry)
    report = {"rules": _score("rules", records, lambda req: draft_job(req, "", available))}
    if proposer is not None:
        catalog = registry_catalog(registry)
        report["model"] = _score(
            "model", records, lambda req: draft_job(req, "", available, proposer=proposer, catalog=catalog)
        )
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("records", type=Path)
    parser.add_argument("--model", action="store_true", help="also score the configured local model")
    parser.add_argument("--out", type=Path, help="write the full per-request report as JSON")
    args = parser.parse_args(argv)

    from backend.core.plugin_registry import get_plugin_workflow_registry

    proposer = make_proposer() if args.model else None
    if args.model and proposer is None:
        print("No local model configured (ASSISTANT_MODEL_BACKEND / ASSISTANT_MODEL_NAME).", file=sys.stderr)
        return 2

    report = evaluate(load_records(args.records), get_plugin_workflow_registry(), proposer)
    for name, part in report.items():
        line = f"{name}: target {part['target_match']}/{part['n']}, target+settings {part['target_and_params_match']}/{part['n']}"
        if part.get("fell_back_to_rules") is not None:
            line += f", fell back to rules {part['fell_back_to_rules']}/{part['n']}"
        print(line)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
