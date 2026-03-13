# NIR Desktop Client App

This document defines the proposed desktop-client model for NeuroInsight Research (NIR), including architecture, security controls, licensing, and commercialization guidance.

## Goals

- Provide a simple desktop orchestration experience for users.
- Keep sensitive neuroimaging data in trusted data and compute environments.
- Support commercial licensing for paid desktop distribution.
- Preserve compatibility with existing NIR workflow and connector behavior.

## Product Positioning

NIR Desktop is a thin orchestration client, not a heavy local-processing product by default.

- Desktop client handles:
  - login and organization context
  - connector setup (HPC, remote server, Pennsieve, XNAT)
  - job submission, status tracking, and transfer management
  - logs and support bundle export
- Data and compute remain on:
  - institutional storage
  - HPC or remote Linux compute
  - approved cloud/object systems

## Architecture (Recommended)

1. Desktop UI shell (Electron or Tauri)
2. Existing NIR backend API as control plane
3. Existing NIR execution/connectors layer
4. Secure storage for secrets in OS keychain (not plain text files)

### Data Residency Rule

Default policy: desktop client should not persist raw imaging data locally unless explicitly enabled by admins.

## Cross-Platform Compatibility Strategy (Linux/macOS/Windows)

Use a combined model:

- Electron desktop shell for native user experience
- Dockerized NIR backend/services for runtime consistency

This minimizes OS-specific behavior differences while preserving one product experience.

### What We Standardize

- same frontend behavior across all desktop OSes
- same backend/runtime stack in containers
- same API contract and workflow/plugin behavior

### What Remains Platform-Specific

- installer packaging and code-signing
- OS keychain integration
- file path normalization and filesystem permissions
- process lifecycle nuances and local firewall prompts

### Startup Preflight (Desktop)

Desktop app should run checks before enabling full functionality:

- Docker availability and minimum version
- required port availability
- CPU/RAM/disk thresholds
- writable application data directory
- keychain availability

### Support Matrix Policy

Define and publish supported targets, for example:

- Ubuntu LTS
- macOS latest-2 versions
- Windows 11 (and current supported enterprise builds)

Pin minimum Docker engine/desktop versions per OS.

### CI and Release Validation

Run platform-specific pipelines:

- build and package desktop artifacts per OS
- smoke test launch -> backend health -> basic browse/submit flow
- verify signed artifacts and update metadata

### Rollout Order (Recommended)

1. Linux desktop first
2. macOS second (signing/notarization)
3. Windows third (MSI/signing/policy hardening)

### Compatibility Risk Controls

- feature flags for OS-specific limitations
- clear in-app messaging when a feature is unavailable
- one-click support bundle for diagnostics
- centralized error taxonomy for support and QA

## Security Requirements

## Authentication and Access

- SSO/OIDC support for organizations (preferred)
- MFA support for privileged roles
- Role-based permissions for connections, submissions, transfers, and admin actions

## Encryption

- TLS for all client-server/API traffic
- Encrypted secrets at rest via native keychain:
  - macOS Keychain
  - Windows Credential Manager
  - Linux Secret Service/KWallet compatible store

## Endpoint and Runtime Hardening

- Signed desktop binaries and signed auto-updates
- Disable insecure debug features in production builds
- Restrict local logs to avoid PHI leakage
- Add configurable inactivity lock and session timeout

## Auditability

- Record user/session-level audit events:
  - login/logout
  - connector create/update/delete
  - job submission/cancel/retry
  - transfer start/finish/fail
- Exportable audit trail for institutional review

## Commercial Licensing Model

Use signed license tokens (file-based), optionally named `nir_license.txt`.

Do not rely on editable plain-text expiration checks without signatures.

### License Token Claims (Suggested)

- `license_id`
- `organization_id`
- `plan_tier`
- `issued_at`
- `expires_at`
- `features` (connector/workflow/transfer entitlements)
- `seat_limit` (optional)
- `offline_grace_days`
- signature

### Validation Rules

- Verify signature using embedded public key
- Verify `expires_at` and entitlement claims
- Support short offline grace period (for institutional network outages)
- Revalidate online periodically when network is available
- Support revocation list checks

### Licensing Lifecycle

1. Customer downloads desktop app from official website
2. Customer signs in or imports license token
3. Client validates token and activates features
4. Client warns before expiry and guides renewal
5. Expired token enters read-only or limited mode based on policy

## Recommended Commercial Tiers (Starter)

- Trial (30-90 days): limited seats/features
- Professional: paid desktop orchestration with standard connectors
- Enterprise: SSO, advanced audit, policy controls, SLA support, optional self-hosted control plane

## Shared Responsibility

NIR team is responsible for:

- client integrity (signing, update channel, security patches)
- license service integrity
- control-plane security and audit fidelity

Customer is responsible for:

- endpoint security posture
- identity governance and access approvals
- HPC/remote infrastructure hardening and policy

## Rollout Plan

## Phase 1: Existing Linux Self-Hosted Orchestrator (Current Baseline)

- harden controls
- improve security documentation and deployment defaults
- establish paid support/licensing foundation

## Phase 2: Desktop Shell

- thin client MVP
- secure keychain integration
- signed updates
- license-token activation/renewal flows

## Phase 3: Hosted SaaS Control Plane

- centralized enterprise controls
- managed onboarding and billing
- compliance-ready posture (DPA/BAA paths where needed)

## Implementation Checklist (MVP)

- [ ] Define desktop threat model
- [ ] Implement keychain-backed credential storage
- [ ] Add signed license-token validation
- [ ] Add expiring trial and renewal UX
- [ ] Add telemetry and audit events (privacy-safe)
- [ ] Ship signed installers for Linux/macOS/Windows
- [ ] Publish security and data handling statement

## Notes for Sensitive Data Users

- Keep raw data in institutional systems whenever possible.
- Prefer remote/HPC execution over local desktop processing.
- Enable org-wide SSO and role-based controls before broad rollout.
- Treat desktop logs and exported bundles as potentially sensitive artifacts.
