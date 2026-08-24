# NeuroInsight v0.1.22

Jobs page layout restored to the classic stacked flow with a two-column submit panel.

## Install

Download for your platform from the GitHub release, or use **Help → Check for Updates**
from v0.1.21.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.22-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.22.exe` |
| Linux | `NeuroInsight-0.1.22.AppImage` / `.deb` |

## Highlights

- **Jobs page** — Process MRI Data submit form on top; stats strip, SLURM queue, and
  jobs list stacked full-width below (not side-by-side).
- **Submit layout** — left: data/compute source + Single/Batch input browser;
  right: pipeline/workflow picker + resource configuration.
- **Job rows** — subject-first labels, ID/compute/runtime, input/output Copy/Finder
  bars, and progress at 100% for completed jobs.
- **Scroll caps** — jobs list and SLURM table share `min(24rem, 55vh)`; file browsers
  stay compact with `nir-scroll-list`.

## Upgrade from v0.1.21

Install the DMG or use in-app update. On first launch the engine pulls
`ghcr.io/phindagijimana/nir-allinone:v0.1.22`. If the UI looks unchanged after
updating the desktop app alone, use **Control Center → Stop/Start engine** or
`./research start` from a git checkout.
