# NeuroInsight v0.1.17

Patch release — **local file picker + host path visibility for Local Docker jobs**.

## Install
Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM. First launch downloads the
engine image (~1.8 GB) once.

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.17-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.17.exe` |
| Linux | `NeuroInsight-0.1.17.AppImage` / `.deb` |

Verify downloads: [INSTALL.md](INSTALL.md).

## Highlights
**Added**
- **Choose… button for local inputs (desktop)** — opens your OS file picker (Finder /
  Explorer / native dialog) instead of requiring a pasted path or browsing only
  `./data`.
- **Engine sees files under your home directory** — Local Docker jobs can use paths
  like `~/Documents/...`. macOS also mounts `/Volumes/...` for external drives.

**Fixed**
- **"Input file not found"** when submitting a valid file on your machine — the
  engine container previously only saw `~/.nir/data`.

## Upgrade notes
- After installing, **restart the engine** once (**Settings → Engine → Restart engine**)
  so the new home-directory mount is applied.
- **Choose…** appears on the Jobs page when **Local** is selected as the data source.
- Paths must still be on drives Docker can access (your user profile; macOS external
  drives under `/Volumes`). Network shares may need files copied locally first.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
