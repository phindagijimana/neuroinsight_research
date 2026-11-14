# TRACK-TBI deployment

NeuroInsight was used to **run and operationalize** neuroimaging processing for the
**TRACK-TBI** study at scale: **600 subjects**, each with **two timepoints**, on
institutional HPC via the platform’s **Transfer**, **Jobs**, and **SLURM** backends.

## Collaboration (DoD)

The **TRACK-TBI** effort under this **Department of Defense (DoD)** project is a
**collaboration between the University of Rochester** (including URMC and CIRC HPC
use) **and the University of Pennsylvania** research labs. NeuroInsight supported
cohort-scale orchestration in the Rochester/CIRC environment; scientific direction,
data, and deliverables reflect the **joint UR–Penn** program described in the
**TRACK-TBI DoD technical report**.

Developed by **Philbert Ndagijimana** with **URMC researchers and collaborators**.
UR clinical-support context: [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md).

## What NeuroInsight provided

| Role | Description |
|------|-------------|
| **Workflow orchestration** | Batch submission, monitoring, and reproducible reruns across hundreds of subjects |
| **HPC integration** | Staging paths on cluster storage, Apptainer/Singularity jobs, queue and log visibility |
| **Study-scale logistics** | Moving data between compute and study storage without per-subject manual cluster scripting |

The **TRACK-TBI processing workflow** (pipeline steps, parameters, and packaging
for handoff) was **documented and delivered** as one of the **technical deliverables**
in the **TRACK-TBI Department of Defense (DoD) technical report**.

NeuroInsight is the **platform that executed and supported** that workflow at
cohort scale; primary neuroimaging methods (e.g. structural MRI tools in the
workflow) remain subject to their **own citations and licenses** —
[REFERENCES.md](REFERENCES.md), [TOOL_LICENSES.md](TOOL_LICENSES.md).

## Scope and limitations

- This page describes **documented research use** under TRACK-TBI; it is **not** a
  DoD endorsement of NeuroInsight as a medical device.
- **600 × 2 timepoints** reflects study scale on the platform; individual QA and
  scientific interpretation follow TRACK-TBI and **University of Rochester / University
  of Pennsylvania** study governance.
- For lesion-aware / FastSurfer TBI recon conventions (standalone fill vs native
  `--lesion_mask`, post-hoc LIT packaging), implementation details live with the
  study workflow deliverable and plugin/container definitions in this repository
  (`plugins/fastsurfer.yaml`, related tooling).

## Related documentation

- [How NeuroInsight works](HOW_IT_WORKS.md) — Transfer → Jobs model
- [HPC pipeline submission](HPC_PIPELINE_SUBMISSION_GUIDE.md)
- [URMC clinical support](CLINICAL_SUPPORT.md)
- [Citing NeuroInsight](REFERENCES.md)
