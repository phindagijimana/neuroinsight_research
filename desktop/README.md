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

## Guardrails

- Keep existing CLI-hosted NIR behavior unchanged.
- Desktop changes should be additive and isolated.
- Use compatibility gates so Linux/macOS/Windows can be rolled out safely.
