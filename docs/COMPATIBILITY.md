# Compatibility matrix

What NeuroInsight **officially targets** and known **platform limits**. For
install steps see [INSTALL.md](INSTALL.md); for product scope see [PRODUCT.md](PRODUCT.md).

## Desktop host (orchestration UI + engine)

| | macOS | Windows | Linux |
|---|--------|---------|--------|
| **Supported versions** | 12+ (Apple Silicon & Intel) | 10/11 64-bit | x86-64, arm64 distros with Docker Engine |
| **Docker** | Docker Desktop required | Docker Desktop (WSL2 backend) | Docker Engine + Compose v2 |
| **Installer** | `.dmg` (signed/notarized when CI secrets set) | `.exe` (may be unsigned — SmartScreen) | `.AppImage` / `.deb` |
| **Engine image pull** | amd64 or arm64 multi-arch | amd64 | amd64 / arm64 |
| **Local heavy MRI** (FreeSurfer, fMRIPrep) | Works; **slower** — give Docker 16 GB+ RAM | Works via WSL2/Docker Desktop | **Recommended** for local processing |
| **Orchestration-only** (HPC/remote jobs) | **Recommended** use on Mac | Supported | Supported |

## Compute backends

| Backend | Requirements | Notes |
|---------|----------------|-------|
| **Local Docker** | Docker on same machine as backend | Plugin images pulled on demand; disk hungry |
| **Remote Docker** | SSH + Docker on Linux host | NeuroInsight server SSH key on remote |
| **HPC / SLURM** | SSH to login node; `sbatch`; Apptainer/Singularity on cluster | Partition names, GPU, timelimits are **site-specific** — [USER_GUIDE.md](USER_GUIDE.md) § HPC |
| **MFA / Duo** | Password (and 2FA) via Jobs SSH panel | Key-only clusters: use key auth per guide |

SLURM job generation: `backend/execution/slurm_backend.py` (time format, partition, `--gres`).

## Connectors

| Connector | Browse / download | Upload / staging | Architecture notes |
|-----------|-------------------|------------------|---------------------|
| **Pennsieve** | All platforms | Agent/CLI on **backend host** | Desktop all-in-one bundles agent on **amd64 only**; Apple Silicon uploads need amd64 engine or CLI on PATH — [TRANSFER.md](TRANSFER.md) |
| **XNAT** | Yes | Upload via platform APIs | TLS skip for SSH tunnels documented in USER_GUIDE |
| **Local / Remote / HPC paths** | SFTP / `cp` where applicable | Same | Large-file resume: TRANSFER.md |

Default Pennsieve agent port avoids MinIO (`11235`, auto-bump on conflict) — v0.1.25+.

## Tooling (from source)

| Component | Version |
|-----------|---------|
| Python | 3.9+ (CI uses 3.10) |
| Node.js | 18+ |
| PostgreSQL / Redis / MinIO | Via `./research infra` (dev); all-in-one image in desktop |

## Pipeline / container images

Each plugin declares a **Docker** image in YAML. On HPC, images are typically
**Apptainer `.sif`** converted from the same registries. GPU plugins (FastSurfer GPU,
some ML steps) require a **GPU partition** and matching image variant.

FreeSurfer and MELD require **license files** — [TOOL_LICENSES.md](TOOL_LICENSES.md).

## Not supported

- Exposing the NeuroInsight API on the public internet **without** your own auth layer
- Multi-tenant SaaS on a single unauthenticated instance
- In-place reads from Pennsieve/XNAT without staging to compute paths
- Guaranteed compatibility with every SLURM site without configuration/testing

## Testing matrix (maintainers)

CI (`.github/workflows/ci.yml`): backend pytest, frontend build, Docker image build on `main`.
Release smoke: [RELEASING.md](RELEASING.md) fresh-machine checklist.

Report compatibility gaps via **phindagijimana@gmail.com** with OS, NeuroInsight
version, backend (local/HPC), and connector used.
