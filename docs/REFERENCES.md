# References and citations

Literature and links for **NeuroInsight** and the **pipelines/plugins** shipped in this repository.

> **Generated** by `python3 scripts/generate_references_doc.py` (NeuroInsight v0.1.25). Edit YAML `references:` fields and re-run the script instead of editing plugin tables below by hand.

## Citing NeuroInsight

If you use this platform in a publication, cite the software:

Developed by **Philbert Ndagijimana** with **URMC researchers and neurologists**.
Technical overview: [ENGINEERING.md](ENGINEERING.md).

```bibtex
@software{neuroinsight,
  author       = {Ndagijimana, Philbert and URMC collaborators},
  title        = {NeuroInsight: Neuroimaging Pipeline Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  version      = 0.1.25,
  note         = {Developed in collaboration with URMC researchers and neurologists}
}
```

Also cite **each pipeline plugin you ran** (sections below) and any licenses
required by those tools.


## Plugins by domain

Use this section in **Methods**: cite NeuroInsight plus every plugin you executed.

### Domain: `structural_mri`


#### FastSurfer (`fastsurfer`)

- **Definition:** `plugins/fastsurfer.yaml`
- **Plugin version:** 2.4.2
- **Container image:** `deepmi/fastsurfer:cpu-v2.4.2`

**References:**

- Henschel, L., et al. (2020). FastSurfer - A fast and accurate deep learning based neuroimaging pipeline. NeuroImage, 219, 117012.

#### FreeSurfer Longitudinal Reconstruction (`freesurfer_longitudinal`)

- **Definition:** `plugins/freesurfer_longitudinal.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `freesurfer/freesurfer:7.4.1`

**References:**

- Reuter, M., et al. (2012). Within-subject template estimation for unbiased longitudinal image analysis. NeuroImage, 61(4), 1402-1418.

#### FreeSurfer Longitudinal Statistics (`freesurfer_longitudinal_stats`)

- **Definition:** `plugins/freesurfer_longitudinal_stats.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `freesurfer/freesurfer:7.4.1`

**References:**

- https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/LongitudinalTutorial

#### FreeSurfer recon-all (`freesurfer_recon`)

- **Definition:** `plugins/freesurfer_recon.yaml`
- **Plugin version:** 7.4.1
- **Container image:** `freesurfer/freesurfer:7.4.1`

**References:**

- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.

#### FreeSurfer Volumetric Segmentation (`freesurfer_autorecon_volonly`)

- **Definition:** `plugins/freesurfer_autorecon_volonly.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/freesurfer-autorecon-volonly:7.4.1`

**References:**

- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.

#### Hippocampal Sclerosis Analysis (`hs_postprocess`)

- **Definition:** `plugins/hs_postprocess.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/hs-postprocess:1.0.0`

**References:**

- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.
- Iglesias, J.E. et al. (2015). A computational atlas of the hippocampal formation using ex vivo, ultra-high resolution MRI. Neuroimage, 115, 117-137.

#### Hippocampal Subfield Segmentation (T1 + T2) (`segmentha_t2`)

- **Definition:** `plugins/segmentha_t2.yaml`
- **Plugin version:** 7.4.1
- **Container image:** `phindagijimana321/freesurfer-mcr:7.4.1`

**References:**

- Iglesias, J.E. et al. (2015). A computational atlas of the hippocampal formation using ex vivo, ultra-high resolution MRI. Neuroimage, 115, 117-137.

#### Hippocampal Subfield Segmentation (T1) (`segmentha_t1`)

- **Definition:** `plugins/segmentha_t1.yaml`
- **Plugin version:** 7.4.1
- **Container image:** `phindagijimana321/freesurfer-mcr:7.4.1`

**References:**

- Iglesias, J.E. et al. (2015). A computational atlas of the hippocampal formation using ex vivo, ultra-high resolution MRI. Neuroimage, 115, 117-137.

### Domain: `functional_mri`


#### fMRIPrep (`fmriprep`)

- **Definition:** `plugins/fmriprep.yaml`
- **Plugin version:** 23.2.1
- **Container image:** `nipreps/fmriprep:23.2.1`

