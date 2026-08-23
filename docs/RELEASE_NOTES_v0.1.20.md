# NeuroInsight v0.1.20

Hotfix — **desktop auto-update download**.

## Install

Download for your platform from the GitHub release, or use **Help → Check for Updates**
from v0.1.18/v0.1.19 once this build is installed.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.20-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.20.exe` |
| Linux | `NeuroInsight-0.1.20.AppImage` / `.deb` |

## Fixed

- **Auto-update download** — the app no longer offers “Download & Install” unless an
  update is actually available, and re-checks before downloading. Fixes the error:
  `Please check update first`.

## Upgrade from v0.1.19

If in-app update failed on v0.1.19, install the v0.1.20 DMG (or run Check for Updates
from v0.1.18). No engine migration required — restart the engine once after updating
if the UI looks stale.
