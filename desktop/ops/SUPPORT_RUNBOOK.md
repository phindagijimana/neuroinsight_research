# Desktop Support Runbook (Phase 5)

This runbook defines the support SOP for pilot and early production desktop users.

## Triage Severity

- `P0`: system unavailable, data-loss risk, security incident
- `P1`: core flow blocked, no viable workaround
- `P2`: degraded behavior with workaround
- `P3`: minor UX/docs issue

## Intake Requirements

Collect the following before investigation:

- desktop app version and commit SHA
- host OS version
- exact user action and timestamp
- diagnostics bundle from desktop control center
- relevant backend error text (if available)

## First Response Targets

- `P0`: acknowledge within 30 minutes
- `P1`: acknowledge within 2 hours
- `P2`: acknowledge within 1 business day
- `P3`: acknowledge within 2 business days

## Standard Troubleshooting Sequence

1. Verify version/build checksum against release metadata.
2. Review preflight output for environment issues (Docker, ports, disk).
3. Review diagnostics bundle for backend status and recent desktop logs.
4. Reproduce on maintained Linux baseline if possible.
5. Apply known fix or mitigation and confirm with reporter.

## Common Mitigations

- Port conflict: stop conflicting process, restart desktop backend.
- Disk pressure: clean unused images/artifacts and retry.
- License invalid: verify token structure, signature key, and expiry.
- Vault failures: verify keychain backend availability or fallback status.

## Escalation

Escalate to incident workflow immediately when:

- P0/P1 with multiple users affected
- suspected security exposure
- repeat failure with no mitigation in 4 hours (P1) or 1 hour (P0)

See `desktop/ops/INCIDENT_WORKFLOW.md`.
