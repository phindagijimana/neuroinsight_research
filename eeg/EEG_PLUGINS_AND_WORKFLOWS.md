# NIR EEG and EEG+Imaging Plugins and Workflows Documentation

## Overview

This document defines the eight core plugins and three starter workflows for NeuroInsight Research (NIR) focused on EEG and EEG+imaging biomarker pipelines. It assumes each plugin will be packaged as a Docker image and deployed on an EC2-based cluster.

The goal of this stack is to support:

* basic EEG epilepsy detection
* EEG source localization
* multimodal epilepsy biomarker scoring

The plugin set is intentionally minimal, clinically meaningful, and practical to operationalize.

**Implementation status:** The repository ships **plugin YAML** for all eight core steps and **workflow YAML** for the three starter workflows under `workflows/` (`basic_eeg_epilepsy_detection`, `eeg_source_localization`, `multimodal_epilepsy_biomarker`). Docker images are under `phindagijimana321/` and `docker/*`.

**Related docs:** `eeg/EEG.md` (module overview), `docs/viewer_later.md` (Viewer scope), `eeg/SAMPLE_SOURCE_LOCALIZATION_DATA.md` (evaluation data).

---

# 1. Architecture Principles

## Plugin model

Each plugin is a single bounded execution unit with:

* a clear responsibility
* standardized inputs
* standardized outputs
* a Docker image
* a YAML definition for orchestration

## Workflow model

A workflow is an ordered set of plugins where the outputs of one plugin become the inputs of the next.

## Runtime assumptions

* Plugins run in containers on EC2 compute nodes
* Shared storage is mounted consistently across containers
* Each run writes artifacts into a run-scoped output directory
* Orchestration is handled by the NIR workflow engine

---

# 2. Directory and Data Conventions

## Recommended run layout

```text
/runs/{run_id}/
  inputs/
    eeg/
    mri/
    metadata/
  intermediate/
    eeg_preprocessing/
    spike_detection/
    eeg_mri_coregistration/
    forward_model/
    source_localization/
    mri_segmentation/
    roi_feature_extraction/
  outputs/
    biomarker_scoring/
    viewer/
    reports/
```

## Recommended shared conventions

* EEG inputs should support EDF, FIF, BrainVision, or BIDS EEG
* MRI inputs should support T1 NIfTI
* Coordinates, transforms, and ROI outputs should use JSON/TSV/NIfTI where possible
* Viewer artifacts should include lightweight assets suitable for the NIR Viewer page (e.g. `nir_multimodal_manifest.json` + mesh/time series for Multimodal View when applicable)

---

# 3. Plugin Documentation

## Plugin 1: eeg_preprocessing

### Purpose

Clean raw EEG so it can be used by downstream detection and source-imaging workflows.

### What it does

* bandpass filtering
* notch filtering
* re-referencing
* optional bad-channel handling
* optional ICA-based artifact handling
* optional event/annotation preservation

### Typical tool origin

Primary implementation source:

* MNE-Python

### Where it is found

* MNE preprocessing tutorials and preprocessing API
* MNE ICA documentation

### Typical inputs

* raw EEG file
* optional channel metadata
* optional montage file
* optional preprocessing configuration JSON/YAML

### Typical outputs

* cleaned EEG file
* optional annotations/events
* QC summary JSON
* preprocessing log

### Why it matters

This is the foundation of all three workflows. Every downstream step depends on having usable EEG.

### Dockerization notes

This is one of the easiest plugins to containerize because it is pure Python and scriptable.

### Example plugin YAML

```yaml
name: eeg_preprocessing
version: 1.0.0
image: nir/eeg-preprocessing-mne:1.0.0
modality: eeg
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 8
inputs:
  eeg_raw:
    path: /data/input/eeg/raw
    required: true
  eeg_metadata:
    path: /data/input/metadata/eeg_metadata.json
    required: false
  config:
    path: /data/input/metadata/preprocessing_config.yaml
    required: false
outputs:
  eeg_clean:
    path: /data/output/eeg/clean_raw.fif
  events:
    path: /data/output/eeg/events.tsv
  qc_summary:
    path: /data/output/qc/preprocessing_qc.json
  logs:
    path: /data/output/logs/preprocessing.log
```

