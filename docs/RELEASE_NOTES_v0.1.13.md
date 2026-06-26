# NeuroInsight v0.1.13

Quality release — **cleaner UI**, **plugin/connection fixes**, and the licenses
panel in the right place for both desktop and web.

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.13-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.13.exe` |
| Linux | `NeuroInsight-0.1.13.AppImage` / `.deb` |

> **Unsigned builds:** first open → macOS **right-click → Open** (Sequoia:
> **System Settings → Privacy & Security → Open Anyway**); Windows
> **More info → Run anyway**. Verify with `desktop-release-sha256-<platform>.txt`.

## Highlights
**Fixed**
- **Boolean plugin parameters now apply** on every backend (local/HPC/remote) —
  e.g. dcm2niix `compress` now produces `.nii.gz` (was silently ignored).
- **Remote Docker backend runs single-plugin jobs** — entrypoint override +
  recursive directory-input upload (verified with dcm2niix on a real server).

**Changed**
- **Cleaner UI** — verbose explanatory text moved into the User Guide; a
  **User Guide** link is in the control center. Connect forms, viewer, jobs, and
  docs are trimmed to concise labels.
- **Tool licenses** (FreeSurfer/MELD) live in the control center on desktop, and
  in a **Settings** tab on web deployments (no control center in a browser).
- **macOS app icon** sized to Apple's grid (no longer oversized in the Dock).

## Notes
- Functionally builds on 0.1.12 (which fixed the macOS launch crash).
- HPC connections support key-based **and** password+Duo (via the host SSH broker);
  connect your VPN first if the cluster is on a private network.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
