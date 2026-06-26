# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/). The canonical version is
the repo-root `VERSION` file (see `scripts/bump_version.py`).

## [Unreleased]

### Added
- **Deployment-aware Settings.** In a browser/web-hosted deployment the app shows
  a **Settings** tab (tool licenses), since there's no desktop control center. In
  the desktop app that tab is hidden — the control center owns engine + licenses.
  Detected via the `window.nir` desktop bridge. Fixes web users losing the
  licenses UI after it moved into the control center.

### Changed
- **Cleaner UI — moved teaching copy into the User Guide.** Trimmed verbose
  in-app explanations (home capability blurbs, page subtitles, viewer/sample
  hint banners, the HPC VPN/Duo banner, the control-center license blurb) down to
  concise labels. Added a **User Guide** button in the control center (Settings)
  and a shared `USER_GUIDE_URL`; the removed how-to (incl. VPN/MFA-Duo/saved-host
  HPC connect details) now lives in `docs/USER_GUIDE.md`. Pass 2 extended this to
  the Docs Plugin/Workflow glossary (incl. the TSC hidden-plugin notes), the
  BackendSelector data→compute description lines, the resource-slider hints, and
  the XNAT connect copy — all trimmed or moved to the guide. Field-level help
  needed at point of use (capacity warnings, API-key location, Duo-push hint) is
  kept.
- **Tool licenses (FreeSurfer/MELD) moved into the control center** ("Settings",
  where the Engine lives) instead of a separate web Settings page. The control
  center now has a Tool-licenses card (status, paste/file upload, replace/remove,
  "Get a license"), proxied to the engine's `/api/licenses` over a new
  `nir.licenses` IPC bridge. The standalone web Settings page + nav item were
  removed so there's a single Settings surface. Verified end-to-end: paste/file
  upload writes `license.txt` to the data dir where jobs read it; remove deletes it.

### Fixed
- **Remote Docker backend couldn't run single-plugin jobs.** Two bugs: (1) the
  command was run as `docker run <image> bash -c …` with no `--entrypoint`, so
  images with a non-shell ENTRYPOINT (heudiconv, fmriprep, qsiprep…) consumed
  the script as their own arguments and failed; (2) **directory** inputs were
  never uploaded (only single files), and inputs weren't staged under the
  plugin's declared key. Now the substituted script is written to a file and run
  via a mounted path with `--entrypoint /bin/bash` (matching the workflow path),
  and inputs are staged under their plugin key with recursive directory upload.
  Verified end-to-end on a real EC2 host: dcm2niix now exits 0 and writes
  `.nii.gz` to the remote output dir. (Remaining: remote job status-monitoring /
  result pull-back still report `pending` — tracked separately.)
- **Boolean plugin parameters were ignored** across all execution backends
  (local Docker, SLURM/HPC, remote Docker). Command templates test
  `[ "{flag}" = "true" ]`, but Python `True` was substituted as `"True"`
  (capital T) via `str()`, so the test always failed and the flag was dropped —
  e.g. dcm2niix `compress=true` silently ran `-z n` and produced a `.nii`
  instead of `.nii.gz`. Bools now render as lowercase `true`/`false`
  (`_shell_value`) at every template-substitution site. Verified end-to-end:
  dcm2niix now runs `-z y` and emits `.nii.gz`.

## [0.1.12] - 2026-06-26

