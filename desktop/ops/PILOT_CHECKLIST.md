# Phase 5 Pilot Checklist

Use this checklist to run a controlled desktop pilot before broad release.

## Pilot Scope

- Build: `desktop` release candidate from tagged commit
- Target OS: Linux first (Ubuntu 22.04+)
- Pilot cohort size: 3-10 users
- Pilot duration: 2-4 weeks

## Entry Criteria (must pass before pilot starts)

- [ ] Desktop artifact built (`.AppImage` and/or `.deb`)
- [ ] `desktop-release-metadata.json` generated
- [ ] `desktop-release-sha256.txt` generated
- [ ] Installer checksum verified by at least one reviewer
- [ ] License validation path tested (valid, invalid, expired)
- [ ] Credential store tested on target Linux environment
- [ ] `./research` baseline regression spot-check passed

## Core User Flows to Validate

- [ ] Launch desktop shell
- [ ] Start backend from desktop
- [ ] Open NIR in same window
- [ ] Stop app services safely
- [ ] Run preflight checks and review warnings
- [ ] Export diagnostics bundle
- [ ] Save/load/delete namespaced secret (`pennsieve.api_key`)
- [ ] Import license file and verify status badge

## Connector and Reliability Flows

- [ ] Pennsieve connection and browse
- [ ] Transfer small folder (smoke test dataset/folder)
- [ ] Remote/HPC job submission from desktop-launched NIR
- [ ] Progress visibility for running job
- [ ] Graceful error visibility for failed transfer/job

## Supportability and Operations

- [ ] Reproduce one issue from user report using diagnostics bundle
- [ ] Follow support runbook to resolution
- [ ] Confirm incident escalation path works (owner + SLA)
- [ ] Confirm rollback path to previous stable desktop release

## Exit Criteria (pilot complete)

- [ ] >= 90% of pilot users complete core flows successfully
- [ ] No unresolved P0/P1 defects
- [ ] Known P2/P3 defects documented with owners and ETA
- [ ] Go-live recommendation document completed
