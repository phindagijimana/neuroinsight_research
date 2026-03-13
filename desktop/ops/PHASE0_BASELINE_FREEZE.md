# Phase 0 Baseline Freeze

This document captures the non-invasive baseline for migrating from the current
desktop wrapper to a full NIR desktop experience.

## Intent

- freeze scope before implementation work
- preserve current NIR behavior while desktop evolves
- define parity gates that must pass before cutover

## Baseline Marker

- baseline tag: `desktop-wrapper-baseline`
- baseline commit: `7d0c3e0`
- baseline date: `2026-03-13` (UTC)

## Scope Lock (Phase 0)

- In scope:
  - architecture baseline and support matrix confirmation
  - risk register confirmation
  - full-experience parity checklist definition
  - acceptance criteria for Phase 1 kickoff
- Out of scope:
  - runtime process changes
  - backend/frontend refactors
  - packaging/signing changes

## Guardrails

- no changes to NIR runtime semantics in Phase 0
- desktop work remains additive and isolated
- any migration task must include rollback notes

## Phase 1 Entry Criteria

- [ ] Baseline tag created and pushed
- [ ] `desktop/architecture/` baseline docs reviewed
- [ ] parity checklist approved by product/engineering
- [ ] rollback and regression strategy documented
