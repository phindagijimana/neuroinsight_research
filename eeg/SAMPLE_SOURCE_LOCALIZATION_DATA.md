# Sample data for evaluating EEG + MRI + forward + inverse + cortical visualization

This document lists **public, research-usable** options to evaluate the **full** multimodal story (registered EEG, anatomical MRI, forward + inverse, cortical surface, optional volume overlays). It also explains how that relates to NIR’s **current** demo (toy sphere + synthetic series) versus a **real** bundle.

---

## 1. Recommended: MNE “sample” dataset (single download, end-to-end)

**What it is:** The canonical MNE-Python teaching dataset (`mne.datasets.sample`).

**Contents (high level):**

| Asset | Relevance |
|-------|-----------|
| `MEG/sample_audvis_raw.fif` | Raw **MEG + EEG** (60 EEG channels + MEG), task data |
| MRI / `subjects/sample/mri/T1.mgz` (and related) | **Anatomical** T1 |
| **FreeSurfer** `subjects/sample` | **Pial / white / inflated** surfaces, segmentation |
| **BEM** surfaces (`bem/*.fif`) | **Forward model** inputs (3-layer BEM typical) |
| **Source space**, **trans** (`*-meg-*-trans.fif`) | **Coregistration** MEG/head ↔ MRI |
| Forward solution `*fwd.fif`, inverse `*inv.fif` (after you compute or use shipped examples) | **Forward + inverse** workflow |

**Size:** On the order of **~1.5 GB** downloaded (varies by version); not something to bundle inside the git repo by default.

**License / use:** Distributed for **documentation and tutorials** with MNE-Python; use per [MNE dataset terms](https://mne.tools/stable/documentation/datasets.html).

**Why it’s ideal for evaluation:** One `data_path()` call gives you **everything** needed to reproduce MNE tutorials: **coreg**, **BEM forward**, **minimum-norm / dSPM / sLORETA**, **STC on cortex**, **volume** morphs.

**NIR gap today:** The bundled **sample job** in NeuroInsight does **not** ship this dataset; it uses **synthetic** EEG + **toy** NIfTI + **UV sphere** mesh. To “evaluate like production,” you **mirror** outputs from this pipeline into NIR’s **result bundle** (manifest + surfaces + time series + optional NIfTI overlays)—see §4.

---

## 2. Lighter or complementary options

| Dataset | Role | Notes |
|---------|------|--------|
| **`mne.datasets.fsaverage`** | Average cortical surface / morph targets | Small; often used **with** `sample` for morphing |
| **`mne.datasets.spm_face`** | M/EEG + MRI for faces paradigm | Another full-ish example; smaller than `sample` in some installs |
| **EEG-only public sets** (e.g. BCI, sleep) | Signal QA only | **No** MRI → not enough for **surface** localization alone |
| **OpenNeuro** | Many EEG+fMRI/MRI studies | Great for **real** science; each study has its own layout; more curation work |

For **fast** iteration on **viewer + bundle contract**, **`sample`** remains the least ambiguous.

---

## 3. What “good multimodal visualization” means here

| Layer | “Real” evaluation | Current NIR demo |
|--------|-------------------|------------------|
| **Anatomical** | T1 / brainmask in Niivue | Toy sphere in a box |
| **Functional / source** | **Subject pial** (or inflated) + **STC** / mapped scalars | **Procedural sphere** + synthetic vertex series |
| **Registration** | `trans` + BEM + aligned electrodes | N/A in demo |
| **Forward + inverse** | `fwd.fif` + `inv.fif` / `stc` | N/A in demo |

The **Viewer** can show **real** anatomy and **real** cortical coloring **once** the **job output** contains real meshes + time-varying source amplitudes (and optional stat volumes). The limitation today is **data + pipeline**, not only the UI.

---

## 4. Mirroring into NIR (evaluation path)

**Goal:** Produce a **job output directory** that NIR can serve like any other completed job:

1. **Imaging View:** `anatomy/t1w.nii.gz` (or `.nii`) from MRI (convert `T1.mgz` → NIfTI if needed).
2. **Multimodal manifest:** `nir_multimodal_manifest.json` pointing at:
   - EEG file path (or a **re-exported** `.fif` window),
   - MRI ref,
   - **Cortical NPZ** (or extend format): **vertices, faces, `data` (V×T), `times`** in **subject** space.
3. **Optional:** NIfTI overlay of **abs** or **stat** map on the **T1** grid for Niivue (separate from mesh).

**Practical approaches:**

- **A. Offline script (recommended for eval):**  
  Python env with **MNE** (+ optional **nibabel** for NIfTI export). Clone tutorial: compute/read `fwd`, `inv`, apply inverse to a short raw window → **sample STC** → **interpolate to pial** vertices → write **NPZ** + manifest under a fake `outputs/<job_id>/`.

- **B. Future NIR plugin:**  
  Container runs the same steps; writes the **same** bundle layout. Viewer stays unchanged.

- **C. Pre-baked tarball:**  
  Host a **minimal** eval bundle (mesh decimated + 10 s STC) on S3/internal; **seed** or **import** like other jobs—avoid committing multi‑GB files to git.

---

## 5. Helper script in this repo

Run (from repo root, with `mne` installed):

```bash
python3 eeg/scripts/print_mne_sample_layout.py
```

This downloads (if missing) the MNE **sample** dataset and prints **paths** to raw MRI, surfaces, bem—useful as a checklist before wiring exports to NIR’s manifest format.

---

## 6. Summary

| Question | Answer |
|----------|--------|
| Can we **find** sample data? | **Yes** — start with **`mne.datasets.sample`**. |
| Does it include **EEG + MRI + forward + inverse + cortex**? | **Yes** (MEG+EEG; full MNE source-analysis stack). |
| Can NIR **visualize** that today? | **Only if** you **export** real meshes + STC-like series into the **bundle** the API serves; the **default bundled job** is still **demo** quality. |
| Next step? | Use **`print_mne_sample_layout.py`**, then an **export script** or **plugin** that writes `nir_multimodal_manifest.json` + NPZ + T1 NIfTI from `sample`. |
