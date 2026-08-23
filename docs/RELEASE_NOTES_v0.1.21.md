# NeuroInsight v0.1.21

Workspace UI polish — **classic layout**, **compact panels**, and **scrollable lists**.

## Install

Download for your platform from the GitHub release, or use **Help → Check for Updates**
from v0.1.20.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.21-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.21.exe` |
| Linux | `NeuroInsight-0.1.21.AppImage` / `.deb` |

## Highlights

- **Top navigation** — Home, Jobs, Results, Viewer, Transfer, Docs (sidebar removed from default flow).
- **Jobs page** — classic vertical layout; pipeline/workflow dropdowns; resources and SSH collapsed until needed.
- **Scrollable lists** — job list, file browsers, SLURM queue, transfer history, and provenance blocks cap height instead of stretching the page.
- **Results** — Statistics / Files / QC tabs; provenance in a collapsed accordion (lazy-loaded).
- **Viewer & Transfer** — tighter headers; Pennsieve agent status as a compact chip.

## Upgrade from v0.1.20

Install the DMG or use in-app update. On first launch the engine pulls
`ghcr.io/phindagijimana/nir-allinone:v0.1.21`. If the UI looks unchanged after
updating the desktop app alone, use **Control Center → Stop/Start engine** or
`./research start` from a git checkout.
