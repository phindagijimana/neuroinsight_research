# NeuroInsight v0.1.23

Transfer-first data movement and compute-only Jobs.

## Install

Download from the [GitHub release](https://github.com/phindagijimana/neuroinsight_research/releases/tag/desktop-v0.1.24)
(latest) or use **Help → Check for Updates** from an older desktop build.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.24-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.24.exe` |
| Linux | `NeuroInsight-0.1.24.AppImage` / `.deb` |

## Highlights

- **Large-file Transfer** — per-file timeouts, resume, skip-on-rerun; Pennsieve → HPC
  direct curl; shared transfer I/O layer.
- **Jobs compute-only** — Data Source row and Pennsieve/XNAT wizard removed from Jobs;
  use **Transfer** for platform data, then submit from Jobs.
- **Transfer → Jobs** — **Open in Jobs** prefills path and compute after a transfer.
- **Path mismatch warnings** — alert before submit when path does not match compute backend.
- **Per-tab SSH panels** — Remote Server vs HPC connect copy under Compute.

## Upgrade

Install the latest desktop build, then **NeuroInsight → Settings → Stop engine → Start
engine** so the workspace pulls `ghcr.io/phindagijimana/nir-allinone:v0.1.24`.

See [TRANSFER.md](TRANSFER.md) for the full route matrix and env vars.
