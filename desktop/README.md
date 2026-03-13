# NIR Desktop App

This folder contains the desktop implementation track for NeuroInsight Research.

The desktop app is designed as a native shell around existing NIR components:

- frontend UI reuse (React/TypeScript)
- backend/control-plane reuse (FastAPI/Celery/connectors)
- desktop-native capabilities (installer, keychain, license, updates)

## Proposed Structure

- `desktop/README.md` - desktop scope and structure
- `desktop/PHASE_PLAN.md` - phased implementation roadmap
- `desktop/architecture/` - architecture notes and diagrams
- `desktop/app/` - Electron shell source (main/preload/desktop services)
- `desktop/ops/` - packaging, signing, and release scripts

## Current Status

- Phase 0: completed (baseline docs under `desktop/architecture/`)
- Phase 1: scaffold created under `desktop/app/`
- Phase 2: preflight and diagnostics scaffold added
- Phase 3/3.5: license and vault hardening scaffold added
- Phase 4: multi-platform packaging/release scaffold added
  - `desktop/app/package.json` build targets/scripts
  - `desktop/ops/package_desktop_linux.sh`
  - `desktop/ops/release_metadata.js`
  - `desktop/ops/verify_release_artifacts.js`
  - `.github/workflows/desktop_release.yml`
  - `.github/workflows/desktop_release_multi.yml`
- Phase 5: production-readiness and pilot ops kit added
  - `desktop/ops/PILOT_CHECKLIST.md`
  - `desktop/ops/GO_LIVE_RECOMMENDATION_TEMPLATE.md`
  - `desktop/ops/pilot_smoke_test.sh`
- Phase 6: trust and distribution hardening scaffold added
  - CI signing-mode detection and verification hooks (macOS/Windows)
  - `desktop/ops/SIGNING_AND_TRUST.md`
- Phase 7: pilot reliability gate scaffold added
  - `desktop/ops/PHASE7_RELIABILITY_GATE.md`
  - `desktop/ops/pilot_reliability_report.template.json`
  - `desktop/ops/evaluate_pilot_gate.js`

## Guardrails

- Keep existing CLI-hosted NIR behavior unchanged.
- Desktop changes should be additive and isolated.
- Use compatibility gates so Linux/macOS/Windows can be rolled out safely.
