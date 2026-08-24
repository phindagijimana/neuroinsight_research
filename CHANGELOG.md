# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/). The canonical version is
the repo-root `VERSION` file (see `scripts/bump_version.py`).

## [Unreleased]

## [0.1.24] - 2026-08-24

### Changed
- **Jobs UI** — 2×2 submit grid (Compute | Pipeline, Subject path | Resources);
  unified page header; removed Back button; Transfer link in subtitle.
- **Transfer UI** — unified header and page width; navy Remote tab; auto-browse
  when platform/SSH already connected; improved empty states.
- **Navigation** — responsive hamburger menu on narrow screens; active-tab highlight.
- **Home** — Transfer-first capability copy; removed duplicate Overview header.

## [0.1.23] - 2026-08-24

### Added
- **Large-file transfer** — per-file timeouts (24h default), `curl -C -` and HTTP
  Range resume, skip complete files on re-run, Pennsieve URL retries; shared I/O in
  `transfer_io.py` / `transfer_manager.py`; Celery tasks delegate to TransferManager.
- **Transfer docs** — `docs/TRANSFER.md` (5×5 matrix + `NIR_TRANSFER_*` env vars).
- **Pennsieve browse pagination** — `limit` / `offset` / `has_more`; session persists
  via `PlatformSessionContext`.
- **Jobs compute-only** — Data Source row and Pennsieve/XNAT wizard removed; compute
  backend + path browse only; Transfer callout on Jobs page.
- **Transfer → Jobs handoff** — “Open in Jobs” after transfer completes; prefills path
  and compute backend via `consumeJobsOpenAt`.
- **Path mismatch warnings** — amber alert before Submit when path does not match
  compute backend (e.g. Mac path on HPC).
- **Per-tab SSH panels** — Remote Server vs HPC (SLURM) connect copy under Compute.

### Changed
- **Jobs / SSH UX** — connected banner (HPC / Remote / SSH only), auto-expand SSH,
  compute tab auto backend switch; honest staging copy on Home and README.
- **SSH broker** — SCP timeout passthrough for large transfers.

## [0.1.22] - 2026-08-23

### Changed
- **Jobs page layout** — submit form on top; full-width stacked stats, SLURM queue,
  and jobs list at the bottom (matches classic vertical flow).
- **Submit panel** — left column: data/compute + input browser; right column:
  pipeline + resources (matches prior Process MRI Data layout).
- **Scroll consistency** — jobs list uses `nir-scroll-panel`; SLURM table aligned
  to the same `min(24rem, 55vh)` cap as other page panels.

## [0.1.21] - 2026-08-23

### Changed
- **Classic workspace UI** — horizontal top navigation and Jobs page layout restored;
  compact pipeline dropdowns and less verbose submission copy.
- **Compact panels** — resources and SSH collapsed by default on Jobs; provenance
  accordion on Results; compact job rows and conditional SLURM/stats strips.
- **Scrollable lists** — shared `nir-scroll-*` utilities for file browsers, job
  lists, transfer history, and long provenance blocks.

### Added
- **Desktop update docs** — `docs/DESKTOP_UPDATES.md` and README updating section.

## [0.1.20] - 2026-08-23

### Fixed
- **Desktop auto-update** — only prompt and download when `electron-updater` reports
  `isUpdateAvailable`, fixing “Please check update first” on Download & Install.

## [0.1.19] - 2026-08-23

### Added
- **Desktop workspace shell** — sidebar navigation (Jobs, Results, Viewer, Transfer,
  Docs), engine status chip, and shared page headers; desktop opens on Jobs by default.
- **Subject-first job labels** and **human-readable output folders** (e.g.
  `sub-001_fs_76625681`); UUID remains the system key. API fields: `subject_label`,
  `input_label`, `output_folder`.
- **Jobs search/filter** and **input/output path bars** with Copy plus open in Finder
  (desktop) or Transfer (HPC, remote, XNAT, Pennsieve).
- **Results page polish** — subject-first picker, Statistics-first tabs, compact
  output path bar, short job IDs in metadata.
- **Viewer file drawer** — collapsible left panel for job outputs; compact Niivue
  toolbar with Adjust panel for window/level and slice controls.
- **Pipeline catalog** (Docs) — selectable plugins by default, toggle for internal
  utilities, compact license chips, clickable references.
- **Searchable pipeline picker** and BIDS/NIfTI-aware submission hints on Jobs.

### Changed
- Jobs, Results, Viewer, and Docs layouts aligned for professional desktop daily use.
- Job selectors use subject labels and 8-character IDs instead of full UUIDs.
- Transfer deep-links when opening remote/HPC/platform paths from job rows.
- Control Center and desktop renderer styling/preflight polish.

