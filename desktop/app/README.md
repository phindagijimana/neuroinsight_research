# Desktop App Phase 1 Scaffold

This folder contains the Electron host for NIR Desktop (Phases 1-4 scaffold).

## What It Does

- opens a native desktop shell window
- checks if NIR backend is running (`/health` on `3000`/`3001`)
- starts backend directly from desktop process manager (uvicorn)
- starts celery worker directly from desktop process manager (best effort)
- stops desktop-managed backend service
- stops desktop-managed backend + celery worker
- opens the running NIR UI in the same desktop window
- persists desktop settings and logs under Electron user data path
- runs desktop preflight checks (Docker/ports/disk/keychain/Python/Celery/ports)
- exports a diagnostics support bundle JSON with runtime process + log snapshots
- supports Phase 3 license import/validation (signed token model)
- auto-detects `nir_license.txt` on startup when placed next to the app binary
  (or AppImage / `.app` bundle location) and imports it when valid
- supports Phase 3 credential vault abstraction (OS keychain when available, encrypted fallback)
- supports optional Phase 3 local app lock (PIN-based sensitive action gating)
- Phase 3.5 hardening:
  - stricter license schema validation
  - invalid licenses are rejected before persistence
  - header license status badge
  - namespaced vault key guidance/presets with backend enforcement
- Phase 4 packaging scaffold:
  - `electron-builder` config for Linux targets (AppImage, deb)
  - packaging scripts in `package.json`
  - release metadata + SHA256 generation via `desktop/ops/release_metadata.js`
- desktop icon assets under `desktop/app/assets/` (`NIR` on navy blue)

## What It Does Not Do Yet

- auto-update channel is not wired yet
- trusted signing/notarization still depends on operator-provided certificates
- fully self-contained backend packaging is not wired yet (repo checkout still required)

## Run Locally

From repo root:

```bash
cd desktop/app
npm install
npm start
```

## Build Linux Artifacts (Phase 4)

From repo root:

```bash
./desktop/ops/package_desktop_linux.sh
```

Artifacts are emitted to `desktop/dist/`, including:

- `nir-desktop-<version>-linux-<arch>.AppImage`
- `nir-desktop-<version>-linux-<arch>.deb`
- `desktop-release-metadata.json`
- `desktop-release-sha256.txt`

## Persistent Desktop Files

On first launch, the app creates:

- settings file (includes `autoOpenOnStart`)
- desktop log file (JSON-line event log)
- diagnostics bundle output directory
- local license state files
- credential vault files (fallback backend only)

The exact file paths are shown in the control center UI.

## License Public Key

For signed license verification, provide an Ed25519 public key:

- env: `NIR_DESKTOP_LICENSE_PUBLIC_KEY`
- or file: `desktop/app/config/license_public_key.pem`
- or file: `<userData>/nir-desktop/license_public_key.pem`

See `desktop/app/config/license_public_key.pem.example`.

## Safety Note

This scaffold is additive and isolated to `desktop/app`. It does not modify the
core NIR backend/frontend codepaths used by existing workflows.
