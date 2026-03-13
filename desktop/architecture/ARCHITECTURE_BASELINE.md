# Phase 0 Architecture Baseline

This document locks the baseline architecture for NIR Desktop Phase 0.

Scope target: single-user, single-machine desktop mode, reusing existing NIR code paths without changing current CLI-hosted behavior.

## Baseline Principles

- Reuse existing NIR frontend and backend components.
- Keep desktop code isolated under `desktop/`.
- Do not change current `./research` production/development flows for web-hosted usage.
- Ship desktop functionality as additive features.
- Preserve security controls already in NIR and add desktop-specific controls incrementally.

## System Boundaries

## Reused Components

- `frontend/` (React/TypeScript UI and existing API service layer)
- `backend/` (FastAPI endpoints, connectors, workflow execution orchestration)
- existing plugin/workflow definitions under `plugins/` and `workflows/`

## New Desktop Components (Phase Track)

- `desktop/app/` - Electron host shell and desktop process management
- `desktop/architecture/` - architecture and decisions
- `desktop/ops/` - packaging/signing/update scripts

## Runtime Model (Target)

1. Electron shell launches desktop window.
2. Desktop app starts or connects to local NIR backend.
3. Existing frontend UI is rendered in desktop shell.
4. User executes existing NIR workflows/connectors through same backend APIs.

## Non-Goals in Phase 0

- No rewrite of backend or frontend.
- No replacement of current CLI tooling.
- No SaaS multi-tenant architecture changes.
- No broad plugin/workflow behavior changes.

## Compatibility Baseline

- Linux first (primary target for initial desktop stabilization)
- macOS second
- Windows third

## Security Baseline for Single-User Desktop

- no mandatory multi-user login wall for standalone mode
- secure credential storage via OS keychain required in later phase
- signed license token model required before paid distribution
- local logs/support bundles treated as sensitive artifacts

## Integration Constraints

- Any backend API additions must be backward compatible.
- Desktop must tolerate current NIR behavior where app may move to alternate port if default is busy.
- Desktop process manager should not assume exclusive control over all host processes.

## Acceptance for Phase 0 Completion

- Architecture baseline approved.
- Reuse boundaries documented and accepted.
- Support matrix published.
- Risk register created with mitigation owners.
