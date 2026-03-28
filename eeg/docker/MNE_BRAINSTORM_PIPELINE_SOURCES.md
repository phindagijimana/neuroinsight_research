# Where NIR EEG plugins map in MNE-Python and Brainstorm

This note ties each planned **plugin stage** to the official tutorials and API entry points you would implement or script inside Docker. Use it when porting logic from interactive tutorials into `/app/run.py` entrypoints.

---

## MNE-Python (recommended for headless Docker plugins)

MNE is pure Python, scriptable, and fits batch containers without a display. Official docs: [https://mne.tools/stable/index.html](https://mne.tools/stable/index.html)

| NIR plugin (concept) | MNE tutorial / topic | URL |
|---------------------|----------------------|-----|
| Typical workflow overview | Cookbook: M/EEG workflow | [documentation/cookbook.html](https://mne.tools/stable/documentation/cookbook.html) |
| **eeg_preprocessing** | Preprocessing overview | [auto_tutorials/preprocessing/](https://mne.tools/stable/auto_tutorials/preprocessing/index.html) |
| Filtering, resampling | Preprocessing overview | [10_preprocessing_overview.html](https://mne.tools/stable/auto_tutorials/preprocessing/10_preprocessing_overview.html) |
| **ICA** | Repairing artifacts with ICA | [40_artifact_correction_ica.html](https://mne.tools/stable/auto_tutorials/preprocessing/40_artifact_correction_ica.html) |
| Bad channels | `annotate_amplitude` / marking bads | See preprocessing tutorials index |
| **Coregistration / sensors** | Align EEG with MRI (digitization, coreg) | [auto_tutorials/forward/](https://mne.tools/stable/auto_tutorials/forward/index.html) and inverse “getting started” |
| **forward_model** | Forward modeling, BEM | [auto_tutorials/forward/](https://mne.tools/stable/auto_tutorials/forward/index.html) |
| **source_localization** | MNE, dSPM, sLORETA, eLORETA | [30_mne_dspm_loreta.html](https://mne.tools/stable/auto_tutorials/inverse/30_mne_dspm_loreta.html) |
| Inverse overview | Inverse tutorials index | [auto_tutorials/inverse/](https://mne.tools/stable/auto_tutorials/inverse/index.html) |
| Sample data layout | `mne.datasets.sample` (MEG/EEG + MRI + BEM) | Run `python eeg/scripts/print_mne_sample_layout.py` in this repo |

**API anchors (code, not tutorials):**

- `mne.io.read_raw_*` — load EDF, FIF, BrainVision, etc.
- `mne.preprocessing.ICA` — ICA
- `mne.make_forward_solution`, `mne.read_forward_solution` — forward / lead field
- `mne.minimum_norm.make_inverse_operator`, `apply_inverse` — minimum-norm / dSPM / sLORETA / eLORETA

---

## Brainstorm (MATLAB GUI + pipeline philosophy)

Brainstorm is documented on the USC wiki. Pipelines are often taught **step-by-step in the GUI**; reproducing them in Docker usually means **exporting scripts** from Brainstorm or reimplementing the same math in MNE (common for production containers).

| NIR plugin (concept) | Brainstorm wiki | URL |
|---------------------|-----------------|-----|
| Epilepsy-oriented EEG + spikes + source | **Epilepsy** | [Tutorials/Epilepsy](https://neuroimage.usc.edu/brainstorm/Tutorials/Epilepsy) |
| Source estimation concepts | **SourceEstimation** | [Tutorials/SourceEstimation](https://neuroimage.usc.edu/brainstorm/Tutorials/SourceEstimation) |
| Introduction | All introductions | [Tutorials/AllIntroduction](https://neuroimage.usc.edu/brainstorm/Tutorials/AllIntroduction) |

**Docker reality check:** A production Brainstorm container typically bundles **MATLAB Runtime or full MATLAB** plus Brainstorm, is large, and may require display-off batch modes or compiled pipelines. For NIR **first-wave** plugins, the repo standardizes on **MNE-based** images under `docker/eeg-mne-*`; add a separate `brainstorm-*` image later if you need pixel-parity with Brainstorm tutorials.

---

## FreeSurfer (structural branch)

`mri_segmentation` in NIR aligns with FreeSurfer recon and hippocampal subfield tools. See FreeSurfer documentation for `recon-all` and hippocampal subfields; the repo already has FreeSurfer-oriented adapters under `adapters/pennsieve/` for other modalities.

---

## Docker images in this repo (MNE)

| Plugin stage | Directory under `docker/` |
|--------------|---------------------------|
| `eeg_preprocessing` | `eeg-mne-preprocessing/` |
| `spike_detection` | `eeg-mne-spike-detection/` |
| `eeg_mri_coregistration` | `eeg-mne-coregistration/` |
| `forward_model` | `eeg-mne-forward-model/` |
| `source_localization` | `eeg-mne-source-localization/` |
| `roi_feature_extraction` | `eeg-roi-feature-extraction/` |
| `biomarker_scoring` | `eeg-biomarker-scoring/` |

Brainstorm and SpikeNet2 are **not** covered here (later).

## Suggested implementation order (matches `eeg/EEG_PLUGINS_AND_WORKFLOWS.md`)

1. **MNE preprocessing** → `docker/eeg-mne-preprocessing/`
2. **Spike detection** → `docker/eeg-mne-spike-detection/`
3. **Coregistration** → `docker/eeg-mne-coregistration/`
4. **Forward model** → `docker/eeg-mne-forward-model/`
5. **Inverse** → `docker/eeg-mne-source-localization/`
6. SpikeNet2 or Brainstorm → separate images + license/compliance review
