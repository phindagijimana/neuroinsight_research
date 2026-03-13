# NIR Licensing Design

This document defines the recommended licensing model for the paid NIR desktop client, including license format, issuance service, validation flow, and security controls.

## Objectives

- Enable paid distribution of NIR desktop.
- Support expiring licenses (for example, 90-day terms).
- Prevent tampering with license files.
- Support institutional/offline-friendly workflows.
- Keep licensing secure and operationally manageable.

## Key Recommendation

Use a signed license token file (optionally named `nir_license.txt`), not an unsigned editable text file.

- A user may open/edit the file, but edits must invalidate the signature.
- License validity is determined by signature verification plus policy checks.

## License File Format

The license file can be plain text containing a structured payload and a signature.

Suggested structure:

1. payload (JSON)
2. signature metadata (`alg`, `kid`)
3. signature value (base64url)

## Suggested Claims

- `license_id`: unique license identifier
- `organization_id`: customer organization
- `plan_tier`: trial/pro/enterprise
- `issued_at`: UTC timestamp
- `expires_at`: UTC timestamp
- `features`: enabled capabilities
  - connector entitlements
  - workflow entitlements
  - transfer limits (if any)
- `seat_limit`: optional seat/device count
- `offline_grace_days`: allowed offline duration
- `issuer`: issuing authority
- `kid`: signing key ID

## Example Payload (Illustrative)

```json
{
  "license_id": "lic_01JXYZ...",
  "organization_id": "org_neuro_lab_001",
  "plan_tier": "professional",
  "issued_at": "2026-03-01T00:00:00Z",
  "expires_at": "2026-05-30T23:59:59Z",
  "features": [
    "connector.hpc",
    "connector.pennsieve",
    "workflow.diffusion_full",
    "workflow.fmri_full"
  ],
  "seat_limit": 10,
  "offline_grace_days": 7,
  "issuer": "nir-license-service",
  "kid": "ed25519-2026-q1"
}
```

## Signing and Cryptography

Recommended:

- Signature algorithm: Ed25519
- Private key: server-side only (KMS/HSM protected)
- Public key: embedded in desktop app (or fetched securely with pinning)

Do not:

- embed private signing key in client
- accept unsigned licenses
- trust client-side generated licenses

## License Issuance Service

The issuance service should be an independent backend component or a protected module in the existing NIR backend.

### Responsibilities

- create, sign, renew, revoke licenses
- persist issuance history and audit trails
- expose validation/revocation endpoints
- support key rotation (`kid`)

### Minimal Data Model

- `customers`
- `licenses`
- `license_activations` (optional)
- `license_revocations`
- `audit_events`

### Minimal API Surface

- `POST /licenses/issue`
- `POST /licenses/renew`
- `POST /licenses/revoke`
- `GET /licenses/{license_id}`
- `POST /licenses/validate` (optional online validation)
- `GET /licenses/revocations` (or delta endpoint)

## Desktop Validation Flow

1. User imports license file (or logs in and fetches it).
2. App parses payload/signature.
3. App verifies signature using public key and `kid`.
4. App checks:
   - current time within validity window
   - feature entitlements
   - seat/device policy (if enabled)
   - revocation status (when online)
5. App stores activation state in secure local storage.

If invalid:

- Signature mismatch: reject immediately.
- Expired: enter grace mode or limited mode by policy.
- Revoked: deactivate features after revocation check.

## Offline and Grace Behavior

Recommended policy:

- Allow offline operation for a short grace window (for example, 7 days).
- Require periodic online revalidation when network is available.
- Display clear expiry and grace countdown in UI.

This balances institutional reliability with commercial enforcement.

## Seat and Device Policy (Optional)

For paid tiers, you may enforce:

- max activated devices per organization/license
- soft overage warning before hard block
- admin-managed deactivation of old devices

Store a privacy-safe device fingerprint (not raw hardware identifiers in logs).

## Security Controls

## Issuance Service Security

- SSO + MFA for license admins
- RBAC for issue/renew/revoke actions
- immutable audit log for all license events
- rate limiting and abuse detection
- strict secret management and key rotation schedule

## Client Security

- signed app binaries
- signed auto-updates
- secure keychain storage for credentials and activation metadata
- no plaintext secrets in config files

## Operational Policies

- publish licensing terms and renewal rules
- define support process for expiration lockouts
- provide emergency extension workflow (controlled and audited)
- maintain revocation SLAs

## Suggested Commercial Defaults

- Trial: 30-90 days, limited features
- Professional: 90-day or annual terms, standard connector/workflow set
- Enterprise: custom term, SSO options, advanced audit/policy controls

## Rollout Plan

## Phase 1: Internal Licensing Foundations

- implement signed token generation
- implement client-side verification
- add expiry warnings and limited mode behavior

## Phase 2: Customer Licensing Operations

- admin issuance portal
- renewal and revocation workflows
- audit and reporting

## Phase 3: Mature Commercial Controls

- automated billing integration
- seat/device lifecycle management
- self-service customer portal for downloads and renewals

## Implementation Checklist

- [ ] Define final token schema and claims
- [ ] Implement signing in issuance service
- [ ] Implement verification in desktop client
- [ ] Add key rotation with `kid`
- [ ] Add revocation endpoint and client checks
- [ ] Add expiry/grace UX in client
- [ ] Add audit trails for issuance operations
- [ ] Publish licensing policy and support SOP

## Notes

- The license file can be a `.txt`, but integrity must come from digital signatures.
- Keep policy decisions server-authoritative where possible.
- For sensitive-data institutions, pair licensing with strong security documentation and transparent data-handling policies.
