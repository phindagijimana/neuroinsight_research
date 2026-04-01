# EEG plugin Docker images (MNE-Python + multimodal fusion)

Images live under `docker/eeg-mne-*`, `docker/eeg-roi-feature-extraction`, and `docker/eeg-biomarker-scoring`. They implement `/app/run.py` entrypoints with paths compatible with `eeg/EEG_PLUGINS_AND_WORKFLOWS.md` (`/data/input`, `/data/output`).

**Source mapping:** [`MNE_BRAINSTORM_PIPELINE_SOURCES.md`](MNE_BRAINSTORM_PIPELINE_SOURCES.md).

## Images (MNE stack)

| Directory | Image tag (example) | Role |
|-----------|---------------------|------|
| `docker/eeg-mne-preprocessing` | `phindagijimana321/eeg-preprocessing-mne:1.0.3` | Filter, notch, reference; optional `metadata/channels.tsv` |
| `docker/eeg-mne-legacy-to-bids` | `phindagijimana321/eeg-legacy-to-bids-mne:1.0.0` | Flat EEG (EDF/BDF/BrainVision/FIF) → BIDS; optional `metadata/channels.tsv` |

**Legacy → BIDS and HPC:** The `eeg_legacy_to_bids` plugin pulls this image from Docker Hub (or your registry). **Build and push** it from `docker/eeg-mne-legacy-to-bids` with the same tag as `plugins/eeg_legacy_to_bids.yaml` before running on a cluster; Apptainer cannot use an image that was never published. Local `docker run` tests work with a locally built tag without pushing.
| `docker/eeg-mne-spike-detection` | `phindagijimana321/eeg-spike-detection-mne:1.0.1` | Baseline envelope + peak detector |
| `docker/eeg-mne-coregistration` | `phindagijimana321/eeg-mri-coregistration-mne:1.0.2` | `trans.fif` passthrough or JSON 4×4 → `eeg_to_mri_trans.fif` |
| `docker/eeg-mne-bem-source-space` | `phindagijimana321/eeg-bem-source-space-mne:1.0.0` | Watershed BEM + volume `src.fif` from T1 (before `forward_model`) |
| `docker/eeg-mne-forward-model` | `phindagijimana321/eeg-forward-model-mne:1.0.10` | `make_forward_solution` (needs `trans`, `src`, BEM sol on input) |
| `docker/eeg-mne-source-localization` | `phindagijimana321/eeg-source-localization-mne:1.0.3` | dSPM inverse (needs `forward_solution.fif`) |
| `docker/eeg-roi-feature-extraction` | `phindagijimana321/eeg-roi-feature-extraction:1.0.1` | Source NIfTI + `region_labels` + `roi_definitions.json` → ROI JSON |
| `docker/eeg-biomarker-scoring` | `phindagijimana321/eeg-biomarker-scoring:1.0.0` | Reads `features/*.json` → biomarker + `viewer_summary.json` |

**Not MNE (later):** Brainstorm, SpikeNet — separate images.

### ROI fusion inputs

- `source/source_map.nii.gz`, `segmentation/region_labels.nii.gz` (resampled to label grid if needed), `metadata/roi_definitions.json` (`{"roi": {"label_ids": [17, …]}}`).
- Optional: `segmentation/structural_metrics.json` or `hippocampal_volumes.json` merged into structural features.

### Biomarker scoring inputs

- `features/roi_source_features.json`, `features/roi_structural_features.json`, `features/concordance_features.json` (from ROI step).
- Optional `metadata/biomarker_scoring_config.yaml`: `left_roi`, `right_roi` (default `hippocampus_left` / `hippocampus_right`).

### Coregistration inputs

- Either `coreg/trans.fif` / `coreg/eeg_to_mri_trans.fif`, **or** `metadata/eeg_to_mri_transform.json` with `"matrix": [[4×4]]` (head→MRI).
- `eeg/clean_raw.fif` required for electrode JSON export.

### Forward model inputs

- `eeg/clean_raw.fif`, `coreg/trans.fif` (or `eeg_to_mri_trans.fif`), `models/src.fif` (or `*-src.fif`), BEM solution file (e.g. `models/bem_sol.fif` or `*-bem-sol.fif`).
- Optional `metadata/forward_config.yaml`: `mindist_mm`, `n_jobs`.

