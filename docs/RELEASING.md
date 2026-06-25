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

- [ ] **Code-signing — currently SKIPPED (optional).** Releases ship **unsigned**;
      the workflow warns (doesn't block). Users do a one-time "open anyway" on
      first launch (see [INSTALL.md](INSTALL.md)). To remove the warnings later,
      add signing secrets (see [SIGNING_AND_TRUST.md](SIGNING_AND_TRUST.md)) and
      builds sign + notarize automatically.
- [ ] **GHCR package is public.** After the first image push, set
      `nir-allinone` to Public: GitHub → your profile → **Packages** →
      `nir-allinone` → **Package settings** → **Change visibility → Public**.
      If it stays private, end users' Docker can't pull it and the app can't
      start its engine.

## Per-release steps

1. **Bump the version** (must be greater than the last tag; latest desktop tag
   was `v0.1.8`, so this release is `0.1.9`):
   ```bash
   python3 scripts/bump_version.py 0.1.9
   git commit -am "chore: release v0.1.9"
   git push origin main
   ```

2. **Publish the engine image FIRST** (so it exists when the app looks for it):
   ```bash
   git tag nir-v0.1.9 && git push origin nir-v0.1.9
   ```
   Wait for the *All-in-One Image (GHCR)* workflow to finish (multi-arch
   amd64+arm64). It tags `:v0.1.9` and `:latest`.

3. **Confirm the image is pullable without auth** (simulates an end user) — from
   a machine that is **not** logged in to GHCR:
   ```bash
   docker pull ghcr.io/phindagijimana/nir-allinone:v0.1.9
   ```
   If this fails with auth/denied, the package isn't public yet (see prereqs).

4. **Build + publish the desktop installers:**
   ```bash
   git tag desktop-v0.1.9 && git push origin desktop-v0.1.9
   ```
   The *Desktop Release (Multi-Platform)* workflow builds macOS/Windows/Linux
   installers, generates `SHA256SUMS.txt`, and attaches everything to the GitHub
   Release. With no signing secrets it **warns and ships unsigned** (current
   setup); add secrets later to sign + notarize.

5. **Verify the release:**
   - [ ] GitHub Release has `.dmg`, `.exe`, `.AppImage`/`.deb`, and `SHA256SUMS.txt`.
   - [ ] (If signed) macOS: `spctl -a -vvv -t install <app>` reports *Notarized
         Developer ID*. (If unsigned, expect the one-time right-click → Open.)
   - [ ] Fresh-machine test: on a clean Mac/Win/Linux with only Docker Desktop,
         install → first launch downloads the engine (~1.8 GB) → lands in the
         Workspace.
   - [ ] `docs/INSTALL.md` links resolve and the version matches.

## Workflow notes (sanity-check)

- `allinone_image.yml` — correct: multi-arch build of `docker/allinone/Dockerfile`,
  GHCR login via the built-in `GITHUB_TOKEN` (`packages: write`), tags derived
  from the `nir-v*` tag (`v<x.y.z>` + `latest`). No change needed; the only
  external action is making the package **public** (above).
- `desktop_release_multi.yml` — builds all three platforms, enforces signing on a
  published tag, runs checksum/trust verification, and attaches artifacts.
- Tag order matters: **`nir-v*` before `desktop-v*`** so the engine image exists
  when the new desktop version ships.
