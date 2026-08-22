# NeuroInsight v0.1.16

Patch release — **macOS Dock icon sizing fix**.

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.16-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.16.exe` |
| Linux | `NeuroInsight-0.1.16.AppImage` / `.deb` |

Verify downloads: [INSTALL.md](INSTALL.md).

## Highlights
**Fixed**
- **macOS Dock icon no longer looks oversized** — the app was overriding the
  padded `icon.icns` (Apple's icon grid) with a full-bleed `icon.png` on every
  launch. Packaged builds now use the bundle `.icns` as intended.

## Upgrade notes
- Drag **NeuroInsight.app** from the DMG into **/Applications** before first launch
  (avoids macOS App Translocation from a read-only DMG path).
- If you are on v0.1.14+, **Help → Check for Updates…** may offer this build once
  the release is published.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