---

## Plugin 2: spike_detection

### Purpose

Detect epileptiform spike candidates from cleaned EEG.

### What it does

* scans cleaned EEG for spike-like events
* returns event timestamps
* identifies relevant channels
* optionally returns confidence or ranking scores

### Typical tool origin

Possible implementations:

* Brainstorm clinical-style workflow
* MNE/custom Python detector
* future AI detector such as SpikeNet2

### Where it is found

* Brainstorm epilepsy tutorial
* MNE event/annotation ecosystem for baseline implementations

### Typical inputs

* cleaned EEG
* optional event-detection configuration

### Typical outputs

* spike event table
* per-event channels
* optional confidence scores
* spike QC log

### Why it matters

This is the first epilepsy biomarker-producing step. Spike presence, spike timing, and spike burden are clinically meaningful.

### Dockerization notes

* Easy if implemented in Python
* More operationally complex if wrapped around Brainstorm, but still feasible with a controlled container entrypoint

### Example plugin YAML

```yaml
name: spike_detection
version: 1.0.0
image: nir/spike-detection:1.0.0
modality: eeg
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 8
inputs:
  eeg_clean:
    path: /data/input/eeg/clean_raw.fif
    required: true
  config:
    path: /data/input/metadata/spike_detection_config.yaml
    required: false
outputs:
  spike_events:
    path: /data/output/events/spike_events.tsv
  spike_channels:
    path: /data/output/events/spike_channels.json
  spike_scores:
    path: /data/output/events/spike_scores.json
  logs:
    path: /data/output/logs/spike_detection.log
```

---

## Plugin 3: eeg_mri_coregistration

### Purpose

Align EEG sensor coordinates to MRI anatomy.

### What it does

* uses channel locations and anatomical references
* computes transform from EEG/head coordinates into MRI space
* produces alignment artifacts for QC

### Typical tool origin

Primary implementation source:

* Brainstorm
* MNE coregistration workflows

### Where it is found

* Brainstorm epilepsy and source-estimation tutorials
* MNE source-imaging workflows

### Typical inputs

* cleaned EEG with montage/channel locations
* subject MRI and/or surfaces
* optional fiducials/headshape metadata

### Typical outputs

* EEG-to-MRI transform
* transformed electrode coordinates
* coregistration QC artifact
* log

### Why it matters

This is the bridge from EEG to brain space and is required for source localization.

### Dockerization notes

Good container candidate because it has deterministic inputs/outputs, but it requires a consistent mounted layout for EEG, MRI, fiducials, and surfaces.

### Example plugin YAML

```yaml
name: eeg_mri_coregistration
version: 1.0.0
image: nir/eeg-mri-coregistration:1.0.0
modality: eeg+imaging
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 12
inputs:
  eeg_clean:
    path: /data/input/eeg/clean_raw.fif
    required: true
  t1_mri:
    path: /data/input/mri/T1.nii.gz
    required: true
  montage:
    path: /data/input/metadata/montage.json
    required: false
outputs:
  coreg_transform:
    path: /data/output/coreg/eeg_to_mri_transform.json
  electrode_coords:
    path: /data/output/coreg/electrode_coords_mri.json
  qc_artifact:
    path: /data/output/qc/coregistration_qc.png
  logs:
    path: /data/output/logs/coregistration.log
```

---

## Plugin 4: forward_model

### Purpose

Construct the forward model (lead field) required for inverse/source localization.

### What it does

* builds or consumes head/BEM surfaces
* combines EEG sensor definitions with anatomy and transform
* computes the forward solution

### Typical tool origin

Primary implementation source:

* MNE
* Brainstorm

### Where it is found

* MNE inverse/source localization workflows
* Brainstorm source estimation documentation

