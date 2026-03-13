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
node desktop/ops/evaluate_pilot_gate.js desktop/ops/pilot_reliability_report.json
```

The script exits non-zero for `no_go`.
