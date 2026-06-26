# NeuroInsight v0.1.11

Patch release — **fixes a launch crash** on macOS so the app reliably opens.
Pilot, unsigned (see the install note below).

> **Upgrade required over 0.1.10.** 0.1.10 could crash on launch (the auto-update
> check tried to download a non-existent `.zip` and the error killed the app).

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.11-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.11.exe` |
| Linux | `NeuroInsight-0.1.11.AppImage` / `.deb` |

> **Unsigned builds:** first open → macOS **right-click → Open** (on macOS 15
> Sequoia: **System Settings → Privacy & Security → Open Anyway**); Windows
> **More info → Run anyway**.

## Verify your download (integrity for unsigned builds)
The build is unsigned, so verify the checksum after downloading. Compare against
`desktop-release-sha256-<platform>.txt` attached to this release:

```bash
# macOS
shasum -a 256 NeuroInsight-0.1.11-arm64.dmg
# Linux
sha256sum NeuroInsight-0.1.11.AppImage
```
```powershell
# Windows (PowerShell)
Get-FileHash .\NeuroInsight-Setup-0.1.11.exe -Algorithm SHA256
```
The printed hash must match the line for your file in the checksum file.

## Highlights
**Fixed**
- **Launch crash on macOS** — the startup update-check no longer auto-downloads;
  it only checks and logs availability, so a dmg-only unsigned release can't
  surface the `ZIP file not provided` error. The mac build also emits a `zip`
  target so signed auto-update works once signing is enabled.

## Notes
- HPC clusters that require **Duo/MFA** are not yet supported (key-based SSH
  works); interactive-MFA support is designed and planned.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
