# NeuroInsight v0.1.25

Infrastructure reliability (MinIO, Pennsieve), transfer UI improvements, HPC SLURM
hardening, and product/engineering documentation.

## Install

| Platform | File |
|---|---|
| macOS (Apple Silicon / Intel) | `NeuroInsight-0.1.25-arm64.dmg` (or x64 build per release assets) |
| Windows | `NeuroInsight-Setup-0.1.25.exe` |
| Linux | `NeuroInsight-0.1.25.AppImage` / `.deb` |

Engine image: `ghcr.io/phindagijimana/nir-allinone:v0.1.25`

> **Maintainers:** publish `nir-v0.1.25` before `desktop-v0.1.25` — [RELEASING.md](RELEASING.md).
> If GitHub **Latest** still shows v0.1.24, installers for 0.1.25 are pending that tag push.

## Highlights

### Engine & Pennsieve (0.1.25)
- **MinIO** — engine image uses Chainguard MinIO (upstream `dl.min.io` / legacy Docker Hub image breakage).
- **All-in-one build** — frontend built on native platform (fixes arm64 QEMU/esbuild failures).
- **Pennsieve uploads** — agent bundled in amd64 all-in-one image; default agent port **11235** (avoids MinIO on 9000); auto-provision agent profile from API credentials.

### Transfer & UI (since v0.1.24, on `main`)
- **Multi-host connections** — backend support for simultaneous connector/SSH contexts.
- **Transfer UI** — connections rail and per-pane connection picker.

### HPC / SLURM (on `main`)
- SLURM time limit formatting, partition/GPU resolution, `sbatch --test-only` preflight, FastSurfer CPU/GPU profile alignment — for site-specific clusters (e.g. CIRC/BlueHive).

### Documentation
- **[ENGINEERING.md](ENGINEERING.md)**, **[PRODUCT.md](PRODUCT.md)**, **[COMPATIBILITY.md](COMPATIBILITY.md)**
- **[CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md)** — URMC Radiology context
- **[REFERENCES.md](REFERENCES.md)** — generated plugin citations
- Streamlined [README.md](../README.md) and doc index

## Upgrade

**Help → Check for Updates…** (macOS) or install from
[Releases](https://github.com/phindagijimana/neuroinsight_research/releases) when
`desktop-v0.1.25` is published.

After updating: **Settings → Stop engine → Start engine → Open Workspace**.

Pennsieve upload users on desktop: confirm Docker is running; on Apple Silicon see
[COMPATIBILITY.md](COMPATIBILITY.md).

## Full changelog

[CHANGELOG.md](../CHANGELOG.md) · prior: [RELEASE_NOTES_v0.1.24.md](RELEASE_NOTES_v0.1.24.md)
