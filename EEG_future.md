# EEG & Multimodal (EEG + Imaging) — Deferred for Future Versions

**Status:** Disabled by default as of 2026-06-23. The platform currently focuses
on **imaging only**. All EEG and multimodal (EEG + imaging) capability described
here is built and present in the repository but **switched off behind a feature
flag** — nothing was deleted. It is intended to be re-enabled and expanded in a
future version.

This document inventories everything EEG-related that exists today, explains
exactly how it is turned off, how to turn it back on, and what we plan to grow
next.

---

## 1. How EEG is currently disabled (feature flag)

EEG is gated by a single backend feature flag. When off, EEG/multimodal plugins
and workflows are never loaded into the registry, the EEG UI is hidden, and EEG
sample/demo jobs are not seeded.

| Layer | Mechanism | File |
|---|---|---|
| Config | `eeg_enabled: bool = False` (env `EEG_ENABLED`) | `backend/core/config.py` |
| Registry | Skips plugins/workflows whose `domain` is `eeg` or `eeg_imaging` when the flag is off (`EEG_DOMAINS`) | `backend/core/plugin_registry.py` |
| API | `GET /api/config` exposes `features.eeg_enabled` to the client | `backend/main.py` |
| Sample jobs | EEG demo jobs only seeded when the flag is on | `backend/main.py` (`ensure_sample_eeg_jobs`) |
| Frontend flags | `FeatureFlagsProvider` / `useFeatureFlags()` reads `/api/config` (defaults to imaging-only) | `frontend/src/contexts/FeatureFlagsContext.tsx`, `frontend/src/main.tsx`, `frontend/src/services/api.ts` (`getConfig`) |
| Frontend UI | EEG/multimodal categories filtered; Signal/Multimodal viewer tabs hidden; EEG sample-demo UI hidden | `PipelineSelector.tsx`, `pages/ViewerPage.tsx`, `pages/JobsPage.tsx`, `pages/DashboardPage.tsx` |

### Re-enabling EEG

1. Set `EEG_ENABLED=true` in `.env` (or the environment).
2. Restart the app (`./research restart`, or `./research stop app && ./research start`).
3. The frontend automatically reflects the flag via `/api/config` — no rebuild
   strictly required, but rebuild if you changed frontend code.

Verify after enabling:

```bash
curl -s http://localhost:<port>/api/config            # features.eeg_enabled: true
curl -s "http://localhost:<port>/api/plugins?user_selectable_only=false"  # EEG domains return
```

With the flag **off**, the registry serves 19 plugins / 8 workflows (imaging
only). With it **on**, EEG adds 10 plugins and 3 workflows (29 / 11 total).

---

## 2. The two EEG domains

Every plugin and workflow carries a `domain:` field. Two domains are treated as
EEG and excluded when the flag is off:

- **`eeg`** — pure EEG tools (MNE-based preprocessing, spike detection, BIDS conversion).
- **`eeg_imaging`** — multimodal steps that combine EEG with structural MRI
  (coregistration, source localization, biomarker scoring). Note this includes
  `mri_segmentation`, which is an MRI tool that exists **only** to feed the
  multimodal source-localization pipeline; it is therefore treated as EEG.

Imaging domains that remain active: `structural_mri`, `functional_mri`,
`diffusion_mri`, `epilepsy`, `conversion`.

---

## 3. Plugins (10) — `plugins/*.yaml`

### Pure EEG (`domain: eeg`)

| ID | Version | Container image |
|---|---|---|
| `eeg_legacy_to_bids` | 1.0.0 | `phindagijimana321/eeg-legacy-to-bids-mne:1.0.0` |
| `eeg_preprocessing` | 1.0.0 | `phindagijimana321/eeg-preprocessing-mne:1.0.3` |
| `spike_detection` | 1.0.0 | `phindagijimana321/eeg-spike-detection-mne:1.0.1` |

### Multimodal (`domain: eeg_imaging`)

| ID | Version | Container image |
|---|---|---|
| `eeg_mri_coregistration` | 1.0.0 | `phindagijimana321/eeg-mri-coregistration-mne:1.0.2` |
| `bem_source_space` | 1.0.0 | `phindagijimana321/eeg-bem-source-space-mne:1.0.0` |
| `forward_model` | 1.0.0 | `phindagijimana321/eeg-forward-model-mne:1.0.10` |
| `source_localization` | 1.0.0 | `phindagijimana321/eeg-source-localization-mne:1.0.3` |
| `mri_segmentation` | 1.0.0 | `phindagijimana321/freesurfer-autorecon-volonly:7.4.1` |
| `roi_feature_extraction` | 1.0.0 | `phindagijimana321/eeg-roi-feature-extraction:1.0.1` |
| `biomarker_scoring` | 1.0.0 | `phindagijimana321/eeg-biomarker-scoring:1.0.0` |

---

## 4. Workflows (3) — `workflows/*.yaml`

| ID | Domain | Steps (plugin chain) |
|---|---|---|
| `basic_eeg_epilepsy_detection` | `eeg` | eeg_preprocessing → spike_detection |
| `eeg_source_localization` | `eeg_imaging` | eeg_preprocessing → spike_detection → eeg_mri_coregistration → bem_source_space → forward_model → source_localization |
| `multimodal_epilepsy_biomarker` | `eeg_imaging` | eeg_preprocessing → spike_detection → eeg_mri_coregistration → bem_source_space → forward_model → source_localization → mri_segmentation → roi_feature_extraction → biomarker_scoring |

