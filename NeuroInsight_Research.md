# NeuroInsight Research

## An HPC-Native, UI-First Platform for Neuroimaging Pipelines and Visualization

---

## 1. Executive Summary

**NeuroInsight Research** is a local and HPC-native research software platform that enables neuroscientists and clinicians to run complex neuroimaging pipelines and visualize results through a graphical user interface, without relying on terminal workflows or cloud-based services.

### The platform is designed to:

- Run inside **High Performance Computing (HPC)** environments (e.g., via Open OnDemand)
- Run as a **local desktop application** that securely connects to HPC systems using existing user credentials
- Support **DICOM → NIfTI conversion** pipelines
- Run all **downstream pipelines on NIfTI data**
- Provide **high-quality visualization** of anatomical images, segmentations, and quantitative metrics
- Maintain **institutional security and data governance** standards

### The system is built to be pipeline-agnostic, extensible, and reproducible, with a clear separation between:

- Core platform
- Pipeline plugins
- Visualization layer

---

## 2. Problem Statement

Modern neuroimaging pipelines (FreeSurfer, FastSurfer, hippocampal subfield segmentation, lesion detection, etc.) are:

- **Terminal-driven**
- **Error-prone**
- **Difficult to reproduce**
- **Inaccessible** to clinicians and many researchers
- **Poorly integrated** with visualization and reporting

### Existing solutions either:

- Require **cloud upload** of sensitive data
- Focus on **data storage, not execution** (e.g., XNAT)
- Are **visualization-only** (e.g., desktop viewers)
- Demand **advanced systems knowledge** to operate

**NeuroInsight Research** addresses this gap by providing a secure, UI-first execution and visualization platform that runs where the data already lives: **on HPC systems**.

---

## 3. Target Users

- Neuroimaging researchers
- Clinical researchers
- Translational neuroscience labs
- Imaging cores
- Graduate students and postdocs
- Clinicians who need interpretation support (research use)

### Key constraint:
All users already have **authorized HPC access**.

---

## 4. System Overview

NeuroInsight Research operates in **two deployment modes** using the same core codebase.

### 4.1 Deployment Modes

#### Mode 1: Local/Desktop (Primary Focus - Phase 1-3)

**Two operating configurations:**

A. **Fully Local Processing**
- Process MRI data on local machine using Docker
- Upload files from local storage
- Run pipelines in local containers
- View results locally

B. **Remote HPC Access** (via Desktop App)
- Desktop app connects to user's HPC via SSH
- User provides their own HPC credentials (ssh-agent)
- Browse HPC filesystem (data stays on HPC, no upload)
- Submit jobs to SLURM remotely
- Stream results for visualization
- **No institutional partnership required** - users bring their own HPC access

#### Mode 2: HPC-Native (Open OnDemand) (Phase 4)

- Deployed directly on HPC cluster as OOD interactive app
- Runs on compute nodes inside HPC environment
- User authentication inherited from OOD
- Direct SLURM job submission (no SSH)
- Data never leaves HPC
- Best for institutional deployments with PHI data

### 4.2 Core Features (All Modes)

| Feature | Description | Local Mode | HPC-Native Mode |
|---------|-------------|------------|-----------------|
| **Upload Files** | Upload MRI data from local machine | ✅ Yes | ❌ Not needed (data on HPC) |
| **Browse Files** | Navigate filesystem to select inputs | ✅ Local + Remote HPC | ✅ HPC filesystem |
| **Select Pipeline** | Choose from production-ready pipelines | ✅ Yes | ✅ Yes |
| **Submit Jobs** | Execute pipeline with parameters | ✅ Docker or SLURM | ✅ SLURM |
| **Monitor Progress** | Real-time job status and progress | ✅ Yes | ✅ Yes |
| **View Results** | NIfTI viewer, metrics, QC images | ✅ Yes | ✅ Yes |
| **Download Results** | Selective download of outputs | ✅ Yes | ✅ Optional |

### 4.3 Key Design Principle: Data Stays on HPC

**For HPC modes (Remote Desktop or OOD):**
- Input data remains on HPC filesystem
- Processing happens on HPC compute nodes
- Only metadata and visualization slices transferred
- No bulk data upload/download required
- Respects institutional data governance

