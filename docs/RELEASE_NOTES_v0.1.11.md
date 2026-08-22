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

Verify downloads: [INSTALL.md](INSTALL.md) (checksum files on the GitHub Release).

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
