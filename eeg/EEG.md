# NeuroInsight Research (NIR): EEG & EEG+Imaging Plugin + Workflow Documentation

This document defines the EEG module for NIR. Future **plugin manifests**, **workflow specs** (e.g. YAML), and **implementation notes** should live under the `eeg/` directory alongside this file unless otherwise agreed.

For the **target EEG / EEG+imaging plugin catalog** (eight core steps, SpikeNet2 option, three starter workflows, YAML examples, and repo status), see [`eeg/EEG_PLUGINS_AND_WORKFLOWS.md`](EEG_PLUGINS_AND_WORKFLOWS.md).

**MNE/Brainstorm pipeline references and Docker images** (preprocessing through source localization; plus **ROI fusion** and **biomarker scoring** images; build/push to `phindagijimana321`): see [`eeg/docker/README.md`](docker/README.md) and [`eeg/docker/MNE_BRAINSTORM_PIPELINE_SOURCES.md`](docker/MNE_BRAINSTORM_PIPELINE_SOURCES.md).

---

## 1. Overview

### Purpose

The EEG module of NIR enables users to:

- Run fully reproducible EEG pipelines
- Integrate EEG with MRI (source localization)
- Perform clinical workflows (epilepsy, spike detection)
- Generate automated reports and biomarkers

### Architecture

```
User UI
  ↓
Workflow (orchestrator)
  ↓
Plugins (containerized execution units)
  ↓
HPC / Local compute
  ↓
Standardized Outputs + Viewer + Reports
```

---

## 2. Design Principles

1. **Plugin-based execution** — Each analysis step is a plugin.
2. **Workflow composition** — Workflows are ordered execution of plugins.
3. **Reproducibility** — Each run logs parameters, software versions, and container hashes.
4. **Standardized outputs** — All plugins emit a common bundle layout:

```
bundle/
  signals/
  metrics/
  visualizations/
  qc/
  logs/
```

---

## 3. Data Standards

### EEG input

Supported formats:

- EDF (`.edf`)
- BrainVision (`.vhdr` / `.eeg` / `.vmrk`)
- FIF (`.fif`)
- BDF (`.bdf`)

### MRI input

- T1-weighted NIfTI (`.nii.gz`)

### Internal standard

- Converted to MNE `Raw` objects (internal)
- BIDS-like structure (optional)

### HPC test data (URMC NFS, EDF)

Use this location when the compute worker can see the URMC NFS mount (e.g. HPC/SLURM job with the same filesystem):

- **Folder:** `/mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/EEG`
- **Example continuous EEG files (EDF):**
  - `X~ X_2a24bf65-41f5-4396-b5a4-58d002b7e04e.EDF` (~23 MB)
  - `X~ X_f0728a0c-95d3-444b-a437-806ab164bd5c.EDF`

**Aligning with NIR EEG workflows** (`basic_eeg_epilepsy_detection`, `eeg_source_localization`, `multimodal_epilepsy_biomarker`): plugins expect raw EEG under **`input_dir/eeg/raw/`** by default (`eeg_raw_path` defaults to `eeg/raw`). You can:

1. **Recommended layout** — Under a run directory used as `input_dir`, create `eeg/raw/` and copy or symlink the `.edf` files there, e.g.  
   `…/EEG/run01/eeg/raw/<name>.edf`, then submit with `input_dir` = `…/EEG/run01` (directory mode) or browse to that folder in Single/Batch as your app supports.
2. **Single file** — In Jobs, **Single** input mode: pick one `.edf` by full path so the job receives that file as the workflow input (worker staging still applies).

Filenames with spaces or odd prefixes can break remote shells; prefer renaming or symlinking to short names (e.g. `sub-01_eeg.edf`) inside `eeg/raw/` for reliable HPC runs.

---

## 4. Plugin specifications

### 4.1 Data import plugins

| Plugin | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| **mne_import_raw** | Load EEG/MEG into the NIR pipeline | EEG file path; optional montage | `bundle/signals/raw.fif`, `bundle/metadata/channels.json` |
| **mne_import_mri** | Load anatomical MRI for source localization | T1 NIfTI | `bundle/mri/T1.nii.gz` |

**mne_import_raw** — Reads raw EEG, applies channel metadata, converts to the standard internal format.

### 4.2 Preprocessing plugins

| Plugin | Purpose | Notes / outputs |
|--------|---------|-----------------|
| **mne_filtering** | Remove noise frequencies | Bandpass; optional notch (50/60 Hz) → `bundle/signals/filtered.fif` |
| **mne_rereference** | Referencing | Average or mastoid → `bundle/signals/reref.fif` |
| **mne_bad_channel_detection** | Detect noisy channels | `bundle/qc/bad_channels.json` |
| **mne_ica_decomposition** | ICA | `bundle/signals/ica.fif` |
| **mne_ica_cleanup** | Remove artifacts (EOG, ECG) | `bundle/signals/clean.fif` |

### 4.3 Epoching plugins