**For Local mode:**
- Data processed locally using Docker
- No HPC required for development or small-scale use

---

## 5. Development Strategy

### Phase 1: Local Web Platform (Months 1-3) - **CURRENT FOCUS**
- Build web UI with React
- Implement local Docker backend
- Pipeline plugin system
- Core features: upload, submit, monitor, visualize
- **Deliverable:** Working local platform for development and demos

### Phase 2: HPC Backend Integration (Months 4-6)
- SSH connection manager with agent authentication
- SLURM backend implementation
- Remote file browsing
- Test with partner HPC institutions
- **Deliverable:** HPC remote access capability

### Phase 3: Desktop Application (Months 7-9)
- Package web app as Electron/Tauri desktop app
- Backend selection UI (local vs. HPC)
- SSH configuration management
- Cross-platform installers (Windows/Mac/Linux)
- **Deliverable:** Standalone desktop application

### Phase 4: HPC-Native Deployment (Months 10-12)
- Open OnDemand integration
- Deploy as OOD interactive app
- Institutional validation studies
- **Deliverable:** Production HPC deployment

---

## 6. High-Level Architecture

```
┌──────────────────────────────────────────────┐
│           User Interface                     │
│  - File Browser                              │
│  - Pipeline Selector                         │
│  - Job Monitor                               │
│  - NIfTI Viewer                              │
│  - Metrics Dashboard                         │
└────────────────────┬─────────────────────────┘
                     │ REST API
                     │
┌────────────────────▼─────────────────────────┐
│         NeuroInsight Core (FastAPI)          │
│  - Pipeline Registry (YAML-based)            │
│  - Job Management                            │
│  - Result Handling                           │
└────────────────────┬─────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │ Execution Backend     │
         │   (Abstraction Layer) │
         └───────────┬───────────┘
                     │
         ┌───────────┴────────────┐
         │                        │
┌────────▼─────────┐   ┌─────────▼────────────┐
│ Local Backend    │   │  SLURM Backend       │
│                  │   │                      │
│ Docker           │   │ SSH → HPC SLURM      │
│ (Development)    │   │ (Production)         │
└──────────────────┘   └──────────────────────┘
```

### 6.1 Execution Backend Abstraction

The platform uses an **abstraction layer** that allows the same application code to run on different execution environments:

```python
# Common interface for all backends
backend.submit_job(spec)      # Works for Docker or SLURM
backend.get_status(job_id)    # Same API for both
backend.cancel_job(job_id)    # Consistent interface
```

**Benefits:**
- Develop locally with Docker backend (fast iteration)
- Deploy to HPC with SLURM backend (no code changes)
- Switch via configuration: `BACKEND_TYPE=local` or `BACKEND_TYPE=slurm`
- Easy to add new backends (PBS, Kubernetes, Cloud)

---

## 7. Data Flow & Processing

### 7.1 Local Mode Data Flow

```
User's Computer
    ↓
Upload MRI files → Local Storage
    ↓
Submit job → Docker Backend
    ↓
Process in Docker container
    ↓
Results → Local Storage
    ↓
Visualize in UI
```

### 7.2 HPC Mode Data Flow (No Data Movement!)

```
User's Computer (Desktop App)
    ↓
Connect via SSH → User's HPC Account
    ↓
Browse HPC Filesystem → Select existing files
    ↓
Submit job → SLURM Scheduler
    ↓
Process on HPC compute node → Results stay on HPC
    ↓
Stream metadata/slices → Desktop App for visualization
    ↓
Optional: Selective download of specific results
```

**Key Advantage:** Data never leaves HPC during processing, only small metadata and visualization data transferred.

### 7.3 NIfTI-Based Pipelines

**All pipelines operate on NIfTI format:**
- `.nii` / `.nii.gz` files
- Conformed orientation (e.g., RAS)
- Explicit metadata recorded in run manifest

**DICOM Support:**
- DICOM → NIfTI conversion as preprocessing step
- All downstream analysis on NIfTI
- Minimizes PHI risk, simplifies tooling, standardizes visualization

---

