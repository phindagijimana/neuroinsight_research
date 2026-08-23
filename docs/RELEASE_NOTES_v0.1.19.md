# NeuroInsight v0.1.19

Minor release — **desktop workspace UX, subject-first jobs, Finder/Transfer path open,
Viewer file drawer**.

## Install

Download for your platform, then see
[docs/INSTALL.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/docs/INSTALL.md).
Requires **Docker Desktop**, ~20 GB free, 8 GB+ RAM (16 GB+ recommended for FreeSurfer).

| Platform | File |
|---|---|
| macOS (Apple Silicon) | `NeuroInsight-0.1.19-arm64.dmg` |
| Windows | `NeuroInsight-Setup-0.1.19.exe` |
| Linux | `NeuroInsight-0.1.19.AppImage` / `.deb` |

Verify downloads: [INSTALL.md](INSTALL.md).

## Highlights

**Added**
- **Workspace sidebar** — Jobs, Results, Viewer, Transfer, Docs with live engine
  status; desktop opens on Jobs.
- **Subject-first job identity** — labels like `sub-001 · ses-1`, searchable Jobs
  list, human-readable output folders (`sub-001_fs_76625681`).
- **Open paths from the app** — click input/output on Jobs or Results to open in
  **Finder** (local) or **Transfer** (HPC, remote, XNAT, Pennsieve).
- **Results** — Statistics tab first; compact job summary; no UUID in the picker.
- **Viewer** — collapsible left file drawer; compact imaging controls; subject context
  bar.
- **Pipeline catalog** — 13 selectable plugins by default; utilities hidden unless
  toggled on.

**Changed**
- Control Center, Jobs submission (searchable pipeline picker), and page headers
  polished for daily desktop use.

**Fixed**
- Output paths resolve to host `~/.nir/data/outputs/…` for local Docker jobs.
- Jobs with false early “Failed” status keep auto-refreshing for up to 12 hours.

## Upgrade notes

1. Install v0.1.19 and **restart the engine** once so the updated UI and API fields
   load cleanly.
2. **New output folders** use subject-based names; older jobs still use UUID folders
   on disk — both work; use the path bar or Copy to locate either.
3. In **Viewer**, use the **Files** drawer on the left to pick volumes; collapse it
   for maximum canvas space.

Full changelog:
[CHANGELOG.md](https://github.com/phindagijimana/neuroinsight_research/blob/main/CHANGELOG.md)
