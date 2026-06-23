# NIR Desktop — Licensing & Billing Operations Playbook (Phase 5)

Operational playbook for issuing, renewing, and revoking NIR Desktop licenses.
It documents the **current** desktop validation behavior (Phase 3) and the
business process around it. This is the "billing/licensing operational playbook"
referenced by `PILOT_CHECKLIST.md`.

## 1. License token model (what the desktop validates)

A license is a signed JSON token: `{ "payload": {...}, "signature": "<base64>" }`.
The signature is **Ed25519** over `JSON.stringify(payload)`, verified in the app
with an embedded/configured public key (`src/licenseManager.js`).

Required payload claims (schema-enforced on import):

| Claim | Type | Notes |
|---|---|---|
| `license_id` | string | Unique per issued license |
| `organization_id` | string | Customer/org identity |
| `plan_tier` | string | `trial` / `professional` / `enterprise` |
| `issued_at` | ISO date | Must be < `expires_at` |
| `expires_at` | ISO date | Drives expiry + grace |
| `features` | string[] | Entitlements (connectors/transfers/…) |
| `offline_grace_days` | int ≥ 0 (optional) | Grace past expiry for offline use |
| `seat_limit` | int ≥ 1 (optional) | Seats for the org |

Invalid format, bad/tampered signature, schema violations, or expiry-beyond-grace
are **rejected at import** and the badge shows an invalid/limited state.

## 2. Verification key configuration

The desktop loads the public key from (first match wins):
1. env `NIR_DESKTOP_LICENSE_PUBLIC_KEY` (PEM, `\n` allowed),
2. `desktop/app/config/license_public_key.pem`,
3. `<userData>/nir-desktop/license_public_key.pem`.

- **No key configured → "unlicensed/community" mode → full features** (used for
  dev and unlicensed builds; nothing is gated).
- **Key configured →** the token is enforced (see §4).

The **private** signing key never ships and is held only by the license service.
Rotate by shipping a new public key in a desktop release; re-issue tokens signed
with the matching new private key.

## 3. Plan tiers (commercial)

| Tier | Intended use | Typical `features` |
|---|---|---|
| `trial` | 30–90 day evaluation | core connectors, limited seats |
| `professional` | Paid desktop orchestration | standard connectors + transfers |
| `enterprise` | Org-wide | SSO/advanced audit/policy, SLA support |

Tier and `features` are advisory metadata the product can branch on; billing is
managed by the license service, not the client.

## 4. Enforcement modes (desktop behavior)

`licenseManager.getEnforcement()` returns the active mode:

| Mode | Condition | Effect |
|---|---|---|
| `unlicensed` | no public key | Full features (community/dev) |
| `active` | valid, not near expiry | Full features |
| `grace` | expired but within `offline_grace_days` | Full features + "renew soon" warning |
| `expired` / `missing` | key configured, no valid token | **Limited mode** — Open-UI disabled |

The renderer also surfaces an **expiring-soon** warning at ≤14 days remaining.

## 5. Lifecycle operations

### Issue
1. Collect org, tier, seats, term, entitlements.
2. License service builds the payload, signs it (Ed25519), emits the token JSON.
3. Deliver as `nir_license.txt` (auto-imported if placed next to the app binary)
   or via **License → Import file / Paste token** in the app.

### Renew
1. Issue a new token with a later `expires_at` (same `license_id` or a new one
   per policy).
2. User imports it; the new valid token supersedes the old. If the user is in
   **grace**, importing restores `active`.
3. Operational trigger: act on the **expiring-soon** (≤14d) signal proactively.

### Revoke
1. Mark `license_id` revoked in the license service and stop renewals.
2. Current client behavior: revocation takes effect at **expiry** (offline,
   file-based validation — there is no online revocation check yet).
   *Roadmap:* online revocation-list checks + periodic re-validation
   (see `../../EEG_future.md`-style roadmap and the desktop security doc).
3. For immediate cutoff before expiry, coordinate with the customer (the desktop
   is a thin client; data/compute access is also governed by connector/SSO
   credentials, which should be rotated/revoked in parallel).

### Expiry handling (what the user experiences)
- **Within grace:** keeps working, shown a renew warning + days remaining.
- **Beyond grace (key configured):** limited mode — cannot open the NIR UI;
  must import a valid token. Support steps in `SUPPORT_SOP.md`.

## 6. Pilot guidance

- Issue short-term `trial` tokens with a small `offline_grace_days` (e.g., 7) so
  the grace path is exercised during the pilot.
- Validate all three paths in the pilot (checklist item): **valid**, **invalid**,
  **expired** — and the **grace** transition.
- Keep the signing private key out of the repo and out of CI logs.

## 7. Operational checklist

- [ ] Public key shipped in the pilot build (or intentionally unlicensed)
- [ ] Token issuance runbook owner named
- [ ] Renewal trigger wired to the expiring-soon signal
- [ ] Revoke + credential-rotation steps rehearsed
- [ ] Trial→paid upgrade path validated (import new token, mode → active)
