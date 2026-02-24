# HPC Pipeline Submission Guide

How to submit neuroimaging pipelines on HPC through the NeuroInsight Research UI.

---

## Prerequisites

### 1. SSH Tunnel from Your Local Machine to the NIR Server

The NIR app runs on an AWS server. You need an SSH tunnel to access the web UI and to relay HPC connections.

```bash
ssh -i /path/to/your-key.pem \
    -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -L 2222:your-hpc-login-node.edu:22 \
    ubuntu@<NIR-SERVER-IP>
```

- `-L 3000:localhost:3000` — tunnels the frontend UI
- `-L 2222:your-hpc-login-node.edu:22` — tunnels SSH to HPC through port 2222

> **Note:** Replace `your-hpc-login-node.edu` with your actual HPC login node hostname (e.g., `hpc.university.edu`).

### 2. SSH Key for HPC Authentication

Your SSH key for the HPC must be loaded into your SSH agent:

```bash
ssh-add ~/.ssh/id_rsa        # or your HPC key
ssh-add -l                    # verify it's loaded
```

The passphrase must be entered once when loading the key. After that, the agent handles authentication.

### 3. License Files

Place these in the NIR project root (`/home/ubuntu/src/NeuroInsight_Research_Tool/`):

- `license.txt` — FreeSurfer license (free from https://surfer.nmr.mgh.harvard.edu/registration.html)
- `meld_license.txt` — MELD Graph license (if using cortical lesion detection)

These are automatically uploaded to HPC job directories during submission.

---

## Step 1: Connect to HPC in the UI

1. Open **http://localhost:3000** in your browser
2. Click **Jobs** in the navigation bar
3. Under **Data Source**, select **HPC**
4. Under **Compute Source**, select **HPC**
5. Fill in the SSH connection fields:
   - **Hostname**: `localhost` (because of the SSH tunnel)
   - **Username**: your HPC username (e.g., `jsmith`)
   - **Port**: `2222` (the tunneled port)
   - **Work Directory**: `~/neuroinsight` (where job directories are created on HPC)
6. Click **Connect** — you should see "Connected to [hostname]"
7. Click **Activate SLURM Backend** (or it auto-activates after connection)

> **Important:** After a browser refresh, you do NOT need to reconnect — the SSH connection persists on the backend. However, if the backend server restarts, you must reconnect.

---

## Step 2: Select a Pipeline or Workflow

In the right panel, choose between **Plugins** (single tools) or **Workflows** (chained pipelines).

### Available Workflows

| Workflow | Steps | Input Type | Description |
|----------|-------|------------|-------------|
| Diffusion Full Pipeline | QSIPrep → QSIRecon | BIDS directory | DWI preprocessing and reconstruction |
| fMRI Full Pipeline | fMRIPrep → XCP-D | BIDS directory | fMRI preprocessing and postprocessing |
| FreeSurfer Longitudinal Full | Longitudinal recon-all → Stats | Directory of T1w NIfTIs | Longitudinal cortical analysis |
| Cortical Lesion Detection | recon-all → MELD Graph | Single T1w NIfTI | Epilepsy lesion detection |
| Hippocampal Sclerosis Detection | recon-all → HS Detection | Single T1w NIfTI | Hippocampal sclerosis analysis |

Select the desired workflow from the dropdown.

---

## Step 3: Provide Input Data

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

### D. FreeSurfer recon-all (Single Plugin)

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

### E. Cortical Lesion Detection (recon-all → MELD Graph)

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
- Requires both `license.txt` (FreeSurfer) and `meld_license.txt` (MELD)
- T1w file is auto-detected by `T1w` or `T1` in the filename
- FLAIR file is auto-detected by `FLAIR` or `flair` in the filename
- Including FLAIR significantly improves lesion detection accuracy
- The `--is_flair` flag is automatically added when FLAIR is detected
- Total runtime: ~8-12 hours (recon-all ~8h + MELD ~30min)

---

## Step 4: Monitor Jobs

### SLURM Queue Monitor
The **SLURM Queue** panel (on the Jobs page) shows real-time SLURM job status, including:
- SLURM Job ID
- Job name
- State (RUNNING, PENDING, COMPLETED, FAILED)
- Wall time elapsed
- Partition and node assignment

This refreshes every 10 seconds.

### Job List
The **Overview of All Processing Jobs** section shows all submitted jobs with:
- Pipeline name and type (Plugin/Workflow)
- Current status and phase
- Compute backend (HPC SLURM / Local Docker)
- Input path and submission time
- Progress bar

Click on a completed job to view results in the Dashboard.

### Checking Job Logs on HPC
Job files are stored at:
```
~/neuroinsight/neuroinsight/jobs/<job-id>/
  ├── inputs/          # Symlinks to input data
  ├── outputs/         # Pipeline outputs
  ├── logs/            # SLURM stdout/stderr logs
  │   ├── slurm-<id>.out
  │   └── slurm-<id>.err
  └── scripts/         # Generated sbatch script and licenses
      ├── run.sh
      ├── pipeline_cmd.sh
      ├── license.txt
      └── meld_license.txt
```

You can SSH into the HPC and check logs directly:
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
