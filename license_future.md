# NIR Desktop Licensing — Deferred for a Future Version

**Status:** Disabled for this version (2026-06-24). The commercial-licensing
feature is **built and present** in the codebase but **hidden / not enforced** —
the desktop runs in permissive "community" mode where all features are available.
This document records what exists, how it's turned off, and how to re-enable it.

This is the licensing counterpart to [`EEG_future.md`](EEG_future.md).

---

## 1. How it's disabled right now

| Layer | State |
|---|---|
| Desktop UI | License card + header badge **hidden** via `LICENSE_ENABLED = false` in `desktop/app/renderer/renderer.js` |
| Enforcement | `licenseManager.getEnforcement()` returns `unlicensed` mode → **full features** (no public key configured) |
| Gating | "Open NIR UI" and all actions are **allowed** (nothing blocked) |
| Code | All licensing code (`licenseManager.js`, IPC, import flows) remains in place — only the UI is hidden |

So today: **no license is required, nothing is gated, and the License UI is not shown.**

### Re-enabling
1. Set `LICENSE_ENABLED = true` in `desktop/app/renderer/renderer.js` (shows the
   License card + badge again).
2. Ship a verification **public key** (see §3). Without a key the app stays in
   `unlicensed` mode regardless.

---

## 2. The token model (what the app validates) — `desktop/app/src/licenseManager.js`

A license is a signed JSON token: `{ "payload": {...}, "signature": "<base64>" }`,
verified with **Ed25519** over `JSON.stringify(payload)` using an embedded/configured
public key.

Required payload claims (schema-enforced on import):

| Claim | Type | Notes |
|---|---|---|
| `license_id` | string | unique per issued license |
| `organization_id` | string | customer/org identity |
| `plan_tier` | string | `trial` / `professional` / `enterprise` |
| `issued_at` | ISO date | must be `< expires_at` |
| `expires_at` | ISO date | drives expiry + grace |
| `features` | string[] | entitlements |
| `offline_grace_days` | int ≥ 0 (optional) | grace past expiry for offline use |
| `seat_limit` | int ≥ 1 (optional) | seats for the org |

Invalid format, bad/tampered signature, schema violations, or expiry-beyond-grace
are **rejected at import**.

## 3. Verification key configuration

The desktop loads the public key from (first match wins):
1. env `NIR_DESKTOP_LICENSE_PUBLIC_KEY` (PEM),
2. `desktop/app/config/license_public_key.pem`,
3. `<userData>/nir-desktop/license_public_key.pem`.

The **private** signing key never ships — it lives only in the license service.
An example public key is provided at `desktop/app/config/license_public_key.pem.example`.

## 4. Enforcement modes — `getEnforcement()`

| Mode | Condition | Effect |
|---|---|---|
| `unlicensed` | no public key | **full features** (current default / community) |
| `active` | valid, not near expiry | full features |
| `grace` | expired but within `offline_grace_days` | full features + "renew soon" warning |
| `expired` / `missing` | key configured, no valid token | **limited mode** — Open-UI disabled |

A ≤14-day **expiring-soon** warning is also surfaced.

## 5. Verified behavior (already tested)

The licensing logic is implemented and has passing tests (Ed25519 functional test):
- invalid / tampered / expired-beyond-grace → rejected,
- expired-but-in-grace → valid with renew warning,
- credentials stored in the OS keychain with **no plaintext on disk**.

## 6. Operations

The business/lifecycle playbook (issue / renew / revoke / expiry handling, plan
tiers, pilot guidance) is already written at
[`desktop/ops/LICENSING_OPERATIONS.md`](desktop/ops/LICENSING_OPERATIONS.md).

## 7. Roadmap to turn licensing on

- [ ] Decide commercial tiers + entitlements (`features` claim values).
- [ ] Stand up the license-signing service (holds the Ed25519 private key).
- [ ] Ship the public key in the desktop build (config or env).
- [ ] Flip `LICENSE_ENABLED = true`.
- [ ] Add online revocation-list checks + periodic re-validation (currently
      offline/file-based only).
- [ ] Wire trial → paid upgrade UX and renewal reminders.
- [ ] Per-org / per-deployment enforcement policy.

## 8. Files

- `desktop/app/src/licenseManager.js` — token validation, grace, enforcement
- `desktop/app/renderer/` — License card/badge (gated by `LICENSE_ENABLED`)
- `desktop/app/config/license_public_key.pem.example`
- `desktop/ops/LICENSING_OPERATIONS.md` — operational playbook
