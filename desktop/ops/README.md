# Desktop Packaging Ops

This directory contains packaging/release utilities for NIR Desktop.

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

## Metadata and Checksums

`release_metadata.js` generates:

- `desktop-release-metadata.json`
- `desktop-release-sha256.txt`

These are also produced by the GitHub workflow:

- `.github/workflows/desktop_release.yml`
