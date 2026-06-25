# NeuroInsight v0.1.9

Desktop app for running neuroimaging pipelines locally or on HPC — your data
stays on your machine. This is a **pilot** release.

## Install

Download the installer for your platform below, then see the
[install guide](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).

| Platform | File |
|---|---|
| macOS | `NeuroInsight-0.1.9.dmg` |
| Windows | `NeuroInsight-Setup-0.1.9.exe` |
| Linux | `NeuroInsight-0.1.9.AppImage` / `.deb` |

**Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/)** (or
Docker Engine on Linux), ~20 GB free disk, and 8 GB+ RAM. On first launch the app
downloads its engine image (~1.8 GB) once.

> **These builds are not code-signed.** They're safe — verify with the
> `desktop-release-sha256-<platform>.txt` checksum file (below) — but your OS
> shows a one-time prompt on first open:
> - **macOS:** right-click the app → **Open → Open** (once).
> - **Windows:** SmartScreen → **More info → Run anyway**.
> - **Linux:** no prompt.

### Verify your download
```bash
# macOS / Linux — use the checksum file matching your installer
shasum -a 256 -c desktop-release-sha256-macos.txt   # or -linux.txt
```

## Highlights

**New**
- Workspace **launchpad** home: quick actions, recent jobs, and engine status.
- App-wide **toasts + confirm dialogs**, consistent status badges, and unified
  loading states.
- Local **crash/error capture** with an exportable diagnostics bundle.

**Improved**
- Cleaner, more professional naming and copy across pages, plugins, and workflows
  (e.g. "Dashboard" → **Results**); calmer labels; decluttered **Settings**.
- Clearer first-run: engine image download now shows progress on the splash.

**Security & reliability**
- Each install generates **unique local credentials** (Redis / MinIO / secret key).
- The engine binds to **localhost only**; do not expose it to the internet.
- Download **checksums** (`SHA256SUMS.txt`) plus an in-app integrity self-check.

**Under the hood**
- Single source-of-truth versioning; green CI (type-check, tests with a coverage
  floor, security scan); end-user install guide and release runbook.

## Known limitations
- Builds are unsigned (see note above).
- Docker Desktop is required.
- Licensing UI is deferred (not needed for this pilot).

---
Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
