# URMC deployment & clinical support

!!! warning "Output use"
    **All outputs: research use only.** **Clinical support** use is on the
    **user’s responsibility** — [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md).

NeuroInsight was **developed by Philbert Ndagijimana** in **collaboration with
URMC researchers and neurologists**. It is **deployed as a production orchestration
platform** at the **University of Rochester Medical Center (URMC)**. It runs
workflows that can **support Radiology and Neurology** (quantitative pipelines under
institutional programs) — coordinating transfer, staging, and compute across local
workstations, XNAT, and HPC (SLURM).

NeuroInsight does **not** replace radiologists, neuroradiologists, or neurologists.
It **automates the technical pipeline**. **Outputs are for research use only**; any
**clinical support** use is **the user’s responsibility** —
[RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md).

## Use cases (workflows)

URMC runs **multiple workflows** on NeuroInsight — **AI / deep-learning pipelines**
and **classical** neuroimaging tools as **clinical support** tooling (orchestration
only — see output policy above).

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

- **All outputs: research use only.** **Clinical support** use only on **user/
  institution responsibility** — [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md).
- NeuroInsight is **research and workflow software** (MIT license for this repository).
  Any activity at URMC must follow **IRB**, contracts, and institutional policy.
- Output from containerized tools (FreeSurfer, MELD, fMRIPrep, etc.) remains
  **research output**; cite those tools as required — [TOOL_LICENSES.md](TOOL_LICENSES.md),
  [REFERENCES.md](REFERENCES.md).
- This document describes **documented deployment context**; it is **not** a
  regulatory clearance or “FDA-approved device” statement.

## Citing NeuroInsight in URMC-related work

When describing the platform in manuscripts, grants, or internal reports, cite
NeuroInsight and the underlying pipelines — see **Citing NeuroInsight** in
[REFERENCES.md](REFERENCES.md) and [CITATION.cff](../CITATION.cff).