**References:**

- Esteban, O., et al. (2019). fMRIPrep: a robust preprocessing pipeline for functional MRI. Nature Methods, 16(1), 111-116.

#### XCP-D (`xcpd`)

- **Definition:** `plugins/xcpd.yaml`
- **Plugin version:** 0.6.1
- **Container image:** `pennlinc/xcp_d:0.6.1`

**References:**

- Ciric, R., et al. (2022). XCP-D: A robust pipeline for the post-processing of fMRI data.

### Domain: `diffusion_mri`


#### QSIPrep (`qsiprep`)

- **Definition:** `plugins/qsiprep.yaml`
- **Plugin version:** 0.20.0
- **Container image:** `pennbbl/qsiprep:0.20.0`

**References:**

- Cieslak, M., et al. (2021). QSIPrep: an integrative platform for preprocessing and reconstructing diffusion MRI data. Nature Methods, 18(7), 775-778.

#### QSIRecon (`qsirecon`)

- **Definition:** `plugins/qsirecon.yaml`
- **Plugin version:** 1.1.1
- **Container image:** `pennlinc/qsirecon:1.1.1`

**References:**

- Cieslak, M., et al. (2021). QSIPrep: an integrative platform for preprocessing and reconstructing diffusion MRI data. Nature Methods, 18(7), 775-778.

### Domain: `eeg`


#### EEG Legacy to BIDS (`eeg_legacy_to_bids`)

- **Definition:** `plugins/eeg_legacy_to_bids.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-legacy-to-bids-mne:1.0.0`

**References:**

- https://mne.tools/mne-bids/stable/use.html

#### EEG Preprocessing (`eeg_preprocessing`)

- **Definition:** `plugins/eeg_preprocessing.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-preprocessing-mne:1.0.3`

**References:**

- https://mne.tools/stable/auto_tutorials/preprocessing/

#### EEG Spike Detection (`spike_detection`)

- **Definition:** `plugins/spike_detection.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-spike-detection-mne:1.0.1`

**References:**

- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.

### Domain: `eeg_imaging`


#### Biomarker Scoring (`biomarker_scoring`)

- **Definition:** `plugins/biomarker_scoring.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-biomarker-scoring:1.0.0`

**References:**

- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.

#### EEG Forward Model (`forward_model`)

- **Definition:** `plugins/forward_model.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-forward-model-mne:1.0.10`

**References:**

- https://mne.tools/stable/auto_tutorials/forward/

#### EEG Head Model & Source Space (`bem_source_space`)

- **Definition:** `plugins/bem_source_space.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-bem-source-space-mne:1.0.0`

**References:**

- https://mne.tools/stable/auto_tutorials/forward/

#### EEG Source Localization (Inverse) (`source_localization`)

- **Definition:** `plugins/source_localization.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-source-localization-mne:1.0.3`

**References:**

- https://mne.tools/stable/auto_tutorials/inverse/30_mne_dspm_loreta.html

#### EEG–MRI Coregistration (`eeg_mri_coregistration`)

- **Definition:** `plugins/eeg_mri_coregistration.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-mri-coregistration-mne:1.0.2`

**References:**

- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.
- https://mne.tools/stable/auto_tutorials/preprocessing/80_coreg.html

#### MRI Volumetric Segmentation (`mri_segmentation`)

- **Definition:** `plugins/mri_segmentation.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/freesurfer-autorecon-volonly:7.4.1`

**References:**

- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.

#### ROI Feature Extraction (`roi_feature_extraction`)

- **Definition:** `plugins/roi_feature_extraction.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `phindagijimana321/eeg-roi-feature-extraction:1.0.1`

**References:**

- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.

### Domain: `conversion`


#### DICOM to NIfTI Converter (`dcm2niix`)

- **Definition:** `plugins/dcm2niix.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `nipy/heudiconv:1.3.4`

**References:**

- Li, X., et al. (2016). The first step for neuroimaging data analysis: DICOM to NIfTI conversion. Journal of Neuroscience Methods, 264, 47-56.

### Domain: `epilepsy`