### Typical inputs

* MRI-derived surfaces/BEM
* coregistration transform
* EEG sensor definitions

### Typical outputs

* forward solution file
* head model artifacts
* logs

### Why it matters

Required for source localization. This is the physics stage of EEG source imaging.

### Dockerization notes

A strong Docker candidate because it is a bounded stage with stable inputs and outputs.

### Example plugin YAML

```yaml
name: forward_model
version: 1.0.0
image: nir/forward-model:1.0.0
modality: eeg+imaging
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 16
inputs:
  coreg_transform:
    path: /data/input/coreg/eeg_to_mri_transform.json
    required: true
  electrode_coords:
    path: /data/input/coreg/electrode_coords_mri.json
    required: true
  bem_surfaces:
    path: /data/input/models/bem/
    required: true
outputs:
  forward_solution:
    path: /data/output/models/forward_solution.fif
  head_model_artifact:
    path: /data/output/qc/head_model_qc.png
  logs:
    path: /data/output/logs/forward_model.log
```

---

## Plugin 5: source_localization

### Purpose

Estimate brain-space source activity from EEG using inverse methods.

### What it does

* consumes cleaned EEG or spike-averaged data
* applies inverse methods such as MNE, dSPM, sLORETA, or eLORETA
* outputs source maps and localization summaries

### Typical tool origin

Primary implementation source:

* MNE minimum-norm / inverse workflows
* Brainstorm source estimation workflows

### Where it is found

* MNE inverse tutorials
* Brainstorm source estimation tutorials

### Typical inputs

* cleaned EEG or spike-averaged epochs
* forward solution
* inverse/noise model ingredients

### Typical outputs

* source map
* peak coordinates
* laterality summary
* optional ROI-mapped source values

### Why it matters

This is the main EEG+imaging biomarker step because it localizes activity in brain space.

### Dockerization notes

One of the best plugins to containerize because it is fully scriptable and naturally produces standard artifacts.

### Example plugin YAML

```yaml
name: source_localization
version: 1.0.0
image: nir/source-localization-mne:1.0.0
modality: eeg+imaging
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 16
inputs:
  eeg_clean:
    path: /data/input/eeg/clean_raw.fif
    required: true
  spike_events:
    path: /data/input/events/spike_events.tsv
    required: false
  forward_solution:
    path: /data/input/models/forward_solution.fif
    required: true
  inverse_config:
    path: /data/input/metadata/source_localization_config.yaml
    required: false
outputs:
  source_map:
    path: /data/output/source/source_map.nii.gz
  peak_coordinates:
    path: /data/output/source/peak_coordinates.json
  laterality_summary:
    path: /data/output/source/laterality_summary.json
  logs:
    path: /data/output/logs/source_localization.log
```

---
## Plugin 6: mri_segmentation

### Purpose

Extract structural anatomy features from MRI, especially hippocampal and temporal-lobe measurements relevant to epilepsy.

### What it does

* segments hippocampal and related anatomy
* computes regional labels and volumes
* supports structural biomarker extraction

### Typical tool origin

Primary implementation source:

* FreeSurfer

### Where it is found

* FreeSurfer hippocampal subfields / amygdala nuclei documentation

### Typical inputs

* T1 MRI
* optional high-resolution images

### Typical outputs

* hippocampal volumes
* subfield volumes
* region labels
* segmentation artifacts

### Why it matters

This is the structural biomarker branch for the multimodal workflow.

### Dockerization notes

Very standard for neuroimaging pipelines, but compute-heavy and dependency-heavy, so it should be isolated in a dedicated long-running container.

### Example plugin YAML

```yaml
name: mri_segmentation
version: 1.0.0
image: nir/mri-segmentation-freesurfer:1.0.0
modality: imaging
entrypoint: bash /app/run.sh
resources:
  cpu: 8
  memory_gb: 32
inputs:
  t1_mri:
    path: /data/input/mri/T1.nii.gz
    required: true
outputs:
  hippocampal_volumes:
    path: /data/output/segmentation/hippocampal_volumes.json
  subfield_volumes:
    path: /data/output/segmentation/subfield_volumes.tsv
  region_labels:
    path: /data/output/segmentation/region_labels.nii.gz
  logs:
    path: /data/output/logs/mri_segmentation.log
```