## Build and push (`phindagijimana321`)

Tags must match **`plugins/*.yaml`** (single canonical line per image). Example:

```bash
export REGISTRY=phindagijimana321

docker build -t ${REGISTRY}/eeg-preprocessing-mne:1.0.3 \
  -f docker/eeg-mne-preprocessing/Dockerfile docker/eeg-mne-preprocessing
docker build -t ${REGISTRY}/eeg-legacy-to-bids-mne:1.0.0 \
  -f docker/eeg-mne-legacy-to-bids/Dockerfile docker/eeg-mne-legacy-to-bids
docker build -t ${REGISTRY}/eeg-spike-detection-mne:1.0.1 \
  -f docker/eeg-mne-spike-detection/Dockerfile docker/eeg-mne-spike-detection
docker build -t ${REGISTRY}/eeg-mri-coregistration-mne:1.0.2 \
  -f docker/eeg-mne-coregistration/Dockerfile docker/eeg-mne-coregistration
docker build -t ${REGISTRY}/eeg-bem-source-space-mne:1.0.0 \
  -f docker/eeg-mne-bem-source-space/Dockerfile docker/eeg-mne-bem-source-space
docker build -t ${REGISTRY}/eeg-forward-model-mne:1.0.10 \
  -f docker/eeg-mne-forward-model/Dockerfile docker/eeg-mne-forward-model
docker build -t ${REGISTRY}/eeg-source-localization-mne:1.0.3 \
  -f docker/eeg-mne-source-localization/Dockerfile docker/eeg-mne-source-localization
docker build -t ${REGISTRY}/eeg-roi-feature-extraction:1.0.1 \
  -f docker/eeg-roi-feature-extraction/Dockerfile docker/eeg-roi-feature-extraction
docker build -t ${REGISTRY}/eeg-biomarker-scoring:1.0.0 \
  -f docker/eeg-biomarker-scoring/Dockerfile docker/eeg-biomarker-scoring

docker push ${REGISTRY}/eeg-preprocessing-mne:1.0.3
docker push ${REGISTRY}/eeg-legacy-to-bids-mne:1.0.0
docker push ${REGISTRY}/eeg-spike-detection-mne:1.0.1
docker push ${REGISTRY}/eeg-mri-coregistration-mne:1.0.2
docker push ${REGISTRY}/eeg-bem-source-space-mne:1.0.0
docker push ${REGISTRY}/eeg-forward-model-mne:1.0.10
docker push ${REGISTRY}/eeg-source-localization-mne:1.0.3
docker push ${REGISTRY}/eeg-roi-feature-extraction:1.0.1
docker push ${REGISTRY}/eeg-biomarker-scoring:1.0.0
```

Log in first: `docker login`.

## Runtime layout (bind-mount)

```text
-v /runs/<id>/inputs:/data/input:ro
-v /runs/<id>/intermediate/...:/data/output
```

Override roots: `NIR_INPUT_ROOT`, `NIR_OUTPUT_ROOT`.

## Smoke test (preprocessing)

```bash
docker run --rm \
  -v "$(pwd)/eeg/docker/fixtures:/data/input:ro" \
  -v /tmp/nir-eeg-out:/data/output \
  phindagijimana321/eeg-preprocessing-mne:1.0.3
```

(Provide your own `fixtures/eeg/` with a small `.fif` or `.edf`.)

## Smoke test (legacy → BIDS)

Staging: `eeg/raw/<file>.edf` (or `.fif`) under the input root; optional `metadata/channels.tsv` and `metadata/bids_config.yaml`.

```bash
docker build -t eeg-legacy-to-bids-mne:local -f docker/eeg-mne-legacy-to-bids/Dockerfile docker/eeg-mne-legacy-to-bids
docker run --rm \
  -v /path/to/staging:/data/input:ro \
  -v /tmp/nir-bids-out:/data/output \
  eeg-legacy-to-bids-mne:local
```

Inspect `/tmp/nir-bids-out/bids_dataset/` and `legacy_to_bids_summary.json`. For NIR on HPC, push `phindagijimana321/eeg-legacy-to-bids-mne:1.0.0` (or bump the tag in `plugins/eeg_legacy_to_bids.yaml` after publishing).
