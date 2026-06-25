# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/). The canonical version is
the repo-root `VERSION` file (see `scripts/bump_version.py`).

## [Unreleased]

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
- All-in-one container now generates unique per-install credentials
  (Redis / MinIO / SECRET_KEY) at first run instead of shipping fixed defaults.
- Release workflow refuses to publish unsigned/un-notarized installers.
- Documented the local-only trust model and the "do not expose to the internet"
  guidance in the README.

## [0.1.0] - unreleased
Initial pilot baseline: Electron desktop app + all-in-one container
(API + Celery + Postgres + Redis + MinIO + SPA), multi-platform installers, and
the plugin/workflow pipeline engine.
