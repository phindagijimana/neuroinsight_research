# Desktop App Phase 1 Scaffold

This folder contains a minimal Electron host for NIR Desktop Phase 1.

## What It Does

- opens a native desktop shell window
- checks if NIR backend is running (`/health` on `3000`/`3001`)
- starts backend using existing CLI: `./research start`
- stops app services: `./research stop app`
- stops app + infrastructure safely: `./research stop`
- opens the running NIR UI in the same desktop window
- persists desktop settings and logs under Electron user data path
- runs desktop preflight checks (Docker/ports/disk/keychain availability)
- exports a diagnostics support bundle JSON
- supports Phase 3 license import/validation (signed token model)
- supports Phase 3 credential vault abstraction (OS keychain when available, encrypted fallback)
- Phase 3.5 hardening:
  - stricter license schema validation
  - invalid licenses are rejected before persistence
  - header license status badge
  - namespaced vault key guidance/presets with backend enforcement

## What It Does Not Do Yet

- packaged installers/signing/update channel
- production keychain integration
- paid license validation
- cross-platform adapters and diagnostics bundle

## Run Locally

From repo root:

```bash
cd desktop/app
npm install
npm start
```

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

This scaffold reuses existing NIR runtime commands and does not modify current
CLI-hosted workflows. It is additive and isolated to `desktop/app`.
