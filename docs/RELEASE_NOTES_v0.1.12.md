# NeuroInsight v0.1.12

Patch release — **macOS app-icon polish**. No functional changes from 0.1.11.

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.12-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.12.exe` |
| Linux | `NeuroInsight-0.1.12.AppImage` / `.deb` |

> **Unsigned builds:** first open → macOS **right-click → Open** (on macOS 15
> Sequoia: **System Settings → Privacy & Security → Open Anyway**); Windows
> **More info → Run anyway**. Verify with `desktop-release-sha256-<platform>.txt`.

## Highlights
**Fixed**
- **macOS app icon sizing** — the Dock/Finder icon was full-bleed and rendered
  larger than neighboring apps; it now follows Apple's icon grid (~80% body with
  transparent margin) so it matches other apps.

## Notes
- Functionally identical to 0.1.11 (which fixed the macOS launch crash).
- HPC clusters that require **Duo/MFA** are not yet supported (key-based SSH
  works); interactive-MFA support is designed and planned.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
