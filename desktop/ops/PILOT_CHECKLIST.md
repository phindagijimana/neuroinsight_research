# Phase 5 Pilot Checklist

Use this checklist to run a controlled desktop pilot before broad release.

## Pilot Scope

- Build: `desktop` release candidate from tagged commit
- Target OS: Linux, macOS, Windows (staged cohort rollout allowed)
- Pilot cohort size: 3-10 users
- Pilot duration: 2-4 weeks

## Entry Criteria (must pass before pilot starts)

- [ ] Desktop artifacts built for each pilot target OS
- [ ] Generic metadata/checksum generated (`desktop-release-metadata.json`, `desktop-release-sha256.txt`)
- [ ] Platform metadata/checksum generated (`desktop-release-metadata-<platform>.json`, `desktop-release-sha256-<platform>.txt`)
- [ ] Installer checksum verified with platform-scoped checksum file
- [ ] License validation path tested (valid, invalid, expired)
- [ ] Credential store tested on each pilot target OS
- [ ] Local app lock tested (enable/unlock/lock-now/disable)
- [ ] `./research` baseline regression spot-check passed

## Week 1 Execution Plan

- [ ] Day 1: install, launch, start backend, open NIR
- [ ] Day 2: preflight, diagnostics export, restart loop
- [ ] Day 3: valid/invalid license checks, namespaced vault ops, app lock checks
- [ ] Day 4: Pennsieve connect/browse/small-folder transfer smoke
- [ ] Day 5: support drill, incident drill, go-live draft

## Core User Flows to Validate

- [ ] Launch desktop shell
- [ ] Start backend from desktop
- [ ] Open NIR in same window
- [ ] Stop app services safely
- [ ] Run preflight checks and review warnings
- [ ] Export diagnostics bundle
- [ ] Save/load/delete namespaced secret (`pennsieve.api_key`)
- [ ] Import license file and verify status badge
- [ ] Enable app lock and confirm sensitive actions are gated while locked
- [ ] Unlock app and confirm gated actions recover

## Connector and Reliability Flows

- [ ] Pennsieve connection and browse
- [ ] Transfer small folder (smoke test dataset/folder)
- [ ] Remote/HPC job submission from desktop-launched NIR
- [ ] Progress visibility for running job
- [ ] Graceful error visibility for failed transfer/job

## Supportability and Operations

- [ ] Reproduce one issue from user report using diagnostics bundle
- [ ] Triage severity used consistently (P0/P1/P2/P3)
- [ ] First response SLA respected for tested issues
- [ ] Confirm incident escalation path works (owner + cadence)
- [ ] Confirm rollback path to previous stable desktop release
- [ ] License renew/revoke scenario reviewed for pilot users
- [ ] Verify diagnostics bundle includes desktop log + backend runtime log + celery runtime log

## Exit Criteria (pilot complete)

- [ ] >= 90% of pilot users complete core flows successfully
- [ ] No unresolved P0/P1 defects
- [ ] Known P2/P3 defects documented with owners and ETA
- [ ] Go-live recommendation document completed
- [ ] Phase 7 reliability report completed (`pilot_reliability_report.json`)
- [ ] Phase 7 gate evaluation run (`evaluate_pilot_gate.js`)

## Pilot Evidence Log (fill during pilot)

- Build tag / commit:
- Pilot window:
- Test owner(s):
- Cohort size:
- Core flow completion rate:
- Open defects by severity (P0/P1/P2/P3):
- Connector notes (Pennsieve browse/transfer, HPC submit):
- Platform notes (linux/macos/windows):
