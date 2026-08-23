# Releasing NeuroInsight (Desktop + Engine Image)

A release has **two coupled artifacts** that must ship at the **same version**:

1. the **all-in-one engine image** → `ghcr.io/phindagijimana/nir-allinone:v<version>`
   (built by `.github/workflows/allinone_image.yml` on a `nir-v*` tag)
2. the **desktop installers** → attached to a GitHub Release
   (built by `.github/workflows/desktop_release_multi.yml` on a `desktop-v*` tag)

The packaged desktop app pulls `nir-allinone:v<appVersion>` on first run, so the
image **must exist and be public before** users run that desktop version.
`VERSION` (repo root) is the single source of truth; `scripts/bump_version.py`
keeps the desktop/frontend `package.json` in sync.

## One-time prerequisites

- [ ] **macOS signing secrets** in GitHub Actions (see [SIGNING_AND_TRUST.md](SIGNING_AND_TRUST.md)) — macOS releases are signed/notarized when `CSC_*` and `APPLE_*` secrets are set.
- [ ] **Windows signing** (optional) — add `WIN_CSC_*` secrets; otherwise Windows ships unsigned with checksums.
- [ ] **GHCR package is public.** After the first image push, set
      `nir-allinone` to Public: GitHub → your profile → **Packages** →
      `nir-allinone` → **Package settings** → **Change visibility → Public**.
      If it stays private, end users' Docker can't pull it and the app can't
      start its engine.

## Per-release steps

1. **Bump the version** (must be greater than the last tag):
   ```bash
   python3 scripts/bump_version.py 0.1.16
   git commit -am "chore: release v0.1.16"
   git push origin main
   ```

2. **Publish the engine image FIRST** (so it exists when the app looks for it):
   ```bash
   git tag nir-v0.1.16 && git push origin nir-v0.1.16
   ```
   Wait for the *All-in-One Image (GHCR)* workflow to finish (multi-arch
   amd64+arm64). It tags `:v0.1.16` and `:latest`.

3. **Confirm the image is pullable without auth** (simulates an end user) — from
   a machine that is **not** logged in to GHCR:
   ```bash
   docker pull ghcr.io/phindagijimana/nir-allinone:v0.1.16
   ```
   If this fails with auth/denied, the package isn't public yet (see prereqs).

4. **Build + publish the desktop installers:**
   ```bash
   git tag desktop-v0.1.16 && git push origin desktop-v0.1.16
   ```
   The *Desktop Release (Multi-Platform)* workflow builds macOS/Windows/Linux
   installers, generates checksum files, and attaches everything to the GitHub
   Release. macOS is signed/notarized when Apple secrets are configured.

5. **Verify the release:**
   - [ ] GitHub Release has `.dmg`, `.exe`, `.AppImage`/`.deb`, and checksum files.
   - [ ] macOS: release includes **`NeuroInsight-*-arm64-mac.zip`** and **`latest-mac.yml`**
         (Squirrel auto-update; CI `dist:mac:ci` must build `dmg zip`).
   - [ ] macOS: `spctl -a -vvv -t install <dmg>` reports *Notarized Developer ID* (when signed).
   - [ ] Fresh-machine test: install → first launch downloads the engine (~1.8 GB).
   - [ ] `docs/INSTALL.md` and `docs/DESKTOP_UPDATES.md` links resolve.

## Auto-update (end users)

User-facing flow and troubleshooting: [DESKTOP_UPDATES.md](DESKTOP_UPDATES.md).

## Workflow notes

- `allinone_image.yml` — multi-arch GHCR image from `nir-v*` tags.
- `desktop_release_multi.yml` — multi-platform installers + checksum/trust verification.
- Tag order: **`nir-v*` before `desktop-v*`** so the engine image exists when the desktop ships.
