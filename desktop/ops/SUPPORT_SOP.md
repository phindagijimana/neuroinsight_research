# NIR Desktop — Support SOP & Incident Workflow (Phase 5)

Operational runbook for supporting NIR Desktop during pilot and early GA. This is
the "operational handoff" artifact referenced by `PILOT_CHECKLIST.md` and
`GO_LIVE_RECOMMENDATION_TEMPLATE.md`.

## 1. Severity definitions

Severity drives first-response SLA and escalation. These match the `p0..p3`
fields consumed by `evaluate_pilot_gate.js`.

| Severity | Definition | Examples |
|---|---|---|
| **P0** | Critical: app unusable for all/most users, data loss, or security exposure | App won't launch on a supported OS; credential leak; backend cannot start for everyone |
| **P1** | High: core flow broken, no reasonable workaround | Cannot start backend; Open-UI fails after healthy backend; license validation wrongly rejects valid tokens |
| **P2** | Medium: feature degraded or broken with a workaround | Diagnostics export fails but logs reachable manually; preflight false-warning |
| **P3** | Low: cosmetic / minor | Label/typo; non-blocking UI glitch |

Gate policy: **P0/P1 block go-live**; P2/P3 are allowed with documented owner +
ETA in `conditional_go_notes` (see `PHASE7_RELIABILITY_GATE.md`).

## 2. First-response SLA (pilot)

| Severity | First response | Target mitigation |
|---|---|---|
| P0 | 1 business hour | Same day (workaround or hotfix) |
| P1 | 4 business hours | 2 business days |
| P2 | 1 business day | Next release |
| P3 | 3 business days | Backlog |

`sla_adherence_rate` in the reliability report tracks how often these were met.

## 3. Intake & triage

1. **Collect the diagnostics bundle first.** Ask the user to use
   **Diagnostics → Export bundle → Show in folder** and attach the JSON. It
   contains: desktop settings, backend status, runtime info, preflight results,
   and tails of the desktop / backend / celery logs (no raw imaging data).
2. **Reproduce from the bundle.** Check `nirDesktop.preflight` for blockers
   (Python/Docker), `nirDesktop.status` for backend/celery state, and the log
   tails for stack traces.
3. **Assign severity** from §1 and record owner + timestamp.
4. **Classify area:** launch / backend lifecycle / license / credentials /
   app-lock / connector (Pennsieve/HPC) / packaging.

## 4. Triage decision tree (most common)

- **App won't launch** → confirm OS is supported; check Gatekeeper/SmartScreen
  (unsigned builds during pilot — see `SIGNING_AND_TRUST.md`); get console log.
- **Backend won't start** → preflight `python` blocker? venv present
  (`./research install`)? port conflict (auto-selected; check `runtime.port`)?
- **"Limited mode / cannot open UI"** → license expired beyond grace, or a
  verification key is configured without a valid token → see
  `LICENSING_OPERATIONS.md`.
- **Credential errors** → check vault backend (keychain vs encrypted fallback)
  in the bundle; app lock may be engaged (unlock required for vault ops).
- **Connector failure (Pennsieve/HPC)** → capture the failing step + bundle;
  confirm network/SSH; escalate to platform on-call if backend-side.

## 5. Escalation path

| Stage | Owner | Trigger |
|---|---|---|
| L1 — Support | Pilot support contact | All intake; resolves P2/P3 with known fixes |
| L2 — Desktop eng | Desktop maintainer | P0/P1, or any defect needing a code change |
| L3 — Platform eng | Backend/platform on-call | Backend/connector/data-plane issues |

Escalate P0 immediately to L2 **and** L3; open an incident (below). Record
owner + cadence in the pilot evidence log.

## 6. Incident workflow (P0/P1)

1. **Declare** the incident; name an incident owner.
2. **Communicate** status to the pilot cohort (initial + at each SLA checkpoint).
3. **Mitigate** — prefer rollback (§7) over hotfix under time pressure.
4. **Resolve & verify** with the reporter's diagnostics bundle.
5. **Post-incident review** within 2 business days: timeline, root cause,
   corrective actions, owners. File P2/P3 follow-ups.

### Incident drill (run once during pilot — checklist item)
Inject a known failure (e.g., rename the venv so Python preflight fails),
confirm the user sees the blocking banner, support reproduces it from a bundle,
and the documented fix restores service. Record pass/fail in the reliability
report's `failure_recovery_drill_passed`.

## 7. Rollback path

NIR Desktop is a thin client; rollback = reinstall the previous signed/verified
release.

1. Identify last-known-good build tag from `desktop-release-metadata.json`.
2. Provide the prior installer + its platform-scoped checksum
   (`desktop-release-sha256-<platform>.txt`); user verifies before install.
3. Reinstall over the current version (settings/state persist in the OS app-data
   dir; no migration needed for a downgrade within a minor series).
4. Confirm launch + backend health; record in the incident log.

## 8. Operational handoff checklist

- [ ] Support contact + L2/L3 owners named and reachable
- [ ] Severity + SLA table shared with the cohort
- [ ] Diagnostics-bundle request templated in the support channel
- [ ] Incident drill executed and recorded
- [ ] Rollback path tested at least once
- [ ] `LICENSING_OPERATIONS.md` reviewed for renew/revoke handling
