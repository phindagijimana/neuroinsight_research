# HPC Pipeline Submission Guide

Pipeline-specific **input layouts** for submitting jobs on HPC through the NeuroInsight UI.

**Before this guide:**

- Connect HPC/SLURM in the UI — [USER_GUIDE.md § Connecting to HPC](USER_GUIDE.md#connecting-to-hpc-slurm-cluster) (SSH keys, tunnels, SLURM settings, monitoring).
- Tool licenses — [TOOL_LICENSES.md](TOOL_LICENSES.md).

---

## Step 1: Select a Pipeline or Workflow

In the right panel, choose between **Plugins** (single tools) or **Workflows** (chained pipelines).

### Available Workflows

| Workflow | Steps | Input Type | Description |
|----------|-------|------------|-------------|
| Diffusion Full Pipeline | QSIPrep → QSIRecon | BIDS directory | DWI preprocessing and reconstruction |
| fMRI Full Pipeline | fMRIPrep → XCP-D | BIDS directory | fMRI preprocessing and postprocessing |
| FreeSurfer Longitudinal Full | Longitudinal recon-all → Stats | Directory of T1w NIfTIs | Longitudinal cortical analysis |
| Cortical Lesion Detection | recon-all → MELD Graph | Single T1w NIfTI | Epilepsy lesion detection |
| Hippocampal Sclerosis Detection | recon-all → HS Detection | Single T1w NIfTI | Hippocampal sclerosis analysis |
| **Multimodal Epilepsy Biomarker** | **8 steps** (EEG prep → spike → coreg → forward → source → FS vol → ROI features → biomarkers) | **One staging directory** on HPC | EEG + T1 for source imaging and multimodal scoring |

Select the desired workflow from the dropdown (workflow id: `multimodal_epilepsy_biomarker`).

---

## Step 2: Provide Input Data

Input data must already be on the HPC filesystem. Use the **Browse** button to navigate the HPC file system and select your input.

### Input Modes

- **Batch mode** (default): Browse directories, select input, and submit
- **Single mode**: Browse and select a single file

---

## Pipeline-Specific Submission Instructions

### A. Diffusion Full Pipeline (QSIPrep → QSIRecon)

**What it does:** Preprocesses diffusion MRI (DWI) data and performs tractography reconstruction.

**Expected input:** A BIDS-formatted directory containing DWI data.

**Required BIDS structure:**
```
your_bids_dir/
  dataset_description.json
  sub-XXXX/
    ses-YY/           (optional, if multi-session)
      dwi/
        sub-XXXX_dwi.nii.gz
        sub-XXXX_dwi.bval
        sub-XXXX_dwi.bvec
        sub-XXXX_dwi.json
      anat/            (recommended for T1w registration)
        sub-XXXX_T1w.nii.gz
```

**How to submit:**

1. Select **Workflows** tab → choose **Diffusion Full Pipeline**
2. In Batch mode, click **Browse** to navigate to your BIDS directory on HPC
3. Navigate to the BIDS root (the directory containing `dataset_description.json` and `sub-*` folders)
4. Click **Use This Directory** in the browser toolbar
5. Click **Submit Directory as Input (BIDS / multi-file pipelines)**

**Notes:**
- The system auto-detects `subject_id` from the `sub-XXXX` directory structure
- If T1w images are in the proper BIDS `anat/` folder, QSIPrep will use them for anatomical registration (better results)
- If no T1w is available, pass the parameter `anat_modality: none`
- BIDS validation is automatically skipped (using `--skip-bids-validation`)

**Resources:** Default 8 CPUs, 32 GB RAM, 4 hours. Adjust as needed (12+ hours recommended for large datasets).

---

### B. fMRI Full Pipeline (fMRIPrep → XCP-D)

**What it does:** Preprocesses functional MRI (BOLD) data and performs denoising, connectivity analysis, and parcellation.

**Expected input:** A BIDS-formatted directory containing functional BOLD and anatomical T1w data.

**Required BIDS structure:**
```
your_bids_dir/
  dataset_description.json
  sub-XXXX/
    anat/
      sub-XXXX_T1w.nii.gz
    func/
      sub-XXXX_task-rest_bold.nii.gz
      sub-XXXX_task-rest_bold.json
```

**How to submit:**

1. Select **Workflows** tab → choose **fMRI Full Pipeline**
2. In Batch mode, click **Browse** to navigate to your BIDS directory on HPC
3. Navigate to the BIDS root
4. Click **Use This Directory**
5. Click **Submit Directory as Input (BIDS / multi-file pipelines)**

**Notes:**
- T1w anatomical scan is **required** for fMRIPrep
- FreeSurfer license is required and automatically provided
- Output spaces default to `MNI152NLin2009cAsym`
- BIDS validation is automatically skipped

**Resources:** Default 8 CPUs, 32 GB RAM, 4 hours. Recommend 12+ hours for full processing.

---

### C. FreeSurfer Longitudinal Full (CROSS → BASE → LONG → Stats)

**What it does:** Runs the full FreeSurfer longitudinal stream for a subject with 2+ timepoints: cross-sectional recon-all per timepoint, unbiased base template creation, and longitudinal recon-all per timepoint.

**Expected input:** A directory containing 2 or more T1-weighted NIfTI files from different timepoints for the same subject.

**Required structure:**
```
your_input_dir/
  sub-XXXX_ses-baseline_T1w.nii.gz
  sub-XXXX_ses-followup_T1w.nii.gz
  sub-XXXX_ses-year2_T1w.nii.gz      (optional additional timepoints)
```

**How to submit:**

1. Select **Workflows** tab → choose **FreeSurfer Longitudinal Full**
2. In Batch mode, click **Browse** to navigate to the directory containing T1w timepoint files
3. Click **Use This Directory**
4. Click **Submit Directory as Input (BIDS / multi-file pipelines)**

**Notes:**
- The directory must contain at least 2 `.nii.gz` files
- Timepoint IDs are extracted from filenames (the part before `_T1w`)
- The pipeline runs 3 stages: CROSS (per timepoint) → BASE (template) → LONG (per timepoint)
- This is a very long-running pipeline: ~8-14 hours per timepoint

**Resources:** Default 8 CPUs, 48 GB RAM, 28 hours.

---

### D. Multimodal Epilepsy Biomarker (8-step EEG + MRI)

**What it does:** Runs the full NIR multimodal chain: preprocess continuous EEG, spike detection, EEG–MRI coregistration, forward model, source localization, FreeSurfer **volume-only** segmentation on T1, ROI feature fusion, and biomarker scoring.

**Where the data must live:** On the **HPC filesystem** (home directory, project space, or NFS path visible to compute nodes). The SLURM backend **does not copy** large datasets from your laptop; it **symlinks** your chosen paths into `~/…/jobs/<job-id>/inputs/` on the cluster.

**Order of operations (do not skip):**

1. **SSH to the HPC login node** (or another session where your lab NFS mounts are visible). BDSP/BIND paths such as `/mnt/nfs/Gugger_Lab/...` are only valid there—not on your laptop by default.
2. **Optional — build one staging folder** from separate BIDS EEG + BIND MRI trees: from a checkout of this repo on the cluster, run `eeg/scripts/stage_bdsp_bind_multimodal.py` (see the script docstring). Write the output under something like `…/Documents/NeuroInsight_Research/multimodal_<id>/`.
3. **Connect NIR to HPC** — follow [USER_GUIDE.md § Connecting to HPC](USER_GUIDE.md#connecting-to-hpc-slurm-cluster) (Jobs → **Compute → HPC**, connect SSH, **Activate SLURM Backend**).
4. **Submit** the workflow from the UI (steps below) so SLURM runs on the cluster.

**Required layout — one folder** (EEG and T1 must not be split across unrelated parents):

```
your_run_on_hpc/
  eeg/
    raw/
      recording.edf          # or .fif / BrainVision / BDF (see eeg/EEG.md)
  T1w.nii.gz                 # T1 for FreeSurfer vol-only (mri_segmentation step)
```

**Optional** (same folder or subfolders, depending on your study):

- `models/` with BEM / source space / `src.fif` etc. (see `eeg/docker/README.md`); if absent, plugins may fall back to sphere BEM with a logged warning.
- FreeSurfer **license:** see [TOOL_LICENSES.md](TOOL_LICENSES.md).

**How to submit (after HPC is connected in the UI):**

1. Confirm **SLURM Backend** is active.
2. **Workflows** → **Multimodal Epilepsy Biomarker**.
3. **Batch** mode → **Browse** on the HPC side to `your_run_on_hpc` (the directory that contains **both** `eeg/raw/` and `T1w.nii.gz`).
4. **Use This Directory**, then **Submit Directory as Input** (same pattern as BIDS workflows).
5. The API requires a **single staging root**: do not submit only the T1 file; submit the **folder** that contains EEG + T1.

**Notes:**

- If your lab keeps EEG on NFS (example path pattern in `eeg/EEG.md`), ensure **batch nodes** can read that path; otherwise stage a copy or symlink under your HPC home that compute nodes see.
- Wall time is the **sum** of per-step defaults in the workflow; use **Customize** under resources if your cluster allows longer jobs.
- For REST submission, `POST /api/workflows/multimodal_epilepsy_biomarker/submit` with `input_files` listing path(s) that resolve to that **one** staging directory (see `backend/validation/workflow_staging.py`).

---

### E. FreeSurfer recon-all (Single Plugin)

**What it does:** Runs FreeSurfer's full cortical reconstruction on a single T1w scan.

**Expected input:** A single T1-weighted NIfTI file.

**How to submit:**

1. Select **Plugins** tab → choose **FreeSurfer recon-all**
2. Switch to **Single** input mode
3. Click **Browse** to navigate to your T1w file on HPC
4. Select the `.nii.gz` file
5. Click **Submit Job**

**Resources:** Default 8 CPUs, 16 GB RAM, 8 hours.

---

### F. Cortical Lesion Detection (recon-all → MELD Graph)

**What it does:** Runs FreeSurfer recon-all followed by MELD Graph neural network for cortical dysplasia detection in drug-resistant epilepsy.

**Expected input:** A directory containing T1w and optionally FLAIR NIfTI files, OR a single T1w file.

**Option 1: Directory with T1w + FLAIR (recommended for best detection)**

```
your_folder/
  sub-XXXX_T1w.nii.gz
  sub-XXXX_FLAIR.nii.gz       (optional, improves lesion detection)
```

**How to submit (directory mode):**

1. Select **Workflows** tab → choose **Cortical Lesion Detection**
2. In Batch mode, click **Browse** to navigate to the folder containing T1w and FLAIR
3. Click **Use This Directory**
4. Click **Submit Directory as Input (BIDS / multi-file pipelines)**

**Option 2: Single T1w file only**

1. Select **Workflows** tab → choose **Cortical Lesion Detection**
2. Switch to **Single** input mode
3. Click **Browse** and select a T1w `.nii.gz` file
4. Click **Submit Job**

**Notes:**
- Requires FreeSurfer and MELD licenses — [TOOL_LICENSES.md](TOOL_LICENSES.md)
- T1w file is auto-detected by `T1w` or `T1` in the filename
- FLAIR file is auto-detected by `FLAIR` or `flair` in the filename
- Including FLAIR significantly improves lesion detection accuracy
- The `--is_flair` flag is automatically added when FLAIR is detected
- Total runtime: ~8-12 hours (recon-all ~8h + MELD ~30min)

---

## Monitor jobs

SLURM queue panel, job list, and log locations: [USER_GUIDE.md § Connecting to HPC — Step 5](USER_GUIDE.md#step-5-monitor-jobs).

Quick log check on the cluster:
```bash
tail -f ~/neuroinsight/neuroinsight/jobs/<job-id>/logs/slurm-*.out
```

---

## Resource Configuration

You can customize resources before submission by checking **Customize** under Resource Configuration:

| Resource | Default | Recommended for Long Jobs |
|----------|---------|---------------------------|
| Memory | 16 GB | 20-48 GB |
| CPUs | 4 | 4-8 |
| Time Limit | 6 hours | 12-28 hours |
| GPU | None | Not required for most pipelines |

> **Tip:** FreeSurfer longitudinal jobs can take 20+ hours. Set the time limit accordingly.

---

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Cannot connect to localhost:2222" | SSH tunnel not active | Re-run the SSH tunnel command from your local machine |
| "Authentication failed" | SSH key not loaded | Run `ssh-add` with your HPC key |
| Job fails immediately | Backend not set to SLURM | Click "Activate SLURM Backend" after connecting |
| "Path does not exist" error | Wrong input path | Use Browse to navigate; submit the BIDS root, not a subdirectory |
| "No T1w images found" | T1w not in BIDS anat/ folder | Copy T1w NIfTIs to the proper `sub-XX/ses-YY/anat/` directory |
| "BIDS validation failed" | Dataset has BIDS compliance issues | Already handled: `--skip-bids-validation` is auto-added |
| Job stuck at "pending" in UI | Backend restarted, lost SLURM connection | Reconnect SSH and activate SLURM backend |
| "Need at least 2 timepoints" | Wrong input dir for longitudinal | Point to the directory containing the T1w NIfTI files directly |
