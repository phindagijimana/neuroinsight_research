# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/). The canonical version is
the repo-root `VERSION` file (see `scripts/bump_version.py`).

## [Unreleased]

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