## 8. Pipeline Plugin System

NeuroInsight uses a **plugin contract** to integrate pipelines.

### 8.1 Pipeline Plugin Definition

Each pipeline defines:

```yaml
name: hippocampal_sclerosis_detection
version: 1.0.0

inputs:
  - T1w: required
  - FLAIR: optional

parameters:
  threads: default=8
  use_gpu: default=false

resources:
  memory_gb: 32
  time_hours: 6

container:
  image: neuroinsight/hs_detector:1.0.0

command:
  run_hs_pipeline.sh --t1 {T1w} --out {output_dir}

outputs:
  segmentation: outputs/segmentation.nii.gz
  metrics: outputs/metrics.json
  qc: outputs/qc/
```

### 8.2 Benefits

- Easy pipeline addition
- Version-controlled execution
- Reproducibility
- Standard UI integration

### 8.3 Production-Ready Pipelines

**Included:**
- FreeSurfer hippocampal analysis
- FastSurfer (rapid segmentation)
- Hippocampal subfields
- Custom pipeline support via YAML

---

## 9. Result Bundle Specification

All pipelines produce a **standard result bundle**.

```
results/
├── results.json
├── volumes/
│   ├── anatomy.nii.gz
│   ├── segmentation.nii.gz
├── labels.json
├── metrics/
│   ├── metrics.csv
│   ├── metrics.json
├── qc/
│   ├── overlay_axial.png
│   ├── overlay_coronal.png
├── logs/
│   ├── stdout.log
│   ├── stderr.log
└── report/
    └── summary.pdf
```

---

## 10. Visualization Framework

### 10.1 NIfTI Visualization

- Multi-slice views
- Overlay support
- Opacity control
- Crosshair navigation
- Label-based segmentation display

**Segmentations** are treated as integer label maps and colored using `labels.json`.

### 10.2 Metrics & QC Visualization

- Quantitative metrics dashboard (volumes, asymmetry indices)
- Quality control image overlays (PNG/JPEG)
- Interactive charts and graphs
- Comparison across timepoints/subjects

---

## 11. Security Model

### 11.1 Authentication

**Desktop Mode (Remote HPC):**
- Uses user's SSH credentials via `ssh-agent`
- No passwords stored in application
- No private keys accessed by app
- Respects user's `~/.ssh/config`
- **Users bring their own HPC access** - no institutional partnership required

**HPC-Native Mode (OOD):**
- Authentication handled by institutional HPC/OOD
- App inherits user identity from OOD session
- No credential management in app

**Local Mode:**
- No authentication required (single user, local machine)

### 11.2 Authorization & Data Access

- App operates **only within user's permissions**
- No privilege escalation
- No cross-user data access
- Users can only process data they already have access to

### 11.3 Data Security

- **No cloud uploads** - data stays on HPC or local machine
- No external API dependencies
- Restricted filesystem permissions (700 on job directories)
- Minimal local caching (configurable)
- Full audit trail in job logs

### 11.4 PHI Compliance

- Logs exclude protected health information
- Commands, parameters, and versions recorded
- Full provenance in `results.json`
- Optional DICOM anonymization before processing

---

## 12. Monetization & Sustainability

### 12.1 Open-Core Model

**Core platform:** Open source (MIT/Apache license)

**Paid services:**
- Enterprise installation and setup
- Custom pipeline integration
- Training workshops
- Priority support contracts

### 12.2 Institutional Licensing

- Department-level support agreements
- Service level agreements (SLA)
- Custom feature development

### 12.3 Grant & SBIR Funding

- NIH SBIR/STTR funding target
- Translational research focus
- Clinical validation studies
- Strong institutional partnerships

---

## 13. Competitive Positioning

| Platform | HPC-Native | Desktop App | Data on HPC | Pipeline-Agnostic | Open Source |
|----------|------------|-------------|-------------|-------------------|-------------|
| **NeuroInsight Research** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| brainlife.io | Yes | No | Yes | Yes | Yes |
| XNAT | Partial | No | No | Limited | Yes |
| Flywheel | No | No | No | Limited | No |
| FSL-GUI | No | Yes | No | No | Yes |

### Key Differentiators:

