# NeuroInsight documentation

**NeuroInsight** orchestrates neuroimaging pipelines: **Transfer** data, **Jobs**
submit containerized analysis, monitor execution on **local Docker**, **remote
SSH**, or **HPC/SLURM**.

Developed by **Philbert Ndagijimana** with **URMC researchers and neurologists**;
deployed at URMC as **clinical support for Radiology**.

## New here?

1. **[Install the desktop app](INSTALL.md)** — Docker Desktop + first launch  
2. **[How NeuroInsight works](HOW_IT_WORKS.md)** — Transfer, Jobs, backends (read this first)  
3. **[10-minute tour](USER_GUIDE.md#10-minute-path)** — your first Transfer → Jobs flow  
4. **[Troubleshooting](TROUBLESHOOTING.md)** if something fails  

## I want to…

| Goal | Page |
|------|------|
| Understand the product | [Product overview](PRODUCT.md) |
| Check OS / HPC / Pennsieve limits | [Compatibility](COMPATIBILITY.md) |
| Move data (Pennsieve, XNAT, HPC) | [Transfer guide](TRANSFER.md) |
| Submit pipelines on HPC | [HPC pipeline layouts](HPC_PIPELINE_SUBMISSION_GUIDE.md) + [User guide](USER_GUIDE.md) |
| URMC / clinical context | [Clinical support](CLINICAL_SUPPORT.md) |
| Cite methods | [References](REFERENCES.md) |
| Extend the codebase | [Engineering overview](ENGINEERING.md) |

## Typical workflow

```mermaid
flowchart LR
  A[Data source] --> B[Transfer]
  B --> C[Staged path on compute]
  C --> D[Jobs: plugin or workflow]
  D --> E[Logs & outputs]
  E --> F[Optional Transfer out]
```

**Data sources / sinks:** Local disk, Remote Server (SSH), HPC (SLURM), Pennsieve, XNAT.

!!! note
    NeuroInsight **stages** data on the compute backend. It does not run FreeSurfer,
    fMRIPrep, etc. on Pennsieve/XNAT in place — you transfer, then submit Jobs on the
    staged path.

## Download

Desktop installers and the engine Docker image are on
[GitHub Releases](https://github.com/phindagijimana/neuroinsight_research/releases).
