# NeuroInsight — product overview

**Developed by Philbert Ndagijimana** with **URMC researchers and neurologists.**

NeuroInsight is neuroimaging **orchestration software**: move data, submit
containerized pipelines, and monitor jobs — without writing cluster scripts for
every study. At URMC it supports **Radiology** workflows (see
[CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md)).

## What it is

| | |
|---|---|
| **Primary use** | Transfer → Jobs → optional Transfer back |
| **Compute** | Local Docker, remote SSH + Docker, HPC/SLURM + Apptainer |
| **Data platforms** | Pennsieve, XNAT (plus local/remote/HPC paths) |
| **Delivery** | Desktop app (macOS, Windows, Linux) or run from source |
| **License** | MIT (this repo); FreeSurfer/MELD and others — [TOOL_LICENSES.md](TOOL_LICENSES.md) |

NeuroInsight is **not** a PACS, not an AI diagnostic device, and **not** a
substitute for clinical reads. It runs and tracks pipelines; clinicians interpret
outputs.

## Supported capabilities

- **Plugins** — single tools (FreeSurfer, FastSurfer, fMRIPrep, QSIPrep, MELD, EEG/MNE steps, …)
- **Workflows** — chained steps (e.g. fMRIPrep → XCP-D, multimodal epilepsy biomarker)
- **Transfer** — all pairwise routes among Local, Remote, HPC, Pennsieve, XNAT ([TRANSFER.md](TRANSFER.md))
- **Viewer** — NIfTI and overlays in the workspace
- **Documentation in-app** — Docs tab reflects `plugins/` and `workflows/` YAML

Platform and architecture limits: **[COMPATIBILITY.md](COMPATIBILITY.md)**.

## Who it is for

- **Neuroradiology / neurology research** teams staging MRI, EEG, and multimodal studies
- **Imaging scientists** submitting to institutional HPC
- **Engineers** extending YAML plugins and connectors — [ENGINEERING.md](ENGINEERING.md)

## Version and releases

- Current source version: `VERSION` at repo root (e.g. **0.1.25**).
- **Desktop installers** ship on [GitHub Releases](https://github.com/phindagijimana/neuroinsight_research/releases) (`desktop-v*` tags).
- **Engine image:** `ghcr.io/phindagijimana/nir-allinone:v<version>` (`nir-v*` tags).

Release process: [RELEASING.md](RELEASING.md). Latest notes: [RELEASE_NOTES_v0.1.25.md](RELEASE_NOTES_v0.1.25.md).

## Support model

| Level | What you get |
|-------|----------------|
| **Self-serve** | [INSTALL.md](INSTALL.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), [USER_GUIDE.md](USER_GUIDE.md) |
| **Issues / questions** | **Philbert Ndagijimana** — phindagijimana@gmail.com |
| **Institutional (URMC-style)** | Site-specific HPC partitions, XNAT URLs, and license files are configured by your team; NeuroInsight does not operate your cluster |

There is **no commercial SLA** in the open-source distribution. Optional desktop
license tiers are documented in `desktop/ops/LICENSING_OPERATIONS.md` for pilot
partners.

## Supported vs experimental

| Area | Status |
|------|--------|
| Desktop install + local Docker jobs | **Supported** — primary path |
| Transfer large files (resume, skip complete) | **Supported** |
| HPC/SLURM + Singularity | **Supported** — cluster-specific tuning may be required |
| Pennsieve download | **Supported** (all architectures) |
| Pennsieve upload (desktop engine) | **Supported on amd64**; limited on Apple Silicon — see [COMPATIBILITY.md](COMPATIBILITY.md) |
| XNAT | **Supported** (incl. tunnel / skip-SSL options in guide) |
| EEG multimodal workflows | **Supported** in repo; heaviest staging/HPC assumptions — [HPC_PIPELINE_SUBMISSION_GUIDE.md](HPC_PIPELINE_SUBMISSION_GUIDE.md) |

Features at **0.1.x** may change between minor releases. Check CHANGELOG before upgrading.

## Documentation map

| Doc | Purpose |
|-----|---------|
| [PRODUCT.md](PRODUCT.md) | This page |
| [COMPATIBILITY.md](COMPATIBILITY.md) | OS, arch, connectors |
| [ENGINEERING.md](ENGINEERING.md) | Technical onboarding |
| [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) | URMC deployment context |
| [REFERENCES.md](REFERENCES.md) | Methods citations |

Full index: [README.md](README.md).
