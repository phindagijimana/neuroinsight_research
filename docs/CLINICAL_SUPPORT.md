# Clinical support use (URMC)

NeuroInsight was **developed by Philbert Ndagijimana** in **collaboration with
URMC researchers and neurologists**. It is **deployed as a production orchestration
platform** at the **University of Rochester Medical Center (URMC)**. It runs
neuroimaging **workflows that serve as clinical support tools for Radiology** —
coordinating transfer, staging, and compute across local workstations,
institutional storage (including XNAT), HPC (SLURM), and containerized analysis
plugins.

NeuroInsight does **not** replace radiologists, neuroradiologists, or neurologists.
It **automates the technical pipeline** around studies that **Radiology** and
**Neurology** use for quantitative neuroimaging support.

## Use cases (workflows)

URMC runs **multiple workflows** on NeuroInsight — **AI / deep-learning pipelines**
and **classical** neuroimaging tools — as **clinical support** (orchestration only).

**→ [USE_CASES.md](USE_CASES.md)** — dedicated tables for **Radiology** and
**Neurology** (workflow IDs, AI vs classical, TRACK-TBI cohort).

At a glance:

- **Radiology:** FastSurfer / FreeSurfer, hippocampal subfields, MELD lesion
  detection, hippocampal sclerosis, fMRI/diffusion BIDS pipelines, TRACK-TBI at scale.
- **Neurology:** EEG epilepsy screening, EEG–MRI source localization, multimodal
  epilepsy biomarker, tuberous sclerosis MRI chain.
- **Platform:** Transfer + Jobs across **local**, **HPC**, **Pennsieve**, **URMC XNAT**
  (`xnat.urmc.rochester.edu`).

Plugin/workflow definitions: in-app **Docs** tab; `plugins/` and `workflows/` in this repo.

## How this relates to published documentation

- **Install & desktop:** [INSTALL.md](INSTALL.md) — same NeuroInsight build used for URMC orchestration (often on macOS hosts submitting to HPC).
- **Connectors:** [USER_GUIDE.md](USER_GUIDE.md) — XNAT, Pennsieve, HPC/SLURM, and remote server setup (including URMC-oriented examples).
- **Pipeline layouts on HPC:** [HPC_PIPELINE_SUBMISSION_GUIDE.md](HPC_PIPELINE_SUBMISSION_GUIDE.md).
- **Methods citations:** [REFERENCES.md](REFERENCES.md) — cite NeuroInsight and each tool you run in publications or reports.

## Important limitations

- NeuroInsight is **research and workflow software** (MIT license for this repository).
  **Clinical use** at URMC is under **institutional policies**, appropriate
  qualifications, and study-/service-specific governance (e.g. IRB, QA, validation
  of each workflow for its intended support role).
- Output from containerized tools (FreeSurfer, MELD, fMRIPrep, etc.) must be
  interpreted by **licensed clinicians**; cite those tools as required by their
  licenses and publications — see [TOOL_LICENSES.md](TOOL_LICENSES.md) and
  [REFERENCES.md](REFERENCES.md).
- This document describes **documented deployment context**; it is **not** a
  regulatory clearance or “FDA-approved device” statement.

## Citing NeuroInsight in URMC-related work

When describing the platform in manuscripts, grants, or internal reports, cite
NeuroInsight and the underlying pipelines — see **Citing NeuroInsight** in
[REFERENCES.md](REFERENCES.md) and [CITATION.cff](../CITATION.cff).