---

## Plugin 7: roi_feature_extraction

### Purpose

Fuse EEG source-localization outputs and MRI segmentation outputs into common ROI-level biomarker features.

### What it does

* maps source activity to ROIs
* maps structural measures to the same ROIs
* computes concordance features between functional and structural findings

### Typical tool origin

NIR-native plugin

### Where it is found

This is a custom NIR plugin built over standard outputs from MNE/Brainstorm/FreeSurfer.

### Typical inputs

* source map
* segmentation outputs
* ROI definitions or atlas

### Typical outputs

* per-ROI source intensity
* per-ROI structural metrics
* concordance features

### Why it matters

This is the main fusion layer that turns separate outputs into a multimodal biomarker representation.

### Dockerization notes

Very easy to containerize because it is mostly custom Python logic over standard files.

### Example plugin YAML

```yaml
name: roi_feature_extraction
version: 1.0.0
image: nir/roi-feature-extraction:1.0.0
modality: eeg+imaging
entrypoint: python /app/run.py
resources:
  cpu: 2
  memory_gb: 4
inputs:
  source_map:
    path: /data/input/source/source_map.nii.gz
    required: true
  segmentation_metrics:
    path: /data/input/segmentation/
    required: true
  roi_definitions:
    path: /data/input/metadata/roi_definitions.json
    required: true
outputs:
  roi_source_features:
    path: /data/output/features/roi_source_features.json
  roi_structural_features:
    path: /data/output/features/roi_structural_features.json
  concordance_features:
    path: /data/output/features/concordance_features.json
  logs:
    path: /data/output/logs/roi_feature_extraction.log
```

---

## Plugin 8: biomarker_scoring

### Purpose

Score the fused ROI features and produce a biomarker-oriented summary that can be used in the viewer and reports.

### What it does

* computes laterality and concordance scores
* generates summary classification or prioritization outputs
* produces viewer/report-ready JSON

### Typical tool origin

NIR-native plugin

### Where it is found

This is a custom NIR plugin built over fused outputs from the prior steps.

### Typical inputs

* ROI source features
* ROI structural features
* concordance features
* optional scoring configuration

### Typical outputs

* biomarker score JSON
* laterality score
* concordance score
* biomarker summary JSON for report/viewer

### Why it matters

This is the final step that turns raw multimodal features into a human-readable biomarker output.

### Dockerization notes

Trivial to containerize and ideal as a lightweight scoring/report plugin.

### Example plugin YAML

```yaml
name: biomarker_scoring
version: 1.0.0
image: nir/biomarker-scoring:1.0.0
modality: eeg+imaging
entrypoint: python /app/run.py
resources:
  cpu: 2
  memory_gb: 4
inputs:
  roi_source_features:
    path: /data/input/features/roi_source_features.json
    required: true
  roi_structural_features:
    path: /data/input/features/roi_structural_features.json
    required: true
  concordance_features:
    path: /data/input/features/concordance_features.json
    required: true
  config:
    path: /data/input/metadata/biomarker_scoring_config.yaml
    required: false
outputs:
  biomarker_scores:
    path: /data/output/biomarker/biomarker_scores.json
  laterality_score:
    path: /data/output/biomarker/laterality_score.json
  concordance_score:
    path: /data/output/biomarker/concordance_score.json
  viewer_summary:
    path: /data/output/biomarker/viewer_summary.json
  logs:
    path: /data/output/logs/biomarker_scoring.log
```

---

## Plugin 9: spikenet2_spike_detection

### Purpose

Detect epileptiform discharges from EEG using the SpikeNet 2.0 deep learning model.

### What it does