#### MELD Graph Lesion Detection (`meld_graph`)

- **Definition:** `plugins/meld_graph.yaml`
- **Plugin version:** 2.2.4
- **Container image:** `phindagijimana321/meld_graph:v2.2.4-nir2`

**References:**

- Ripart, M. et al. (2025). Detection of epileptogenic focal cortical dysplasia using graph neural networks: a MELD study. JAMA Neurology.
- Spitzer, H., Ripart, M. et al. (2022). Interpretable surface-based detection of focal cortical dysplasias. Brain, 145(11).
- https://github.com/MELDProject/meld_graph

#### TSC Data Preparation (`tsc_data_preparation`)

- **Definition:** `plugins/tsc_data_preparation.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `python:3.11-slim`

**References:**

- Sanchez Fernandez I, et al. Epilepsia 2025. doi:10.1111/epi.70007

#### TSC Registration (ANTs) (`tsc_registration_ants`)

- **Definition:** `plugins/tsc_registration_ants.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `ivansanchezfernandez/bias_correct_resample_and_register_to_mni_with_ants`

**References:**

- Avants BB, et al. ANTs. NeuroImage 2011.

#### TSC Skull Stripping (SynthStrip) (`tsc_skull_strip_synthstrip`)

- **Definition:** `plugins/tsc_skull_strip_synthstrip.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `freesurfer/freesurfer:7.4.1`

**References:**

- Hoopes A, et al. SynthStrip. NeuroImage 2022.

#### TSC T2 Super-Resolution (NiftyMIC) (`tsc_t2_combine_niftymic`)

- **Definition:** `plugins/tsc_t2_combine_niftymic.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `ivansanchezfernandez/combine_t2_files_with_niftymic`

**References:**

- Ebner M, et al. NiftyMIC. NeuroImage 2020.

#### TSC Tuber Segmentation (TSCCNN3D) (`tsc_segmentation_tsccnn3d`)

- **Definition:** `plugins/tsc_segmentation_tsccnn3d.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `ivansanchezfernandez/segment_tubers_and_quantify_tuber_burden_with_tsccnn3d_dropout`

**References:**

- Sanchez Fernandez I, et al. Epilepsia 2025. doi:10.1111/epi.70007
- PubMed: https://pubmed.ncbi.nlm.nih.gov/41258699/

## Legacy pipeline definitions (`pipelines/`)

These YAML files define older monolithic pipeline specs. Prefer plugin citations when you run jobs via the plugin registry.

#### fastsurfer (`fastsurfer`)

- **Definition:** `pipelines/fastsurfer.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `deepmi/fastsurfer:latest`

**References:**

- Henschel, L., et al. (2020). FastSurfer - A fast and accurate deep learning based neuroimaging pipeline. NeuroImage, 219, 117012.
- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.

#### freesurfer_hippocampus (`freesurfer_hippocampus`)

