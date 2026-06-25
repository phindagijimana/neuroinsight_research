# NeuroInsight v0.1.10

Patch release — **fixes local processing** and improves SSH/remote connections.
Pilot, unsigned (see the install note below).

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.10-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.10.exe` |
| Linux | `NeuroInsight-0.1.10.AppImage` / `.deb` |

> **Unsigned builds:** first open → macOS **right-click → Open**; Windows
> **More info → Run anyway**. Verify with `desktop-release-sha256-<platform>.txt`.

## Highlights
**Fixed**
- **Local jobs now run** — a crash broke every local Docker pipeline in 0.1.9.
- The app reliably restarts after a force-quit/crash (stale Postgres lock cleared).
- Saved SSH hosts resolve correctly (container `HOME` fix).

**Added**
- **Connect to remote/HPC by saved host** — pick an alias from your
  `~/.ssh/config` instead of typing host/user/port.
- Faster, multiplexed SSH (ControlMaster) under the hood.

## Notes
- **Upgrade strongly recommended over 0.1.9** (0.1.9 can't run local jobs).
- HPC clusters that require **Duo/MFA** are not yet supported (key-based SSH
  works); interactive-MFA support is designed and planned.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
