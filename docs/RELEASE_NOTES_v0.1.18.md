# NeuroInsight v0.1.18

Patch release — **FreeSurfer local jobs, resource detection, Transfer parity, progress UI**.

## Install

Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM (16 GB+ recommended for FreeSurfer).

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.18-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.18.exe` |
| Linux | `NeuroInsight-0.1.18.AppImage` / `.deb` |

Verify downloads: [INSTALL.md](INSTALL.md).

## Highlights

**Fixed**
- **FreeSurfer recon-all failing mid-run** (`Container exited with code 1` during CA
  registration) — removed `-parallel` from container commands; `-parallel` re-invokes
  `recon-all -i` and fails when a subject folder already exists.
- **Existing FreeSurfer subject folder** — if `subject` (or your chosen ID) already
  exists in `SUBJECTS_DIR`, the run automatically uses `subject_2`, `subject_3`, …
  instead of failing or overwriting.
- **Progress bar stuck at 0%** during FreeSurfer — milestone patterns updated for
  FreeSurfer 7.4 log format (`#@# MotionCor`, `#@# Talairach`, etc.).
- **Resource panel showed wrong host limits** — the engine container previously
  reported its own cgroup limits (~5 GB / 2 CPU) instead of your Mac/PC. Host CPU/RAM
  are now passed through (`NIR_HOST_CPU_COUNT`, `NIR_HOST_MEMORY_GB`).
- **Customize resources ignored or under-applied** — job submission now merges plugin
  profile defaults with UI overrides reliably (`mem_gb` / `memory_gb` normalization).
- **Job runtime showing 0m** — runtime now falls back to submitted→completed timestamps
  when `started_at` was missing; stale-job reaper preserves container start time.

**Added**
- **Transfer page parity** — home-directory root, **Choose…** (desktop), auto-open
  file browser when selecting Local or connecting Remote/HPC (same as Jobs page).
- **Choose… placeholder** — Subject Path field no longer suggests `./data/sub-001/…`
  when using desktop local paths.

## Upgrade notes

1. Install v0.1.18 and **restart the engine** once (**Settings → Engine → Restart
   engine**) so host resource env vars and plugin YAML updates load.
2. For **FreeSurfer recon-all** on Local Docker:
   - Use **Choose…** to pick your T1w file.
   - Set **Memory ≥ 16 GB** (32 GB recommended), **CPUs 4–8**, **Time ≥ 8 h**.
   - Allow 6–8 hours per subject on Apple Silicon (Rosetta emulation).
3. Failed partial FreeSurfer runs from older versions can stay on disk; v0.1.18 picks
   the next free subject folder name automatically.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
