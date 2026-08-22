# NeuroInsight v0.1.15

Bugfix release — **macOS Docker/Node/npm detection on normal double-click launch**.

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.15-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.15.exe` |
| Linux | `NeuroInsight-0.1.15.AppImage` / `.deb` |

Verify downloads: [INSTALL.md](INSTALL.md).

## Highlights
**Fixed**
- **Preflight finds Docker (and Node/npm/Celery) when launched from Finder/Dock/DMG**
  on macOS. GUI apps inherit a stripped `PATH` without `/usr/local/bin` or
  `/opt/homebrew/bin`, so v0.1.14 wrongly reported "Docker is not running" even
  with Docker Desktop up. v0.1.15 augments `PATH` at startup so checks and spawns
  work on a normal double-click — no Terminal workaround needed.

## Upgrade notes
- Drag **NeuroInsight.app** from the DMG into **/Applications** before first launch
  (avoids macOS App Translocation from a read-only DMG path).
- If you are on v0.1.14+, **Help → Check for Updates…** may offer this build once
  the release is published.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