| Plugin | Purpose |
|--------|---------|
| **mne_epoching** | Segment EEG into trials (events, time window) → `bundle/signals/epochs.fif` |
| **mne_reject_epochs** | Remove bad trials |

### 4.4 ERP plugins

| Plugin | Purpose | Outputs |
|--------|---------|---------|
| **mne_evoked_average** | Event-related potentials (ERP) | `bundle/metrics/erp.npy`, `bundle/visualizations/erp_plot.png` |
| **mne_evoked_metrics** | ERP biomarkers | `bundle/metrics/erp_features.json` |

### 4.5 Spectral plugins

| Plugin | Purpose |
|--------|---------|
| **mne_psd** | Power spectral density → `bundle/metrics/psd.json` |
| **mne_band_power** | Band power (delta, theta, alpha, beta, gamma) |
| **mne_time_frequency** | Time-frequency decomposition → `bundle/visualizations/timefreq.png` |

### 4.6 Connectivity plugins

| Plugin | Purpose |
|--------|---------|
| **mne_connectivity_sensor** | Connectivity between electrodes |
| **mne_connectivity_source** | Connectivity between brain regions |
| **mne_network_metrics** | Graph metrics (degree, clustering, efficiency) |

### 4.7 MRI / head model plugins

| Plugin | Purpose |
|--------|---------|
| **mne_coregistration** | Align EEG with MRI |
| **mne_bem_model** | Build head model |
| **mne_forward_solution** | Forward model |

### 4.8 Source localization plugins

| Plugin | Purpose |
|--------|---------|
| **mne_inverse_solution** | EEG → brain activity (MNE, dSPM, sLORETA) |
| **mne_beamformer** | Advanced localization |
| **mne_source_parcellation** | Summarize activity per region |

### 4.9 Statistics plugins

| Plugin | Purpose |
|--------|---------|
| **mne_statistics_cluster** | Cluster-based permutation testing |
| **mne_group_analysis** | Group-level analysis |

### 4.10 Machine learning plugin

| Plugin | Purpose | Outputs |
|--------|---------|---------|
| **mne_decoding** | Brain state classification | `bundle/metrics/accuracy.json` |

### 4.11 Reporting plugins

| Plugin | Purpose |
|--------|---------|
| **mne_report_generation** | QC HTML report |
| **nir_pdf_report** | Clinical PDF report |

### 4.12 Brainstorm clinical plugins

| Plugin | Purpose | Outputs |
|--------|---------|---------|
| **brainstorm_spike_detection** | Epileptic spike detection | `bundle/metrics/spikes.json`, `bundle/visualizations/spikes.png` |
| **brainstorm_spike_localization** | Localize spike sources | `bundle/source/spike_map.nii.gz` |
| **brainstorm_epilepsy_metrics** | Clinical biomarkers | (per pipeline) |

---

## 5. Workflows

| # | Workflow | Steps (high level) |
|---|----------|-------------------|
| 1 | EEG preprocessing | import → filter → rereference → ICA → cleanup |
| 2 | ERP analysis | preprocessing → epoching → averaging → metrics |
| 3 | Spectral analysis | preprocessing → PSD → band power |
| 4 | Time-frequency | preprocessing → time-frequency |
| 5 | EEG connectivity | preprocessing → connectivity → network metrics |
| 6 | EEG + MRI source localization | preprocessing → coregistration → forward → inverse |
| 7 | Source connectivity | source localization → connectivity → network metrics |
| 8 | Group analysis | subject-level → statistics → group outputs |
| 9 | Decoding (ML) | preprocessing → feature extraction → classifier |
| 10 | QC reporting | preprocessing → report generation |
| 11 | Epilepsy spike detection | preprocessing → spike detection → metrics |
| 12 | Epilepsy localization (EEG + MRI) | preprocessing → spike detection → source localization |
| 13 | Full epilepsy pipeline | preprocessing → spike detection → source localization → report |

---

## 6. Visualization layer (EEG viewer)

Niivue covers imaging; EEG needs a complementary stack:

**Recommended options**

- MNE browser (backend rendering)
- Plotly (interactive)
- Custom WebGL viewer

**Features**

- Time series viewer
- Topomap viewer
- Time-frequency maps
- Spike visualization
- Source overlays on MRI (Niivue integration)

---

## 7. HPC execution

Each plugin runs similarly to:

```bash
docker run <image> run.py --inputs --outputs
```

Supports:

- SLURM
- SSH agent forwarding
- OOD integration

---

## 8. Clinical translation potential

This design supports:

- Epilepsy diagnostics
- Cognitive biomarkers
- ML-based EEG biomarkers
- Multimodal (EEG + MRI) analysis

---

## Summary

The NIR EEG system targets:

- MNE-powered, scalable pipelines
- Brainstorm-derived clinical workflows
- Containerized reproducibility
- UI-driven execution (minimal coding)
- HPC and local execution

### Next steps (optional)

- Convert this outline into YAML plugin + workflow specifications
- Design EEG viewer UI (Niivue-style affordances for signals)
- Map outputs to biomarkers for product positioning
