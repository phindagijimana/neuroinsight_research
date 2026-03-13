# Desktop Packaging Ops

This directory contains packaging/release utilities for NIR Desktop.

## Phase 5 Operations Kit

- `PILOT_CHECKLIST.md` - pilot scope and pass/fail checklist
- `UAT_REPORT_TEMPLATE.md` - structured UAT reporting template
- `SUPPORT_RUNBOOK.md` - support SOP and triage guidance
- `INCIDENT_WORKFLOW.md` - incident declaration/escalation flow
- `LICENSING_BILLING_PLAYBOOK.md` - licensing operations baseline
- `GO_LIVE_RECOMMENDATION_TEMPLATE.md` - final go-live decision template
- `pilot_smoke_test.sh` - quick pre-pilot validation script

## Linux Packaging

Use:

```bash
./desktop/ops/package_desktop_linux.sh
```

This performs:

- dependency install for `desktop/app`
- desktop source checks
- Linux artifact build (AppImage + deb)
- SHA256 and release metadata generation

Artifacts are written to `desktop/dist/`.

## Pre-Pilot Smoke Validation

Use:

```bash
./desktop/ops/pilot_smoke_test.sh
```

## Metadata and Checksums

`release_metadata.js` generates:

- `desktop-release-metadata.json`
- `desktop-release-sha256.txt`

These are also produced by the GitHub workflow:

- `.github/workflows/desktop_release.yml`