### Fixed
- Host output path resolution for local Docker jobs (`host_data_dir` mapping to
  `~/.nir/data/outputs/…`).
- Auto-refresh for recent jobs that may reconcile after false failures (long runs).
- Viewer and Docs no longer surface internal utility plugins by default.
- Multi-file job inputs use the first real file path for reveal/open actions.
- macOS release CI now ships a signed `.zip` alongside the DMG so in-app auto-update
  works on Mac (Squirrel.Mac requires the zip feed entry in `latest-mac.yml`).

## [0.1.18] - 2026-08-22

### Added
- **Transfer page parity with Jobs** — home-directory browse root, desktop **Choose…**
  picker, and auto-open file browser when selecting Local or connecting Remote/HPC.
- **FreeSurfer subject-folder collision handling** — uses `subject_2`, `subject_3`, …
  when the requested subject ID already exists in `SUBJECTS_DIR`.

### Fixed
- **FreeSurfer local Docker jobs failing mid-run** — removed `-parallel` from
  `freesurfer_recon` and `freesurfer_autorecon_volonly` commands (incompatible with
  containerized `-i` re-runs).
- **Progress bar stuck at 0% during FreeSurfer** — phase milestones match FreeSurfer
  7.4 `#@#` stage headers.
- **Resource panel under-reporting host RAM/CPU (desktop)** — engine now receives
  `NIR_HOST_CPU_COUNT` and `NIR_HOST_MEMORY_GB` from the desktop app instead of
  reading the engine container's cgroup limits.
- **Job resource merge** — plugin profile defaults and Customize UI overrides merge
  correctly (`mem_gb` / `memory_gb`); thread count passed to FreeSurfer `-openmp`.
- **Job runtime showing 0m** — `runtime_seconds` falls back to submitted→completed;
  `started_at` set on first running transition; stale reaper reads container start time.
- **Misleading Subject Path placeholder** — local mode now says "Choose… or paste an
  absolute path" instead of `./data/sub-001/…`.

## [0.1.17] - 2026-08-21

### Added
- **Native file/folder picker for local jobs (desktop).** Jobs → **Choose…** opens the
  OS file dialog (Finder on macOS, Explorer on Windows, native picker on Linux)
  instead of only the in-app tree rooted at `./data`.
- **Host home directory mounted into the engine container** so local input paths
  under your profile resolve for Local Docker jobs (`NIR_HOST_HOME` + read-only
  home bind mount). macOS also mounts `/Volumes` read-only for external drives.

### Fixed
- **"Input file not found" for valid local paths** — the engine could not see host
  files outside `~/.nir/data` when submitting Local Docker jobs from the desktop app.

## [0.1.16] - 2026-08-21

### Fixed
- **macOS Dock icon looked oversized** — `app.dock.setIcon()` was overriding the
  padded `icon.icns` with full-bleed `icon.png` on every launch. Packaged apps
  now use the bundle `.icns`; dev mode loads the padded `.icns` explicitly.

## [0.1.15] - 2026-08-20

### Fixed
- **macOS GUI launch PATH (Docker/Node/npm/Celery detection).** Apps launched from
  Finder, Dock, or a DMG inherit a stripped `PATH` (`/usr/bin:/bin:…`) that omits
  `/usr/local/bin`, `/opt/homebrew/bin`, and Docker Desktop's bundled `bin`, so
  preflight reported "Docker is not running" (and Node/npm/Celery checks failed)
  even when those tools were installed and running. The desktop app now prepends
  the standard tool locations to `process.env.PATH` at startup so every spawn finds
  them regardless of launch method.

## [0.1.14] - 2026-07-07

### Added
- **User-confirmed auto-update (desktop).** Now that releases are signed and ship
  a signed `.zip`, the app can update itself — and never downloads without
  consent. On startup (or via **Help → Check for Updates…**) it prompts when a
  new version is available, downloads on confirmation, then offers to **Restart
  Now** or install on next quit.
- **Remote-Docker job status monitoring.** Jobs run on a remote Docker server
  over SSH now report live status (pending → running → completed/failed) in the
  UI, matching the existing local and HPC/SLURM behavior. Validated end-to-end
  against a live remote host.

### Changed
- **Signed & notarized macOS releases** are now the norm (Developer ID +
  notarization/stapling), so macOS no longer shows the Gatekeeper
  "unidentified developer" block. Notarization is resilient to Apple notary
  backlogs.

## [0.1.13] - 2026-06-26

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
