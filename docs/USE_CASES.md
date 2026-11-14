# URMC use cases (research workflows)

!!! warning "Output use"
    **All outputs: research use only.** **Clinical support** use is allowed only on
    **your responsibility** — [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md).

NeuroInsight at the **University of Rochester Medical Center (URMC)** runs
**research workflows** in programs associated with **Radiology** and **Neurology**.
The platform **orchestrates** containerized pipelines (Transfer → Jobs on local
Docker or **HPC/SLURM**); it does **not** replace radiologists,
neuroradiologists, or neurologists.

Developed by **Philbert Ndagijimana** with **URMC researchers and neurologists**.
Deployment context: [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md).
Output policy: [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md).

Workflow and plugin IDs match the in-app **Docs** tab and `workflows/` /
`plugins/` in this repository.

---

## How use cases are grouped

| Category | Meaning |
|----------|---------|
| **AI / ML workflows** | Deep learning or graph models (e.g. cortical parcellation CNNs, lesion detection GNNs, TSC segmentation) |
| **Classical pipelines** | Established software with rule-based or optimization-based methods (FreeSurfer, BIDS apps, MNE-Python EEG) |
| **Hybrid** | Classical preprocessing → AI inference (e.g. recon-all → MELD Graph) |

---

## Radiology — research workflows

| Use case | Type | NeuroInsight workflow / plugin | Research role (outputs **research use only**) |
|----------|------|--------------------------------|--------------|
| Cortical surface & volumetry | AI + classical | **FastSurfer** (`fastsurfer`); **FreeSurfer recon** (`freesurfer_recon`, `freesurfer_autorecon_volonly`) | Quantitative parcellation and volumes for read support |
| Longitudinal structural MRI | Classical | **FreeSurfer Longitudinal Pipeline** (`wf_freesurfer_longitudinal_full`) | Unbiased within-subject templates across timepoints |
| Hippocampal subfields (T1 / T1+T2) | Classical | **Hippocampal Subfield Segmentation** (`hippo_subfields_t1`, `hippo_subfields_t2`); **SegmentHA** (`segmentha_t1`, `segmentha_t2`) | Mesial temporal lobe quantification |
| Focal cortical dysplasia / lesion (MRI) | Hybrid | **Focal Cortical Lesion Detection** (`cortical_lesion_detection`: recon → **MELD Graph** `meld_graph`) | Surface-based lesion likelihood maps for epilepsy imaging review |
| Hippocampal sclerosis (T1) | Hybrid | **Hippocampal Sclerosis Detection** (`wf_hs_detection_v1`: recon → **HS postprocess** `hs_postprocess`) | Asymmetry, lateralization, QC overlays |
| DICOM → research format | Classical | **dcm2niix** (`dcm2niix`) | Ingest for downstream pipelines |
| Functional MRI preprocessing | Classical | **fMRI Full Pipeline** (`fmri_full`: fMRIPrep → XCP-D) | BIDS fMRI derivatives for research and translational reads |
| Diffusion MRI preprocessing | Classical | **Diffusion Full Pipeline** (`diffusion_full`: QSIPrep → QSIRecon) | DWI preprocessing and reconstruction |
| Cohort TBI (DoD program) | Hybrid | TRACK-TBI structural workflow at scale (see [TRACK_TBI.md](TRACK_TBI.md)) | **600 subjects × 2 timepoints** on HPC; deliverable in **DoD technical report** (UR–Penn collaboration) |

**Typical Radiology flow on NeuroInsight:** data from **XNAT** or study storage →
**Transfer** to HPC scratch → **Jobs** → optional **Transfer** of QC outputs or
derivatives. Input layouts: [HPC_PIPELINE_SUBMISSION_GUIDE.md](HPC_PIPELINE_SUBMISSION_GUIDE.md).

---

## Neurology — research workflows

| Use case | Type | NeuroInsight workflow / plugin | Research role (outputs **research use only**) |
|----------|------|--------------------------------|--------------|
| EEG screening (epileptiform activity) | Classical (+ signal processing) | **EEG Epilepsy Screening** (`basic_eeg_epilepsy_detection`: preprocessing → **spike detection** `spike_detection`) | Spike candidates for neurology review |
| EEG + MRI source imaging | Classical | **EEG Source Localization** (`eeg_source_localization`); steps: preprocessing, coregistration, BEM, forward model, **source localization** | Distributed source estimates for surgical planning support |
| Multimodal epilepsy biomarker | Hybrid | **Multimodal Epilepsy Biomarker** (`multimodal_epilepsy_biomarker`) — EEG + structural MRI, ROI features, **biomarker scoring** | Fused laterality/concordance summaries for multidisciplinary review |
| Tuberous sclerosis (MRI) | Hybrid | **Tuberous Sclerosis Detection** (`tuberous_sclerosis_detection`) — prep, SynthStrip, NiftyMIC, ANTs, **TSCCNN3D** segmentation | TSC lesion burden and registration-supported metrics |
| Lesion / FCD MRI (with Radiology) | Hybrid | **Focal Cortical Lesion Detection** (`cortical_lesion_detection`) | Shared with Radiology for surgical epilepsy workups |

Neurology workflows often share **structural MRI** steps with Radiology (FreeSurfer
/ FastSurfer, MELD) and add **EEG/MNE** chains staged in a single directory on HPC.

---

## Cross-cutting platform capabilities

| Capability | Radiology | Neurology |
|------------|-----------|-----------|
| **Pennsieve / XNAT** connectors | Study archive ingest & export | Multimodal study packages |
| **HPC (CIRC / BlueHive)** | Long-running recon, cohort batches | Long EEG–MRI chains |
| **Viewer (NIfTI + overlays)** | Segmentation & lesion overlays | Source and ROI review |

---

## Outputs: research use; clinical support on your responsibility

- **Research use only** — default intended use for all pipeline outputs.
- **Clinical support** — you **may** use outputs to support reads or neurology
  workflows **only if you and your institution** assume responsibility (IRB,
  validation, sign-out policy, tool licenses, applicable law).
- NeuroInsight does not make clinical-use claims or provide medical advice.
- Cite NeuroInsight and **each underlying tool** — [REFERENCES.md](REFERENCES.md).
- [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md)

---

## Related pages

| Page | Topic |
|------|--------|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | Transfer, Jobs, backends |
| [RESEARCH_OUTPUT_USE.md](RESEARCH_OUTPUT_USE.md) | Research-only output policy |
| [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) | URMC deployment |
| [TRACK_TBI.md](TRACK_TBI.md) | DoD cohort workflow |
| [PRODUCT.md](PRODUCT.md) | Product scope |
