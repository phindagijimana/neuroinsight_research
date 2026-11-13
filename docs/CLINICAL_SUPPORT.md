# Clinical support use (URMC)

NeuroInsight was **developed by Philbert Ndagijimana** in **collaboration with
URMC researchers and neurologists**. It is **deployed as a production orchestration
platform** at the **University of Rochester Medical Center (URMC)**. It runs
neuroimaging **workflows that serve as clinical support tools for Radiology** —
coordinating transfer, staging, and compute across local workstations,
institutional storage (including XNAT), HPC (SLURM), and containerized analysis
plugins.

NeuroInsight does **not** replace the radiologist or neuroradiologist. It **automates
the technical pipeline** around studies that Radiology and related services use for
readings, research–clinical translation, and quantitative neuroimaging support.

## What runs in practice

At URMC, typical uses include:

| Capability | Role for Radiology |
|------------|-------------------|
| **Structural MRI** (FreeSurfer, FastSurfer, hippocampal subfields / SegmentHA) | Volumetry, segmentation, and longitudinal templates for interpretation support |
| **Lesion & FCD workflows** (e.g. Cortical Lesion Detection → MELD Graph) | Quantitative surface-based analysis to support epilepsy and lesion-related reads |
| **Hippocampal sclerosis (HS) workflow** | Asymmetry, lateralization, and QC overlays to support temporal-lobe epilepsy imaging review |
| **Transfer + Jobs** | Move data between **local**, **HPC**, **Pennsieve**, and **URMC XNAT** (`xnat.urmc.rochester.edu`), then submit compute on staged paths without manual cluster scripting |
| **Multimodal epilepsy biomarker workflow** (EEG + MRI) | Chained EEG/MRI steps for research and translational clinical support where multimodal evidence is needed |

Exact plugins and workflows in your environment match those in the **Docs** page in
the app and the definitions under `plugins/` and `workflows/` in this repository.

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
