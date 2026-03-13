# Desktop Packaging Ops

This directory contains packaging/release utilities for NIR Desktop.

## Phase 5 Operations Kit

- `PILOT_CHECKLIST.md` - single execution doc (checklist + cadence + evidence log)
- `GO_LIVE_RECOMMENDATION_TEMPLATE.md` - single decision doc for phase exit
- `pilot_smoke_test.sh` - quick pre-pilot validation script
- `SIGNING_AND_TRUST.md` - Phase 6 signing/notarization setup and trust checks
- `PHASE7_RELIABILITY_GATE.md` - Phase 7 go/conditional/no-go gate definition
- `pilot_reliability_report.template.json` - reliability evidence template
- `evaluate_pilot_gate.js` - automated gate evaluator for pilot evidence

## Linux Packaging

Use:

```bash
./desktop/ops/package_desktop_linux.sh
```

This performs:

- dependency install for `desktop/app`
- desktop source checks
- Linux artifact build (AppImage + deb)
- SHA256 and release metadata generation

Artifacts are written to `desktop/dist/`.

## Pre-Pilot Smoke Validation

Use:

```bash
./desktop/ops/pilot_smoke_test.sh linux
./desktop/ops/pilot_smoke_test.sh windows
./desktop/ops/pilot_smoke_test.sh macos
```

## Metadata and Checksums

`release_metadata.js` generates:

- `desktop-release-metadata.json`
- `desktop-release-sha256.txt`
- `desktop-release-metadata-<platform>.json` (when platform is provided)
- `desktop-release-sha256-<platform>.txt` (when platform is provided)

Use platform-scoped checksum files for user verification to avoid mixing
Linux/macOS/Windows checksums in the same download folder.

`verify_release_artifacts.js` validates that platform installers and platform-
scoped checksum/metadata files exist before upload:

```bash
node desktop/ops/verify_release_artifacts.js desktop/dist linux
node desktop/ops/verify_release_artifacts.js desktop/dist windows
node desktop/ops/verify_release_artifacts.js desktop/dist macos
```

`verify_release_checksums.js` validates checksum coverage and digest integrity
for each platform artifact set:

```bash
node desktop/ops/verify_release_checksums.js desktop/dist linux
node desktop/ops/verify_release_checksums.js desktop/dist windows
node desktop/ops/verify_release_checksums.js desktop/dist macos
```

## Verified Install Helpers (Checksum Before Install)

Each release bundle includes a platform helper that verifies installer checksum
entries first, then starts install:

- Linux: `install-nir-linux.sh`
- macOS: `install-nir-macos.sh`
- Windows: `install-nir-windows.cmd` (wraps `install-nir-windows.ps1`)

These are also produced by the GitHub workflow:

- `.github/workflows/desktop_release.yml`
- `.github/workflows/desktop_release_multi.yml` (Linux + Windows + macOS, isolated desktop-only release path)

## Phase 7 Reliability Gate Check

Use:

```bash
cp desktop/ops/pilot_reliability_report.template.json desktop/ops/pilot_reliability_report.json
# fill pilot_reliability_report.json with real pilot evidence
node desktop/ops/evaluate_pilot_gate.js desktop/ops/pilot_reliability_report.json
```

Exit code behavior:

- `0`: `go` or `conditional_go`
- `2`: `no_go`