---

## 5. Container processors (9) — `docker/eeg-*`

Each directory holds the Dockerfile + `app/run.py` for one EEG step. All are
MNE-Python based unless noted.

- `docker/eeg-mne-legacy-to-bids`
- `docker/eeg-mne-preprocessing`
- `docker/eeg-mne-spike-detection`
- `docker/eeg-mne-coregistration`
- `docker/eeg-mne-bem-source-space`
- `docker/eeg-mne-forward-model`
- `docker/eeg-mne-source-localization`
- `docker/eeg-roi-feature-extraction`
- `docker/eeg-biomarker-scoring`

Pinned image references/digests live in `docker/processors/required-images.yaml`.

---

## 6. Backend modules

| File | Purpose |
|---|---|
| `backend/services/eeg_preview.py` | MNE-backed time-series preview for the Signal View (`/api/results/{id}/eeg_preview`) |
| `backend/services/sample_eeg_jobs.py` | Seeds synthetic EEG demo jobs (FIF + toy T1) — only when `eeg_enabled` |
| `backend/services/multimodal_bundle.py` | Bundles multimodal (EEG + imaging) outputs |
| `backend/execution/workflow_merge.py` | Merges per-step outputs for chained workflows (used by multimodal chains) |
| `backend/execution/workflow_nir_env.py` | NIR environment wiring for workflow execution |
| `backend/validation/workflow_staging.py` | Staging validation for EEG/multimodal input layouts |
| `backend/routes/results.py` | Exposes the `eeg_preview` result endpoint |
| `backend/execution/slurm_backend.py` | SLURM submission paths used by EEG/multimodal HPC runs |

Helper scripts: `scripts/submit_multimodal_slurm.py`, `scripts/submit_plugin_slurm.py`.

> Note: these modules remain importable and are not gated individually. They are
> simply unreachable through the UI/registry while the flag is off (no EEG jobs
> can be created, and `eeg_preview` is only hit by EEG result paths). Sample-job
> seeding is the one startup path explicitly guarded by the flag.

---

## 7. Frontend (React/TypeScript)

### Dedicated EEG components — `frontend/src/components/`

| Component | Purpose |
|---|---|
| `EegViewerPanel.tsx` | Signal View — EEG/EDF/FIF time-series viewer (MNE preview) |
| `EegBrainFusionPanel.tsx` | Multimodal View — EEG signal + brain volume side by side |
| `MultimodalLinkageCard.tsx` | Links EEG ↔ imaging results in the multimodal view |
| `CorticalSourceViewer.tsx` | three.js cortical source-map viewer for source localization |

### Utilities / wiring

- `frontend/src/utils/viewerQuery.ts` — `ViewerTab = 'eeg' | 'imaging' | 'eeg-brain'`
- `frontend/src/utils/resultFiles.ts` — `isEegResultPath()` classifies EEG outputs
- `PipelineSelector.tsx` — maps `eeg`/`eeg_imaging` domains to `eeg`/`multimodal` UI categories (filtered out when flag off)

These render only inside the Signal/Multimodal viewer tabs, which are hidden when
the flag is off; the tab state is also coerced back to `imaging`.

---

## 8. Documentation already in-repo (`eeg/`)

- `eeg/EEG.md`
- `eeg/EEG_PLUGINS_AND_WORKFLOWS.md`
- `eeg/SAMPLE_SOURCE_LOCALIZATION_DATA.md`
- `eeg/docker/README.md`
- `eeg/docker/MNE_BRAINSTORM_PIPELINE_SOURCES.md`
- Scripts: `eeg/scripts/` (HPC source-localization runners, multimodal staging,
  sample-layout printer, local image pruning).

---

## 9. Roadmap — to expand in future versions

Planned work to graduate EEG from "present but disabled" to a first-class,
supported modality:

- [ ] Make `eeg_enabled` a per-organization / per-deployment setting (not just env).
- [ ] Surface EEG/multimodal plugins in `/docs` and the home page when enabled.
- [ ] Validate and pin all `phindagijimana321/eeg-*` images (digests) and add a
      CI smoke test per processor.
- [ ] Harden the multimodal staging contract (`workflow_staging.py`) and document
      the expected `eeg/raw` + `T1w.nii.gz` input layout end to end.
- [ ] Expand the Signal View (montages, annotations, longer windows) and the
      Multimodal/Source viewers (source-map overlays, time-locked scrubbing).
- [ ] Replace synthetic sample jobs with a small curated demo dataset.
- [ ] Add EEG-specific QC reporting to the dashboard.
- [ ] Re-enable EEG sample-demo seeding and verify the full
      `multimodal_epilepsy_biomarker` chain on local Docker and HPC/SLURM.

---

## 10. Quick reference — files changed to disable EEG

Backend: `backend/core/config.py`, `backend/core/plugin_registry.py`, `backend/main.py`
Frontend: `frontend/src/contexts/FeatureFlagsContext.tsx` (new), `frontend/src/main.tsx`,
`frontend/src/services/api.ts`, `frontend/src/components/PipelineSelector.tsx`,
`frontend/src/pages/ViewerPage.tsx`, `frontend/src/pages/JobsPage.tsx`,
`frontend/src/pages/DashboardPage.tsx`

To bring EEG back: set `EEG_ENABLED=true` and restart. See §1.
