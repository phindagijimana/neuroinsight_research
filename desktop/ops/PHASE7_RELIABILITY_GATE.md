# Phase 7 Pilot Reliability Gate

Use this gate after pilot execution to decide whether desktop can advance to GA
cutover planning.

## Inputs

- Final pilot checklist state: `desktop/ops/PILOT_CHECKLIST.md`
- Pilot go-live decision draft: `desktop/ops/GO_LIVE_RECOMMENDATION_TEMPLATE.md`
- Reliability evidence JSON: `desktop/ops/pilot_reliability_report.json`
- Parity criteria: `desktop/ops/FULL_EXPERIENCE_PARITY_CHECKLIST.md`

## Required reliability thresholds

- Core flow completion rate >= 90%
- Parity checklist completion >= 90%
- No unresolved P0 defects
- No unresolved P1 defects
- Crash-free launch rate >= 98%
- Support SLA on pilot incidents >= 90%

## Required evidence coverage

- Linux pilot evidence present
- macOS pilot evidence present
- Windows pilot evidence present
- At least one diagnostics bundle sample per OS
- Failure-recovery drill validated per OS

## Decision policy

- `go`: all thresholds/evidence pass
- `conditional_go`: only non-critical gaps remain (typically P2/P3), each with
  owner + ETA + mitigation
- `no_go`: any critical threshold miss or unresolved P0/P1

## CLI gate check

```bash
# human-readable
node desktop/ops/evaluate_pilot_gate.js desktop/ops/pilot_reliability_report.json
# machine-readable (for capture/automation)
node desktop/ops/evaluate_pilot_gate.js desktop/ops/pilot_reliability_report.json --json
```

The script exits non-zero for `no_go`.

## Capturing the decision into the go-live record

```bash
node desktop/ops/capture_gate_result.js desktop/ops/pilot_reliability_report.json
```

Writes `pilot_gate_result.json` (machine-readable) and `GO_LIVE_DECISION.md`
(a stamp to paste into `GO_LIVE_RECOMMENDATION_TEMPLATE.md` under "Reliability
Evidence"). Set `NIR_GATE_TIMESTAMP` to record the evaluation time. Exits
non-zero on `no_go`.

## CI enforcement (blocks GA)

`.github/workflows/desktop_reliability_gate.yml` runs the gate automatically.
Until a real `pilot_reliability_report.json` is committed it skips cleanly; once
present it fails the check on `no_go`, so **unresolved P0/P1 defects block GA
advancement**. The decision artifacts are uploaded for the go-live review.

## How to produce the report

1. Copy `pilot_reliability_report.template.json` to
   `pilot_reliability_report.json` and fill it with real pilot evidence
   (per-OS evidence, diagnostics samples, failure-recovery drill, defect counts).
2. Run the gate / capture commands above.
3. Paste `GO_LIVE_DECISION.md` into the go-live recommendation and attach
   `pilot_gate_result.json`.
