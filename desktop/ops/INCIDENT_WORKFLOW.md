# Incident Workflow (Phase 5)

## Trigger Conditions

- `P0` or widespread `P1`
- security/privacy concern
- release integrity concern (artifact mismatch, checksum failure)

## Workflow

1. **Declare incident**
   - Open incident ticket/channel
   - Assign incident commander and communication owner
2. **Stabilize**
   - Pause new rollout
   - Provide temporary mitigation (rollback or disable affected path)
3. **Investigate**
   - Use diagnostics bundle and logs
   - Identify blast radius and affected versions
4. **Recover**
   - Ship hotfix or rollback release
   - Confirm service health with pilot users
5. **Close**
   - Publish incident summary
   - Capture follow-up actions with owners and due dates

## Rollback Guidance

- Revert to previous known-good desktop artifact set.
- Verify checksums and metadata before redistribution.
- Mark bad release as deprecated in release notes.

## Communication Cadence

- P0: every 30 minutes until stable
- P1: every 2 hours until stable

## Postmortem Minimum Fields

- timeline
- root cause
- contributing factors
- user impact
- corrective actions