- **Definition:** `pipelines/freesurfer_hippocampus.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `freesurfer/freesurfer:7.4.1`

**References:**

- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.
- Iglesias, J.E. et al. (2015). A computational atlas of the hippocampal formation using ex vivo, ultra-high resolution MRI. Neuroimage, 115, 117-137.

#### qsiprep (`qsiprep`)

- **Definition:** `pipelines/qsiprep.yaml`
- **Plugin version:** 1.0.0
- **Container image:** `pennbbl/qsiprep:latest`

**References:**

- Cieslak, M., et al. (2021). QSIPrep: an integrative platform for preprocessing and reconstructing diffusion MRI data. Nature Methods, 18(7), 775-778.
- Garyfallidis, E., et al. (2014). Dipy, a library for the analysis of diffusion MRI data. Frontiers in Neuroinformatics, 8, 8.

## Deduplicated bibliography (from YAML)

Alphabetical list of all `references:` strings across plugins and pipelines (may include duplicates across tools, e.g. FreeSurfer cited by several plugins).

- Avants BB, et al. ANTs. NeuroImage 2011.
- Cieslak, M., et al. (2021). QSIPrep: an integrative platform for preprocessing and reconstructing diffusion MRI data. Nature Methods, 18(7), 775-778.
- Ciric, R., et al. (2022). XCP-D: A robust pipeline for the post-processing of fMRI data.
- Ebner M, et al. NiftyMIC. NeuroImage 2020.
- Esteban, O., et al. (2019). fMRIPrep: a robust preprocessing pipeline for functional MRI. Nature Methods, 16(1), 111-116.
- Fischl, B. (2012). FreeSurfer. Neuroimage, 62(2), 774-781.
- Garyfallidis, E., et al. (2014). Dipy, a library for the analysis of diffusion MRI data. Frontiers in Neuroinformatics, 8, 8.
- Gramfort, A., et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience, 7, 267.
- Henschel, L., et al. (2020). FastSurfer - A fast and accurate deep learning based neuroimaging pipeline. NeuroImage, 219, 117012.
- Hoopes A, et al. SynthStrip. NeuroImage 2022.
- https://github.com/MELDProject/meld_graph
- https://mne.tools/mne-bids/stable/use.html
- https://mne.tools/stable/auto_tutorials/forward/
- https://mne.tools/stable/auto_tutorials/inverse/30_mne_dspm_loreta.html
- https://mne.tools/stable/auto_tutorials/preprocessing/
- https://mne.tools/stable/auto_tutorials/preprocessing/80_coreg.html
- https://surfer.nmr.mgh.harvard.edu/fswiki/FsTutorial/LongitudinalTutorial
- Iglesias, J.E. et al. (2015). A computational atlas of the hippocampal formation using ex vivo, ultra-high resolution MRI. Neuroimage, 115, 117-137.
- Li, X., et al. (2016). The first step for neuroimaging data analysis: DICOM to NIfTI conversion. Journal of Neuroscience Methods, 264, 47-56.
- PubMed: https://pubmed.ncbi.nlm.nih.gov/41258699/
- Reuter, M., et al. (2012). Within-subject template estimation for unbiased longitudinal image analysis. NeuroImage, 61(4), 1402-1418.
- Ripart, M. et al. (2025). Detection of epileptogenic focal cortical dysplasia using graph neural networks: a MELD study. JAMA Neurology.
- Sanchez Fernandez I, et al. Epilepsia 2025. doi:10.1111/epi.70007
- Spitzer, H., Ripart, M. et al. (2022). Interpretable surface-based detection of focal cortical dysplasias. Brain, 145(11).

## Clinical deployment

URMC: NeuroInsight runs production workflows that support Radiology. See
[CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) (scope, limitations, citations).

## NeuroInsight application stack

NeuroInsight (this repository) is the orchestration layer — web UI, job
scheduling, data transfer, and HPC/SSH/Docker backends. It is **not** a
replacement for citing the neuroimaging tools you actually run.

| Component | Role | Citation / license |
|-----------|------|-------------------|
| NeuroInsight | Platform (MIT) | [CITATION.cff](../CITATION.cff), BibTeX below |
| FastAPI, Uvicorn | HTTP API | https://fastapi.tiangolo.com/ |
| Celery, Redis | Background jobs (optional) | Celery project docs |
| PostgreSQL, SQLAlchemy | Job/metadata store | Standard software acknowledgments |
| React, Vite, TypeScript | Desktop/web UI | Standard software acknowledgments |
| Electron | Desktop shell | https://www.electronjs.org/ |
| Docker / Apptainer-Singularity | Container execution | Cite **container images** in plugin YAML |
| Paramiko | SSH remote execution | Paramiko docs |
| SLURM | HPC batch scheduler | Schultz et al., 2003 (SLURM) if your site requires it |
| MinIO (optional) | S3-compatible staging | MinIO docs |
| Pennsieve connector | `pennsieve2`, AWS Cognito | https://docs.pennsieve.io/ — cite Pennsieve if you publish data there |
| XNAT connector | REST adapter | https://xnat.org/ — cite XNAT if used for archiving |

Tool **license files** (FreeSurfer, MELD, etc.) are separate from literature:
see [TOOL_LICENSES.md](TOOL_LICENSES.md).

