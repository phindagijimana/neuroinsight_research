# Full Experience Parity Checklist

Use this checklist to verify that desktop delivers the same practical
experience as the current NIR web/CLI deployment.

## A. Startup and Shell Behavior

- [ ] Desktop app launches reliably on target OS
- [ ] Backend boots from desktop without `./research` dependency
- [ ] App transitions from control/splash to NIR UI automatically
- [ ] Startup errors are shown with actionable messages
- [ ] Desktop restart preserves previous user state where expected

## B. UI and Navigation Parity

- [ ] Dashboard renders with expected data and actions
- [ ] Jobs page supports list/filter/status updates
- [ ] Transfer page supports browse/transfer workflows
- [ ] Viewer page loads bundle outputs and overlays
- [ ] Documentation/help links behave as expected

## C. Core Workflow Parity

- [ ] Local plugin run submits and completes
- [ ] Workflow run submits and completes
- [ ] Result files, metrics, and provenance endpoints work
- [ ] Export/download flows behave the same as baseline
- [ ] Failure states match baseline semantics

## D. Connectors and HPC Parity

- [ ] Pennsieve connect/browse/download flow works
- [ ] XNAT connect/browse/download flow works
- [ ] HPC connect and submission flow works
- [ ] HPC result resolution and retrieval works
- [ ] Connector/HPC errors are visible and diagnosable

## E. Security and Licensing Parity

- [ ] License import and validation behavior matches policy
- [ ] Invalid/expired license UX is clear and correct
- [ ] Credential vault read/write/delete works by key namespace
- [ ] No plaintext secrets are written outside approved locations

## F. Diagnostics and Supportability

- [ ] Desktop log path is discoverable in UI
- [ ] Diagnostics bundle exports successfully
- [ ] Bundle contains enough evidence for triage
- [ ] Error correlation between desktop and backend logs is possible

## G. Packaging and Install/Upgrade

- [ ] Clean install works on Linux/macOS/Windows
- [ ] Upgrade from previous installer keeps user data safely
- [ ] Uninstall behavior matches expectations
- [ ] Checksum verification instructions are accurate

## H. Acceptance Gate

- [ ] No unresolved P0/P1 parity regressions
- [ ] Known deltas are documented with owners and ETA
- [ ] Stakeholders approve cutover readiness