* performs automated epileptiform discharge detection on EEG recordings
* supports event-level spike detection
* supports EEG-level classification
* can provide candidate spike events for downstream source-localization workflows

### Typical tool origin

Primary implementation source:

* SpikeNet 2.0 on the Brain Data Science Platform (BDSP)
* companion code repository from bdsp-core/SpikeNet2

### Where it is found

* [BDSP SpikeNet 2.0 resource page](https://bdsp.io/content/spikenet2/1.0/)
* BDSP SpikeNet2 GitHub repository

### Notes on validation and access

SpikeNet 2.0 is described by BDSP as an advanced deep learning model for automated detection of epileptiform discharges in EEG recordings. The BDSP page states that it achieves expert-level performance in both event-level spike detection and EEG-level classification, with reduced false-positive rates compared with previous models, and that it was trained on 17,812 EEGs from 13,523 patients and validated across multiple external datasets. The BDSP resource is restricted access and requires users to sign a data use agreement to access files.

### Typical inputs

* cleaned EEG
* optional model configuration
* optional channel metadata / montage

### Typical outputs

* spike events table
* per-event confidence scores
* EEG-level classification score
* optional viewer-ready spike summary JSON

### Why it matters

This is a strong candidate replacement or enhancement for baseline spike detection in epilepsy workflows because the target output—epileptiform spike detection—is directly relevant to epilepsy biomarkers. It is especially useful where you want a more scalable automated detector before source localization.

### Where it can be used in workflows

It can be used anywhere the `spike_detection` plugin appears. In practice:

* Workflow 1: Basic EEG Epilepsy Detection
* Workflow 2: EEG Source Localization
* Workflow 3: Multimodal Epilepsy Biomarker

It should be treated as an implementation option for the spike-detection step, not as a replacement for source localization or MRI segmentation.

### Dockerization notes

This is a strong Docker candidate because BDSP states that code, trained models, processing pipelines, and analysis scripts are provided in the SpikeNet2 repository. In NIR, the cleanest pattern is to wrap the inference entrypoint in a container, standardize EEG input locations, and emit a stable spike-events JSON/TSV contract for downstream plugins.

### Example plugin YAML

```yaml
name: spikenet2_spike_detection
version: 1.0.0
image: nir/spikenet2-spike-detection:1.0.0
modality: eeg
entrypoint: python /app/run.py
resources:
  cpu: 4
  memory_gb: 12
  gpu: optional
inputs:
  eeg_clean:
    path: /data/input/eeg/clean_raw.fif
    required: true
  config:
    path: /data/input/metadata/spikenet2_config.yaml
    required: false
outputs:
  spike_events:
    path: /data/output/events/spikenet2_spike_events.tsv
  spike_scores:
    path: /data/output/events/spikenet2_spike_scores.json
  eeg_level_classification:
    path: /data/output/events/spikenet2_eeg_level_classification.json
  logs:
    path: /data/output/logs/spikenet2.log
```

---

# 4. Workflow Documentation

## Workflow 1: Basic EEG Epilepsy Detection

### Goal

Provide a fast, clinically recognizable baseline workflow for detecting epileptiform spikes from EEG.

### Plugins used

1. `eeg_preprocessing`
2. `spike_detection`

### What each plugin does in this workflow

* `eeg_preprocessing` cleans the raw EEG so downstream detection is robust
* `spike_detection` finds epileptiform events and writes event artifacts

### Input/output flow

```text
raw EEG
  → eeg_preprocessing
    → cleaned EEG
      → spike_detection
        → spike event table + channels + optional scores
```

### What the workflow does

It takes raw EEG, cleans it, identifies spike candidates, and produces outputs suitable for the Signal View and epilepsy review.

### Example workflow YAML

```yaml
name: basic_eeg_epilepsy_detection
version: 1.0.0
plugins:
  - id: eeg_preprocessing
    image: nir/eeg-preprocessing-mne:1.0.0
    inputs:
      eeg_raw: /runs/${RUN_ID}/inputs/eeg/raw
    outputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
      events: /runs/${RUN_ID}/intermediate/eeg_preprocessing/events.tsv
      qc_summary: /runs/${RUN_ID}/intermediate/eeg_preprocessing/preprocessing_qc.json

  - id: spike_detection
    image: nir/spike-detection:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
    outputs:
      spike_events: /runs/${RUN_ID}/outputs/events/spike_events.tsv
      spike_channels: /runs/${RUN_ID}/outputs/events/spike_channels.json
      spike_scores: /runs/${RUN_ID}/outputs/events/spike_scores.json
```

---

## Workflow 2: EEG Source Localization

### Goal

Detect spike-related activity and localize it into brain space using EEG and MRI.

### Plugins used

1. `eeg_preprocessing`
2. `spike_detection`
3. `eeg_mri_coregistration`
4. `forward_model`
5. `source_localization`

### What each plugin does in this workflow

* `eeg_preprocessing` cleans the EEG
* `spike_detection` finds candidate epileptiform events
* `eeg_mri_coregistration` aligns electrodes to MRI
* `forward_model` computes the lead field/head model
* `source_localization` estimates cortical/brain-space source activity

### Input/output flow

```text
raw EEG
  → eeg_preprocessing
    → cleaned EEG
      → spike_detection
        → spike events
cleaned EEG + MRI
  → eeg_mri_coregistration
    → transform + electrode coords
transform + anatomy
  → forward_model
    → forward solution
cleaned EEG + spike events + forward solution
  → source_localization
    → source map + peak coordinates + laterality summary
```

### What the workflow does

It takes EEG and MRI together, finds spike-related events, aligns the sensors with the anatomy, builds the forward model, and produces source-localized brain results for the Brain View and Multimodal View.

### Example workflow YAML

```yaml
name: eeg_source_localization
version: 1.0.0
plugins:
  - id: eeg_preprocessing
    image: nir/eeg-preprocessing-mne:1.0.0
    inputs:
      eeg_raw: /runs/${RUN_ID}/inputs/eeg/raw
    outputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif

  - id: spike_detection
    image: nir/spike-detection:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
    outputs:
      spike_events: /runs/${RUN_ID}/intermediate/spike_detection/spike_events.tsv

  - id: eeg_mri_coregistration
    image: nir/eeg-mri-coregistration:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
      t1_mri: /runs/${RUN_ID}/inputs/mri/T1.nii.gz
    outputs:
      coreg_transform: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/eeg_to_mri_transform.json
      electrode_coords: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/electrode_coords_mri.json

  - id: forward_model
    image: nir/forward-model:1.0.0
    inputs:
      coreg_transform: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/eeg_to_mri_transform.json
      electrode_coords: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/electrode_coords_mri.json
      bem_surfaces: /runs/${RUN_ID}/inputs/mri/bem/
    outputs:
      forward_solution: /runs/${RUN_ID}/intermediate/forward_model/forward_solution.fif

  - id: source_localization
    image: nir/source-localization-mne:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
      spike_events: /runs/${RUN_ID}/intermediate/spike_detection/spike_events.tsv
      forward_solution: /runs/${RUN_ID}/intermediate/forward_model/forward_solution.fif
    outputs:
      source_map: /runs/${RUN_ID}/outputs/source/source_map.nii.gz
      peak_coordinates: /runs/${RUN_ID}/outputs/source/peak_coordinates.json
      laterality_summary: /runs/${RUN_ID}/outputs/source/laterality_summary.json
```

---
## Workflow 3: Multimodal Epilepsy Biomarker

### Goal

Combine EEG spike findings, source localization, and structural MRI segmentation into a unified biomarker-oriented output.

### Plugins used

1. `eeg_preprocessing`
2. `spike_detection`
3. `eeg_mri_coregistration`
4. `forward_model`
5. `source_localization`
6. `mri_segmentation`
7. `roi_feature_extraction`
8. `biomarker_scoring`

### What each plugin does in this workflow

* `eeg_preprocessing` cleans the EEG
* `spike_detection` identifies epileptiform events
* `eeg_mri_coregistration` aligns EEG to MRI
* `forward_model` builds the lead field
* `source_localization` localizes the spike activity in brain space
* `mri_segmentation` extracts structural anatomy features such as hippocampal metrics
* `roi_feature_extraction` fuses source and structural results into common ROIs
* `biomarker_scoring` scores the multimodal evidence into a report/viewer-ready biomarker summary

### Input/output flow

```text
EEG branch:
raw EEG
  → eeg_preprocessing
    → cleaned EEG
      → spike_detection
        → spike events
          → eeg_mri_coregistration
            → transform + coords
              → forward_model
                → forward solution
                  → source_localization
                    → source map + laterality

MRI branch:
T1 MRI
  → mri_segmentation
    → hippocampal volumes + subfields + labels

Fusion branch:
source map + segmentation outputs
  → roi_feature_extraction
    → ROI source features + ROI structural features + concordance features
      → biomarker_scoring
        → laterality score + concordance score + biomarker summary
```

### What the workflow does

This workflow operationalizes multimodal epilepsy reasoning. It asks whether epileptiform EEG activity localizes to brain regions that are also structurally abnormal on MRI, then scores how strongly the two modalities agree.

### Example workflow YAML

```yaml
name: multimodal_epilepsy_biomarker
version: 1.0.0
plugins:
  - id: eeg_preprocessing
    image: nir/eeg-preprocessing-mne:1.0.0
    inputs:
      eeg_raw: /runs/${RUN_ID}/inputs/eeg/raw
    outputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif

  - id: spike_detection
    image: nir/spike-detection:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
    outputs:
      spike_events: /runs/${RUN_ID}/intermediate/spike_detection/spike_events.tsv
      spike_scores: /runs/${RUN_ID}/intermediate/spike_detection/spike_scores.json

  - id: eeg_mri_coregistration
    image: nir/eeg-mri-coregistration:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
      t1_mri: /runs/${RUN_ID}/inputs/mri/T1.nii.gz
    outputs:
      coreg_transform: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/eeg_to_mri_transform.json
      electrode_coords: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/electrode_coords_mri.json

  - id: forward_model
    image: nir/forward-model:1.0.0
    inputs:
      coreg_transform: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/eeg_to_mri_transform.json
      electrode_coords: /runs/${RUN_ID}/intermediate/eeg_mri_coregistration/electrode_coords_mri.json
      bem_surfaces: /runs/${RUN_ID}/inputs/mri/bem/
    outputs:
      forward_solution: /runs/${RUN_ID}/intermediate/forward_model/forward_solution.fif

  - id: source_localization
    image: nir/source-localization-mne:1.0.0
    inputs:
      eeg_clean: /runs/${RUN_ID}/intermediate/eeg_preprocessing/clean_raw.fif
      spike_events: /runs/${RUN_ID}/intermediate/spike_detection/spike_events.tsv
      forward_solution: /runs/${RUN_ID}/intermediate/forward_model/forward_solution.fif
    outputs:
      source_map: /runs/${RUN_ID}/intermediate/source_localization/source_map.nii.gz
      peak_coordinates: /runs/${RUN_ID}/intermediate/source_localization/peak_coordinates.json
      laterality_summary: /runs/${RUN_ID}/intermediate/source_localization/laterality_summary.json

  - id: mri_segmentation
    image: nir/mri-segmentation-freesurfer:1.0.0
    inputs:
      t1_mri: /runs/${RUN_ID}/inputs/mri/T1.nii.gz
    outputs:
      hippocampal_volumes: /runs/${RUN_ID}/intermediate/mri_segmentation/hippocampal_volumes.json
      subfield_volumes: /runs/${RUN_ID}/intermediate/mri_segmentation/subfield_volumes.tsv
      region_labels: /runs/${RUN_ID}/intermediate/mri_segmentation/region_labels.nii.gz

  - id: roi_feature_extraction
    image: nir/roi-feature-extraction:1.0.0
    inputs:
      source_map: /runs/${RUN_ID}/intermediate/source_localization/source_map.nii.gz
      segmentation_metrics: /runs/${RUN_ID}/intermediate/mri_segmentation/
      roi_definitions: /runs/${RUN_ID}/inputs/metadata/roi_definitions.json
    outputs:
      roi_source_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/roi_source_features.json
      roi_structural_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/roi_structural_features.json
      concordance_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/concordance_features.json

  - id: biomarker_scoring
    image: nir/biomarker-scoring:1.0.0
    inputs:
      roi_source_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/roi_source_features.json
      roi_structural_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/roi_structural_features.json
      concordance_features: /runs/${RUN_ID}/intermediate/roi_feature_extraction/concordance_features.json
    outputs:
      biomarker_scores: /runs/${RUN_ID}/outputs/biomarker/biomarker_scores.json
      laterality_score: /runs/${RUN_ID}/outputs/biomarker/laterality_score.json
      concordance_score: /runs/${RUN_ID}/outputs/biomarker/concordance_score.json
      viewer_summary: /runs/${RUN_ID}/outputs/biomarker/viewer_summary.json
```

---

# 5. Plugin Source References

## MNE

* Preprocessing and ICA documentation
* Source localization / inverse tutorials
* Minimum-norm inverse workflows

## Brainstorm

* Epilepsy tutorial
* Source estimation tutorial

## FreeSurfer

* Hippocampal subfields and amygdala nuclei segmentation documentation

---

# 6. Recommended EC2 Cluster Strategy

## Compute classes

* lightweight Python plugins:

  * `eeg_preprocessing`
  * `spike_detection`
  * `roi_feature_extraction`
  * `biomarker_scoring`
* heavier compute plugins:

  * `forward_model`
  * `source_localization`
  * `mri_segmentation`

## Operational recommendations

* pin tool versions in Docker tags
* mount a consistent shared filesystem across nodes
* keep each plugin stateless outside mounted input/output directories
* write JSON summaries for every stage for UI consumption
* keep logs as first-class artifacts

---

# 7. Final Recommendation

## Best initial build order

1. `eeg_preprocessing`
2. `spike_detection`
3. `eeg_mri_coregistration`
4. `forward_model`
5. `source_localization`
6. `mri_segmentation`
7. `roi_feature_extraction`
8. `biomarker_scoring`

## Why this order

* workflow 1 becomes available first
* workflow 2 builds naturally on workflow 1
* workflow 3 becomes your premium multimodal biomarker workflow

This gives NIR a realistic path from baseline EEG review to a differentiated multimodal biomarker platform.

---

# 8. Repository status (plugins vs workflows)

| Spec ID | Role | Present in `plugins/` (approx.) |
|--------|------|--------------------------------|
| `eeg_preprocessing` | core | yes (`eeg_preprocessing.yaml`) |
| `spike_detection` | core | yes (`spike_detection.yaml`) |
| `eeg_mri_coregistration` | core | yes (`eeg_mri_coregistration.yaml`) |
| `forward_model` | core | yes (`forward_model.yaml`) |
| `source_localization` | core | yes (`source_localization.yaml`) |
| `mri_segmentation` | core | yes (`mri_segmentation.yaml`; same image as FreeSurfer VolOnly) |
| `roi_feature_extraction` | core | yes (`roi_feature_extraction.yaml`) |
| `biomarker_scoring` | core | yes (`biomarker_scoring.yaml`) |
| `spikenet2_spike_detection` | optional spike step | not yet |

| Workflow name | Present in `workflows/` |
|----------------|-------------------------|
| `basic_eeg_epilepsy_detection` | yes (`basic_eeg_epilepsy_detection.yaml`) |
| `eeg_source_localization` | yes (`eeg_source_localization.yaml`) |
| `multimodal_epilepsy_biomarker` | yes (`multimodal_epilepsy_biomarker.yaml`) |

Update this table when new plugin or workflow YAMLs land.
