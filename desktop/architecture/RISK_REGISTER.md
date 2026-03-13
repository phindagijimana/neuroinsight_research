# Phase 0 Risk Register

Initial risk register for NIR Desktop rollout.

## Legend

- Severity: High / Medium / Low
- Status: Open / Mitigating / Closed

## Risks

| ID | Risk | Severity | Status | Mitigation | Owner |
|---|---|---|---|---|---|
| R-001 | Desktop changes accidentally affect current CLI/web NIR behavior | High | Open | Isolate all desktop code under `desktop/`; require regression checks on existing startup and job flows | Engineering |
| R-002 | Port conflicts cause unpredictable backend launch port | High | Open | Add desktop port discovery and explicit UI display of active port; add restart fallback logic | Engineering |
| R-003 | Cross-platform runtime drift causes inconsistent behavior | High | Open | Standardize backend runtime with Docker where possible; define support matrix and platform gates | Engineering |
| R-004 | Large installer and dependency footprint degrades adoption | Medium | Open | Minimize bundled assets; phase optimization after baseline stability | Product/Engineering |
| R-005 | Credential leakage risk on desktop endpoints | High | Open | Use OS keychain; avoid plaintext secret files; redact sensitive logs | Security/Engineering |
| R-006 | License bypass or tampering in paid desktop mode | High | Open | Use signed license tokens with server-held private keys and client verification | Security/Engineering |
| R-007 | Slow Pennsieve browsing or navigation regressions impact UX | Medium | Mitigating | Keep pagination + root filtering + caching; add UI-level loading improvements and telemetry | Engineering |
| R-008 | macOS signing/notarization and Windows signing delays release | Medium | Open | Start signing pipeline design early; test with staging certs | Ops/Engineering |
| R-009 | Support burden increases due to endpoint-specific issues | Medium | Open | One-click diagnostics bundle; standardized error taxonomy; support runbook | Support/Engineering |
| R-010 | Ambiguous single-user vs managed-mode security expectations | Medium | Open | Explicit mode labeling and documentation; publish shared responsibility notes | Product/Security |

## Phase 0 Action Items

- [ ] assign named owners for each risk
- [ ] set target mitigation date per high-severity risk
- [ ] define escalation path for release-blocking risks