### Fixed
- **macOS app icon looked oversized** — the icon art was full-bleed
  (squircle edge-to-edge), so it rendered ~20% larger than other apps in the
  Dock/Finder. Rebuilt `icon.icns` to Apple's icon grid (824px body on the
  1024 canvas, ~100px transparent margin). Windows `.ico` / Linux `.png` stay
  full-bleed (those platforms don't mask icons).

## [0.1.11] - 2026-06-26

### Fixed
- **App crashed on launch (macOS)** — the startup update-check had
  `autoDownload=true`, so electron-updater's `MacUpdater` tried to download the
  update and threw `ZIP file not provided` for a dmg-only, unsigned release, and
  the unhandled rejection killed the app before it reached the workspace. The
  updater now only checks + logs availability (`autoDownload=false`,
  `autoInstallOnAppQuit=false`); downloads happen only on explicit action once
  signing + a `.zip` artifact exist. The mac build now also emits a `zip` target
  so signed auto-update works when enabled.

### Notes
- Builds remain **unsigned** (pilot). First launch: macOS **right-click → Open**
  (Sequoia: **System Settings → Privacy & Security → Open Anyway**); Windows
  **More info → Run anyway**. Verify integrity with the published
  `desktop-release-sha256-<platform>.txt`.

## [0.1.10] - 2026-06-25

### Fixed
- **Local jobs crashed** (`NameError` in `celery_tasks.run_docker_job`) — every
  local Docker plugin/workflow job failed. Found by running dcm2niix end-to-end.
- **Container `HOME` unset** under supervisord → `~/.ssh/config` didn't resolve;
  saved-host aliases came back empty. Pinned `HOME=/home/neuroinsight`.
- **Stale `postmaster.pid`** after a force-quit/crash made Postgres refuse to
  start, so the app never came up; the lock is now cleared on startup.

### Added
- **Saved-host SSH alias picker** — connect by `~/.ssh/config` alias
  (`GET /api/hpc/ssh-hosts`), auto-filling host/user/port.
- **SystemSSHSession** — OS `ssh` + ControlMaster multiplexing (connect/exec/
  browse), honoring `~/.ssh/config` (aliases, ProxyJump). Foundation for the
  designed interactive-MFA HPC flow (`docs/design/interactive-ssh-auth.md`).
- End-user docs: `docs/INSTALL.md`, `docs/RELEASING.md`; real multi-res app icon.

## [0.1.9] - 2026-06-25

### Added
- Desktop crash & fatal-error capture: native crash minidumps (local-only) plus
  handlers for uncaughtException / unhandledRejection / render- & child-process
  crashes, logged to the diagnostics store with a single clear user dialog.
- `docs/SIGNING_AND_TRUST.md` runbook for macOS notarization and Windows code
  signing, including the exact GitHub Secrets and local verification steps.
- Single version source of truth: repo-root `VERSION` (read by the backend and
  synced to both package.json files via `scripts/bump_version.py`).
- Shared UI primitives: `Button`, `StatusBadge`, `LoadingState`/`Spinner`, and an
  app-wide toast + confirm-dialog system.
- `CHANGELOG.md`; CI security scan (bandit, advisory) and a coverage floor.

### Changed
- UI polish: clearer page names (Dashboard → Results), calmer labels (removed
  ALL-CAPS micro-labels and marketing buzzwords), decluttered Control Center
  into essentials + an Advanced section, and tokenized the navy brand colour.
- CORS restricted to explicit methods/headers (was wildcard).
- Frontend `build` now runs `tsc --noEmit` so type errors fail the build.

### Fixed
- Frontend type-check (`tsc --noEmit`) now passes, so CI actually enforces it
  (added `@types/three`, fixed `TreeNode`/recharts/missing-import errors).
- Streamed first-run container image-pull progress to the splash screen.

### Security
- Interim integrity for unsigned builds: every desktop build now emits a
  `SHA256SUMS.txt` next to the installers (afterAllArtifactBuild hook), and the
  app bakes in an `app-integrity.json` (sha256 of app.asar) that it self-verifies
  at launch, warning on tampering/corruption until code signing is in place.
- All-in-one container now generates unique per-install credentials
  (Redis / MinIO / SECRET_KEY) at first run instead of shipping fixed defaults.
- Releases currently ship unsigned (signing skipped); integrity via
  SHA256SUMS.txt + a baked-in app-integrity manifest, with a one-time
  "open anyway" on first launch. Signing/notarization auto-engages when
  certs are added (docs/SIGNING_AND_TRUST.md).
- Documented the local-only trust model and the "do not expose to the internet"
  guidance in the README.

## [0.1.0] - unreleased
Initial pilot baseline: Electron desktop app + all-in-one container
(API + Celery + Postgres + Redis + MinIO + SPA), multi-platform installers, and
the plugin/workflow pipeline engine.
