# Go-Live Recommendation Template (Phase 5 Exit)

## Release Candidate

- Tag: `unreleased-main`
- Commit: `<fill current commit>`
- Build date: `<fill build date>`
- Target channel: `pilot-desktop`
- Artifact set:
  - Linux: `.AppImage` / `.deb`
  - macOS: `.dmg` / `.zip`
  - Windows: `.exe` (and `.msi` if produced)
  - `desktop-release-metadata.json`
  - `desktop-release-sha256.txt`
  - `desktop-release-metadata-<platform>.json`
  - `desktop-release-sha256-<platform>.txt`

## Pilot Outcome Summary

- Cohort size: (fill after pilot)
- Pilot duration: (fill after pilot)
- Core flow completion rate: (fill after pilot)
- Open critical defects: (fill after pilot)

## Reliability Evidence

- Pilot checklist completion: `desktop/ops/PILOT_CHECKLIST.md` (final state)
- Phase 7 reliability report: `desktop/ops/pilot_reliability_report.json`
- Phase 7 gate output: `node desktop/ops/evaluate_pilot_gate.js ...`
- Connector reliability notes: include Pennsieve browse/transfer outcomes
- Key evidence references:
  - diagnostics bundle samples
  - issue/defect summary for pilot week
  - platform-scoped release metadata/checksum verification

## Operational Readiness

- Support triage process validated during pilot: yes/no
- Incident drill completed during pilot: yes/no
- License operations (import/expiry/renewal path) validated: yes/no
- App lock controls validated (enable/unlock/lock-now/disable): yes/no

## Risks and Mitigations

- Risk: (add top 1-3 risks)
  - Impact:
  - Mitigation:
  - Owner:

## Recommendation

- [ ] Go
- [ ] Conditional Go
- [ ] No Go

Decision rationale:
