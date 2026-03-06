# Phase 4 — Pennsieve Registration Worksheet

Use this worksheet to register currently ready processors and workflows in Pennsieve.

Scope source: `pennsieve/registration_bundle_phase2_published.yaml`

## A) Register 11 Processors (Ready Now)

For each processor:
1. Pennsieve UI -> `Analysis > Configuration > Create Application`
2. Fill fields from the row below
3. Save
4. Wait until status is `Available`
5. Mark checkbox

| Done | Plugin ID | Application Name | Source URL | Type | CPU | Memory (GB) |
|---|---|---|---|---|---:|---:|
| [ ] | `dcm2niix` | `neuroinsight-dcm2niix` | `docker://phindagijimana321/heudiconv:1.3.4` | `processor` | 2 | 8 |
| [ ] | `fastsurfer` | `neuroinsight-fastsurfer` | `docker://phindagijimana321/fastsurfer:cpu-v2.4.2` | `processor` | 4 | 16 |
| [ ] | `fmriprep` | `neuroinsight-fmriprep` | `docker://phindagijimana321/fmriprep:23.2.1` | `processor` | 16 | 64 |
| [ ] | `freesurfer_autorecon_volonly` | `neuroinsight-freesurfer-autorecon-volonly` | `docker://phindagijimana321/freesurfer:7.4.1` | `processor` | 8 | 32 |
| [ ] | `freesurfer_longitudinal` | `neuroinsight-freesurfer-longitudinal` | `docker://phindagijimana321/freesurfer:7.4.1` | `processor` | 8 | 48 |
| [ ] | `freesurfer_longitudinal_stats` | `neuroinsight-freesurfer-longitudinal-stats` | `docker://phindagijimana321/freesurfer:7.4.1` | `postprocessor` | 4 | 16 |
| [ ] | `freesurfer_recon` | `neuroinsight-freesurfer-recon` | `docker://phindagijimana321/freesurfer:7.4.1` | `processor` | 8 | 32 |
| [ ] | `hs_postprocess` | `neuroinsight-hs-postprocess` | `docker://phindagijimana321/hs-postprocess:1.0.0` | `postprocessor` | 4 | 16 |
| [ ] | `meld_graph` | `neuroinsight-meld-graph` | `docker://phindagijimana321/meld_graph:v2.2.4` | `processor` | 4 | 48 |
| [ ] | `segmentha_t1` | `neuroinsight-segmentha-t1` | `docker://phindagijimana321/freesurfer-mcr:7.4.1` | `processor` | 4 | 16 |
| [ ] | `segmentha_t2` | `neuroinsight-segmentha-t2` | `docker://phindagijimana321/freesurfer-mcr:7.4.1` | `processor` | 4 | 16 |

Processor gate:
- [ ] All 11 processors show `Available`

## B) Register 5 Workflows (Ready Now)

Pennsieve UI -> workflow builder:
- Create named workflow
- Add processors in order
- Wire dependencies (`depends_on`)
- Save and publish

### 1) `neuroinsight-cortical-lesion-detection`
- Node `freesurfer_recon` (no deps)
- Node `meld_graph` depends on `freesurfer_recon`
- [ ] Registered

### 2) `neuroinsight-freesurfer-longitudinal-full`
- Node `freesurfer_longitudinal` (no deps)
- Node `freesurfer_longitudinal_stats` depends on `freesurfer_longitudinal`
- [ ] Registered

### 3) `neuroinsight-hs-detection`
- Node `freesurfer_autorecon_volonly` (no deps)
- Node `hs_postprocess` depends on `freesurfer_autorecon_volonly`
- [ ] Registered

### 4) `neuroinsight-hippo-subfields-t1`
- Node `freesurfer_recon` (no deps)
- Node `segmentha_t1` depends on `freesurfer_recon`
- [ ] Registered

### 5) `neuroinsight-hippo-subfields-t2`
- Node `freesurfer_recon` (no deps)
- Node `segmentha_t2` depends on `freesurfer_recon`
- [ ] Registered

Workflow gate:
- [ ] All 5 workflows are saved and runnable

## C) Deferred (after remaining 3 images publish)

- `fmri_full` requires `xcpd`
- `diffusion_full` requires `qsiprep` and `qsirecon`
