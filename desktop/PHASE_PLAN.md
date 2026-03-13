# NIR Desktop Implementation Plan

This roadmap is organized in execution phases with clear deliverables and exit criteria.

## Phase 0 - Scope Lock and Architecture Baseline

## Goals

- Finalize desktop target: single-user, single-machine mode first.
- Confirm reuse boundaries for existing frontend/backend.
- Freeze minimum supported OS matrix for v1.

## Deliverables

- approved desktop architecture doc
- support matrix (Linux first, then macOS, then Windows)
- risk register and go/no-go criteria

## Exit Criteria

- architecture and scope approved
- no unresolved critical design questions
- Phase 0 baseline artifacts present under `desktop/architecture/`:
  - `ARCHITECTURE_BASELINE.md`
  - `SUPPORT_MATRIX.md`
  - `RISK_REGISTER.md`
- Phase 0 execution artifacts present under `desktop/ops/`:
  - `PHASE0_BASELINE_FREEZE.md`
  - `FULL_EXPERIENCE_PARITY_CHECKLIST.md`

## Phase 0 Notes (Full-Experience Desktop Track)

- Phase 0 for the full desktop migration is documentation and baseline tagging only.
- No runtime behavior changes are made to NIR in this phase.
- Code changes for decoupling/bundling start in Phase 1.

## Phase 1 - Desktop Scaffold and Runtime Bootstrap

## Goals

- Create Electron shell scaffold and startup orchestration.
- Launch existing NIR UI in desktop window.
- Start/stop backend process from desktop app in local mode.

## Deliverables

- `desktop/app/` scaffold (main, preload, renderer bridge)
- local process manager for backend lifecycle
- basic desktop settings and log output

## Exit Criteria

- app launches successfully
- backend health reachable from desktop shell
- no changes required to existing `./research` workflows

## Phase 2 - Compatibility and Stability Layer

## Goals

- Standardize runtime behavior across Linux/macOS/Windows.
- Add startup preflight checks.
- Add diagnostics for supportability.

## Deliverables

- preflight checks (Docker, ports, disk, keychain availability)
- platform adapters for path/process differences
- support bundle export from desktop app

## Exit Criteria

- consistent startup behavior on supported dev environments
- reproducible troubleshooting flow from diagnostics

## Phase 3 - Licensing and Local Security Controls

## Goals

- Add signed license token validation for paid desktop.
- Secure local credential handling.
- Add optional local app lock controls.

## Deliverables

- license validation flow (signature + expiry + grace window)
- OS keychain storage integration
- clear licensing/expiry UX

## Exit Criteria

- invalid licenses are rejected
- expired behavior matches policy
- no plaintext secret storage

## Phase 4 - Packaging and Distribution

## Goals

- Build one-click installers by OS.
- Add signing and update pipeline.
- Prepare website distribution artifacts.

## Deliverables

- installer artifacts (`.AppImage/.deb`, `.dmg/.pkg`, `.exe/.msi`)
- signed release pipeline
- release metadata and checksum publishing

## Exit Criteria

- install/launch smoke tests pass for target platforms
- signed artifact verification enforced

## Phase 5 - Production Readiness and Pilot

## Goals

- Validate reliability under real workflows/connectors.
- Complete pilot documentation and support runbook.
- Establish commercialization readiness baseline.

## Deliverables

- pilot checklist and UAT report
- support SOP and incident workflow
- billing/licensing operational playbook

## Exit Criteria

- pilot users complete core flows successfully
- operational handoff complete
- go-live recommendation documented

## Phase 6 - Trust and Distribution Hardening

## Goals

- Ship trusted installers for macOS and Windows.
- Add explicit trust verification steps to release automation.
- Publish operator/user guidance for verification workflows.

## Deliverables

- desktop release workflow paths for optional signing secrets
- macOS notarization verification and Windows signature verification in CI
- signing setup + trust verification runbook under `desktop/ops/`
- release notes/checksum verification guidance for operators and users

## Exit Criteria

- signed build path passes when required secrets are configured
- unsigned fallback path still works for internal testing
- platform-scoped checksum and trust verification documentation is complete

## Phase 7 - Pilot Reliability Gate

## Goals

- Convert pilot outcomes into explicit go/no-go release decisions.
- Enforce parity and reliability thresholds across Linux/macOS/Windows.
- Ensure failure-recovery and support readiness before GA cutover.

## Deliverables

- reliability gate criteria document under `desktop/ops/`
- pilot reliability evidence template (structured JSON)
- automated gate evaluator script for go/conditional/no-go recommendation

## Exit Criteria

- pilot reliability report completed with platform evidence
- automated gate result reviewed and captured in go-live recommendation
- unresolved P0/P1 defects blocked from GA advancement

## Execution Rhythm

- Build in 2-week sprints.
- At end of each phase:
  - demo the phase outcomes
  - run regression checks against existing CLI-hosted NIR
  - decide continue, scope adjust, or hold