1. **Dual deployment:** Works locally AND on HPC with same codebase
2. **No institutional partnership required:** Users connect with their own HPC credentials
3. **Data stays on HPC:** No bulk upload/download, respects data governance  
4. **Desktop + OOD:** Supports both individual researchers and institutional deployments
5. **Execution abstraction:** Easy to develop locally, deploy to production HPC

---

## 14. Implementation Roadmap

### Phase 1: Local Web Platform (Months 1-3) ✅ **IN PROGRESS**

**Focus:** Build and test locally with Docker backend

- [x] Execution backend abstraction layer
- [x] Local Docker backend implementation  
- [x] Pipeline plugin system (YAML-based)
- [x] FastAPI REST API with job management
- [x] Database schema and models
- [ ] React frontend (file upload, job monitoring, visualization)
- [ ] NIfTI slice viewer
- [ ] Metrics dashboard
- [ ] FreeSurfer, FastSurfer, subfield pipelines

**Deliverable:** Working local web platform, demo video, test datasets

---

### Phase 2: HPC Backend Integration (Months 4-6)

**Focus:** Add SLURM backend, test with real HPC

- [ ] SSH connection manager with agent authentication
- [ ] SLURM backend implementation (sbatch, squeue, scancel)
- [ ] Remote file browser (browse HPC via SSH)
- [ ] Job status polling from SLURM
- [ ] Result streaming from HPC
- [ ] Test with partner HPC institution

**Deliverable:** HPC remote access capability, validated on real HPC

---

### Phase 3: Desktop Application (Months 7-9)

**Focus:** Package as standalone desktop app

- [ ] Tauri/Electron wrapper
- [ ] Backend selection UI (local Docker vs. remote HPC)
- [ ] SSH configuration wizard
- [ ] Cross-platform installers (Windows, macOS, Linux)
- [ ] User documentation and tutorials

**Deliverable:** Distributable desktop application

---

### Phase 4: HPC-Native Deployment (Months 10-12)

**Focus:** Open OnDemand integration for institutional deployment

- [ ] OOD interactive app manifest
- [ ] Deploy on compute nodes
- [ ] Institutional authentication integration
- [ ] Multi-institution validation studies
- [ ] Publication in neuroimaging journal

**Deliverable:** Production OOD deployment, peer-reviewed publication

---

## 15. Summary

**NeuroInsight Research** bridges the gap between powerful neuroimaging pipelines and researcher usability.

### Key Advantages:

- ✅ **Two deployment modes:** Local/Desktop (rapid development) + HPC-Native (production)
- ✅ **Data stays on HPC:** No bulk transfers, respects institutional governance
- ✅ **No partnership required:** Users bring their own HPC credentials via desktop app
- ✅ **Execution abstraction:** Same code runs locally (Docker) or on HPC (SLURM)
- ✅ **Pipeline-agnostic:** YAML-based plugin system for easy extensibility
- ✅ **Production-ready:** FreeSurfer, FastSurfer, and custom pipelines included
- ✅ **UI-first:** Web and desktop interfaces eliminate terminal workflows
- ✅ **Secure by design:** Users operate within their own permissions
- ✅ **Open source:** Core platform freely available, sustainable via services

### Current Status:

**Phase 1 (Local Platform) is in active development.**  
Backend abstraction, Docker execution, and pipeline system are implemented.  
Frontend development and testing with real datasets are next milestones.

### Strategic Path:

1. **Build locally** (Months 1-3) - Fast iteration, no dependencies
2. **Add HPC support** (Months 4-6) - Validate with partner institutions
3. **Desktop app** (Months 7-9) - Scale to individual researchers
4. **OOD deployment** (Months 10-12) - Institutional production use

---

## Document Information

**Document Version:** 2.0  
**Last Updated:** February 7, 2026  
**Target Audience:** Developers, Investors, Research Teams, HPC Administrators  
**Status:** Technical Design Document & Implementation Roadmap  
**Project Repository:** `neuroinsight_research/` (see README.md for setup)

**Separate from:** NeuroInsight (existing hippocampal sclerosis detection tool)  
**Built by:** NeuroInsight Research Team
