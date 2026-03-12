"""
Phase Milestones -- Fixed progress percentages per pipeline phase.

Each plugin defines a list of (log_marker, percentage, label) tuples.
When the Celery worker sees a log_marker in the container's stdout,
it jumps the job's progress to that fixed percentage.

The percentages are weighted estimates based on typical wall-clock time
for each phase.  They are NOT computed dynamically -- they are
hand-tuned constants that represent "how far through the pipeline
are we" when a given phase is reached.

Phases are matched in ORDER.  The worker checks each marker against
the latest log output.  Once a marker is matched, progress jumps to
that percentage (never goes backwards).

Coverage: every plugin in plugins/*.yaml has milestones here.
"""

from typing import Dict, List, Tuple

#
# Type: List of (log_marker_regex_or_substring, pct, label)
#
PhaseMilestone = Tuple[str, int, str]
WorkflowMilestone = Tuple[str, int, str]

# ══════════════════════════════════════════════════════════════════════
#  FreeSurfer recon-all  (~6-8 hours)
# ══════════════════════════════════════════════════════════════════════
FREESURFER_RECON: List[PhaseMilestone] = [
    ("recon-all", 2, "Initializing recon-all"),
    ("SUBJECTS_DIR", 3, "Setting up subject directory"),

    # autorecon1
    ("MotionCorrect", 5, "Motion correction"),
    ("mri_convert", 6, "Converting input format"),
    ("Talairach", 8, "Talairach registration"),
    ("NUIntensityCorrection", 10, "Intensity correction (N3)"),
    ("SkullStripping", 14, "Skull stripping"),

    # autorecon2
    ("EMRegister", 18, "EM registration"),
    ("CANormalize", 20, "CA normalize"),
    ("CARegister", 25, "CA register (atlas)"),
    ("SubCortSeg", 30, "Subcortical segmentation"),
    ("IntensityNormalization2", 33, "Intensity normalization 2"),
    ("WhiteMatterSegmentation", 36, "White matter segmentation"),
    ("Fill", 38, "Filling ventricles"),
    ("Tessellate", 42, "Tessellating hemispheres"),
    ("Smooth1", 45, "Smoothing surface 1"),
    ("Inflation1", 48, "Inflating surface 1"),
    ("QSphere", 52, "Quasi-sphere mapping"),
    ("FixTopology", 56, "Fixing topology"),
    ("MakeWhiteSurface", 60, "Generating white surface"),
    ("Smooth2", 63, "Smoothing surface 2"),
    ("Inflation2", 65, "Inflating surface 2"),
    ("SphericalMapping", 68, "Spherical mapping"),
    ("IpsilateralSurfaceReg", 72, "Surface registration"),
    ("CorticalParcellation", 75, "Cortical parcellation (Desikan)"),
    ("PialSurface", 78, "Generating pial surface"),

    # autorecon3
    ("CorticalParcellation2", 82, "Cortical parcellation (DKT)"),
    ("CorticalRibbon", 85, "Cortical ribbon mask"),
    ("CorticalThickness", 88, "Computing cortical thickness"),
    ("ParcellationStats", 91, "Parcellation statistics"),
    ("CorticalParcellation3", 93, "Cortical parcellation (BA)"),
    ("WM/GMContrast", 95, "WM/GM contrast"),

    # Completion
    ("recon-all.*finished", 97, "recon-all finished"),
    ("FreeSurfer recon-all completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  FreeSurfer autorecon-volonly  (~15-40 min, no surfaces)
# ══════════════════════════════════════════════════════════════════════
FREESURFER_VOLONLY: List[PhaseMilestone] = [
    ("Running FreeSurfer autorecon1", 3, "Starting autorecon1 + volonly"),
    ("recon-all", 5, "Initializing recon-all"),
    ("SUBJECTS_DIR", 6, "Setting up subject directory"),

    # autorecon1
    ("MotionCorrect", 10, "Motion correction"),
    ("mri_convert", 12, "Converting input format"),
    ("Talairach", 18, "Talairach registration"),
    ("NUIntensityCorrection", 25, "Intensity correction (N3)"),
    ("SkullStripping", 35, "Skull stripping"),

    # autorecon2-volonly (no surface stages)
    ("EMRegister", 42, "EM registration"),
    ("CANormalize", 48, "CA normalize"),
    ("CARegister", 55, "CA register (atlas)"),
    ("SubCortSeg", 65, "Subcortical segmentation"),
    ("IntensityNormalization2", 72, "Intensity normalization 2"),
    ("WhiteMatterSegmentation", 80, "White matter segmentation"),

    # mri_segstats
    ("mri_segstats", 88, "Running segstats on aseg"),
    ("aseg.stats", 92, "Writing aseg statistics"),

    # Completion
    ("FreeSurfer VolOnly.*completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  FreeSurfer longitudinal  (~20+ hours for 3 stages)
# ══════════════════════════════════════════════════════════════════════
FREESURFER_LONGITUDINAL: List[PhaseMilestone] = [
    ("Discovering timepoints", 2, "Discovering timepoints"),
    ("Found timepoint", 4, "Found timepoints"),
    ("Total timepoints", 5, "Timepoints validated"),

    # Stage 1: Cross-sectional (~40% of total)
    ("STAGE 1.*Cross-sectional", 6, "Stage 1: Cross-sectional processing"),
    ("Processing CROSS", 8, "Running cross-sectional recon-all"),
    ("MotionCorrect", 10, "Cross: Motion correction"),
    ("Talairach", 14, "Cross: Talairach registration"),
    ("SkullStripping", 18, "Cross: Skull stripping"),
    ("SubCortSeg", 22, "Cross: Subcortical segmentation"),
    ("Tessellate", 26, "Cross: Tessellating"),
    ("SphericalMapping", 30, "Cross: Spherical mapping"),
    ("CorticalParcellation", 34, "Cross: Cortical parcellation"),
    ("SKIP.*already completed", 36, "Cross: Resuming (skipped completed)"),

    # Stage 2: Base template (~25% of total)
    ("STAGE 2.*Base template", 40, "Stage 2: Building base template"),
    ("Building base template", 42, "Creating unbiased template"),
    ("recon-all -base", 44, "Base: recon-all running"),

    # Stage 3: Longitudinal (~35% of total)
    ("STAGE 3.*Longitudinal", 65, "Stage 3: Longitudinal processing"),
    ("Processing LONG", 68, "Running longitudinal recon-all"),
    ("recon-all -long", 70, "Long: recon-all running"),

    # Completion
    ("longitudinal processing complete", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  FreeSurfer longitudinal stats  (~5-15 min)
# ══════════════════════════════════════════════════════════════════════
FREESURFER_LONGITUDINAL_STATS: List[PhaseMilestone] = [
    ("Extracting longitudinal stats", 5, "Starting stats extraction"),
    ("SUBJECTS_DIR", 8, "Setting up SUBJECTS_DIR"),
    ("Found LONG dir", 15, "Found longitudinal directories"),
    ("Copying per-timepoint stats", 30, "Copying per-timepoint stats"),
    ("Extracting stats for", 50, "Extracting stats"),
    ("Generating longitudinal summary", 75, "Generating summary"),
    ("Written summary", 90, "Summary written"),
    ("Longitudinal stats extraction completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  FastSurfer  (~10-60 min depending on GPU/CPU)
# ══════════════════════════════════════════════════════════════════════
FASTSURFER: List[PhaseMilestone] = [
    ("run_fastsurfer", 2, "Starting FastSurfer"),
    ("SUBJECTS_DIR", 3, "Setting up directories"),

    # Segmentation (CNN)
    ("run_prediction", 5, "Loading segmentation model"),
    ("Loading checkpoint", 8, "Loading model checkpoint"),
    ("Conforming image", 10, "Conforming input image"),
    ("Run coronal prediction", 14, "Segmenting coronal plane"),
    ("coronal inference", 22, "Coronal inference complete"),
    ("Run sagittal prediction", 26, "Segmenting sagittal plane"),
    ("sagittal inference", 34, "Sagittal inference complete"),
    ("Run axial prediction", 38, "Segmenting axial plane"),
    ("axial inference", 44, "Axial inference complete"),
    ("ViewAggregation", 48, "Aggregating views"),

    # Surface reconstruction
    ("recon-surf", 52, "Starting surface recon"),
    ("mri_convert", 55, "Converting volumes"),
    ("mris_inflate", 62, "Inflating surfaces"),
    ("mris_sphere", 68, "Spherical mapping"),
    ("mris_register", 74, "Surface registration"),
    ("mris_ca_label", 80, "Cortical parcellation"),
    ("mris_anatomical_stats", 86, "Anatomical statistics"),
    ("mri_aparc2aseg", 90, "aparc+aseg creation"),

    # Stats & metrics
    ("aseg.stats", 90, "Writing statistics"),
    ("Metrics extracted", 95, "Extracting metrics"),

    # Completion
    ("FastSurfer completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  QSIPrep  (~2-8 hours, nipype-based)
# ══════════════════════════════════════════════════════════════════════
QSIPREP: List[PhaseMilestone] = [
    ("qsiprep_wf", 3, "QSIPrep workflow started"),

    # Anatomical preprocessing (~20% of total)
    ("anat_preproc_wf", 5, "Anatomical preprocessing"),
    ("synthstrip", 8, "SynthStrip skull stripping"),
    ("Finished.*synthstrip", 12, "Skull stripping complete"),
    ("rigid_acpc_resample", 15, "ACPC alignment"),
    ("anat_nlin_normalization", 18, "MNI normalization (ANTs — may take 30-60 min)"),
    ("Finished.*anat_nlin_normalization", 28, "MNI normalization complete"),
    ("register_t1_to_raw", 30, "T1-to-DWI registration"),
    ("Finished.*register_t1_to_raw", 32, "T1-to-DWI registration complete"),
    ("acpc_aseg_to_dseg", 33, "Segmentation labeling"),
    ("seg_rpt", 35, "Generating segmentation report"),

    # DWI preprocessing (~50% of total)
    ("dwi_preproc_wf", 38, "DWI preprocessing"),
    ("pre_eddy_b0_ref", 40, "Pre-eddy B0 reference"),
    ("b0_ref_mask_to_lps", 42, "B0 mask reorientation"),
    ("eddy", 45, "Eddy current correction (may take 30+ min)"),
    ("Finished.*eddy", 58, "Eddy correction complete"),
    ("hmc_sdc_wf", 60, "Head motion / distortion correction"),
    ("dwi_denoise_wf", 62, "Denoising DWI"),
    ("merge_dwis", 65, "Merging DWI volumes"),
    ("Finished.*merge_dwis", 67, "DWI merge complete"),

    # Registration & resampling (~15% of total)
    ("b0_to_anat_registration", 70, "B0-to-anatomical registration"),
    ("Finished.*b0_to_anat", 74, "DWI-anat registration complete"),
    ("dwi_resampling", 76, "Resampling DWI to template"),
    ("Finished.*dwi_resampling", 80, "DWI resampling complete"),

    # Derivatives & reports (~10%)
    ("ds_report_wf", 82, "Writing reports"),
    ("ds_dwi_t1", 85, "Writing DWI derivatives"),
    ("confounds_wf", 88, "Computing confounds"),
    ("carpet_seg", 90, "Generating carpet plot"),

    # Completion
    ("Subject results", 93, "Writing subject results"),
    ("resource monitor", 95, "Finalizing"),
    ("QSIPrep completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  QSIRecon  (~30 min - 3 hours, nipype-based)
# ══════════════════════════════════════════════════════════════════════
QSIRECON: List[PhaseMilestone] = [
    ("qsirecon", 3, "QSIRecon workflow started"),

    # Setup & loading
    ("Loading.*recon.*spec", 6, "Loading reconstruction spec"),
    ("participant", 8, "Processing participant"),

    # Reconstruction (~70%)
    ("recon_wf", 12, "Starting reconstruction workflow"),
    ("importing_dwi", 15, "Importing preprocessed DWI"),
    ("Finished.*importing", 18, "DWI import complete"),
    ("recon_scalars", 22, "Computing scalar maps"),
    ("mrtrix", 28, "Running MRtrix3 processing"),
    ("Finished.*mrtrix", 35, "MRtrix3 complete"),
    ("dsi_studio", 30, "Running DSI Studio"),
    ("dipy", 32, "Running Dipy processing"),
    ("tractography", 40, "Running tractography"),
    ("Finished.*tractography", 50, "Tractography complete"),
    ("connectivity", 55, "Computing connectivity matrices"),
    ("Finished.*connectivity", 62, "Connectivity complete"),
    ("bundle_map", 65, "Creating bundle maps"),

    # Scalar & metric computation (~20%)
    ("fa_map", 70, "Computing FA map"),
    ("md_map", 73, "Computing MD map"),
    ("rd_map", 76, "Computing RD map"),
    ("ad_map", 78, "Computing AD map"),

    # Output & reports (~10%)
    ("ds_report_wf", 82, "Writing reports"),
    ("ds_recon_wf", 85, "Writing reconstruction outputs"),
    ("atlas_wf", 88, "Atlas-based analysis"),
    ("workflow completed", 92, "Workflow completed"),

    # Completion
    ("QSIRecon completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  fMRIPrep  (~2-6 hours)
# ══════════════════════════════════════════════════════════════════════
FMRIPREP: List[PhaseMilestone] = [
    ("fMRIPrep started", 2, "Initializing fMRIPrep"),

    # Anatomical preprocessing (~60% of total due to FreeSurfer)
    # Use "Executing" prefix to avoid matching early "Setting-up" lines
    ("Executing.*brain_extraction_wf", 5, "Brain extraction"),
    ("Executing.*anat_template_wf", 8, "Building anatomical template"),
    ("Finished.*brain_mask", 12, "Brain mask complete"),
    ("Executing.*skull_strip_extern", 15, "Surface reconstruction started"),
    ("Executing.*gcareg", 18, "FreeSurfer autorecon"),
    ("Executing.*autorecon2_vol", 22, "FreeSurfer volume processing"),
    ("Finished.*autorecon2_vol", 30, "Volume processing complete"),
    ("Executing.*autorecon_surfs", 32, "FreeSurfer surface reconstruction"),
    ("Finished.*autorecon_surfs", 50, "Surface reconstruction complete"),
    ("Executing.*register_template_wf", 55, "Template registration"),
    ("Finished.*anat_norm", 58, "Anatomical normalization complete"),

    # BOLD preprocessing (~35% of total)
    ("Finished.*hmc_boldref", 60, "BOLD reference complete"),
    ("Finished.*slice_timing_correction", 63, "Slice-timing correction complete"),
    ("Executing.*bold_bold_trans_wf", 66, "BOLD transformation"),
    ("Executing.*bold_confounds_wf\\.acompcor", 70, "Computing aCompCor confounds"),
    ("Finished.*acompcor", 75, "Confound estimation"),
    ("Finished.*bold_confounds_wf\\.concat", 80, "Confounds complete"),
    ("Executing.*carpetplot", 83, "Generating carpet plot"),

    # Reports & completion (~5%)
    ("Finished.*ds_report", 88, "Writing reports"),
    ("Finished.*ds_bold_t1w", 92, "Writing BOLD derivatives"),
    ("resource monitor", 95, "Finalizing"),
    ("fMRIPrep finished", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  XCP-D  (~30 min - 2 hours)
# ══════════════════════════════════════════════════════════════════════
XCPD: List[PhaseMilestone] = [
    ("xcp_d", 3, "Starting XCP-D"),
    ("participant", 5, "Processing participant"),

    # Postprocessing stages
    ("postprocess_wf", 10, "Post-processing workflow"),
    ("denoise_wf", 18, "Denoising BOLD"),
    ("Finished.*denoise", 28, "Denoising complete"),
    ("confound_regression", 32, "Confound regression"),
    ("bandpass_filter", 38, "Bandpass filtering"),
    ("Finished.*bandpass", 42, "Filtering complete"),
    ("smoothing", 48, "Spatial smoothing"),
    ("resampling", 55, "Resampling to standard"),
    ("Finished.*resampling", 60, "Resampling complete"),

    # Connectivity & parcellation
    ("connectivity", 65, "Computing functional connectivity"),
    ("parcellation", 72, "Atlas parcellation"),
    ("Finished.*connectivity", 78, "Connectivity complete"),

    # Reports & quality control
    ("qc_report", 82, "Quality control report"),
    ("ds_report", 88, "Writing reports"),
    ("carpet", 90, "Generating carpet plot"),

    # Completion
    ("write_derivative_description", 94, "Finalizing outputs"),
    ("XCP-D completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  MELD Graph  (~30 min - 2 hours)
# ══════════════════════════════════════════════════════════════════════
MELD_GRAPH: List[PhaseMilestone] = [
    ("Running MELD Graph", 5, "Starting MELD Graph"),

    # Setup & data staging
    ("fs_outputs", 10, "Linking FreeSurfer outputs"),
    ("new_pt_pipeline", 12, "Running new patient pipeline"),

    # Feature extraction (~50%)
    ("feature_extraction", 18, "Extracting cortical features"),
    ("smoothing", 25, "Smoothing features"),
    ("thickness", 30, "Processing cortical thickness"),
    ("curvature", 35, "Processing curvature"),
    ("sulcal_depth", 40, "Processing sulcal depth"),
    ("FLAIR", 45, "Processing FLAIR features"),
    ("feature.*complete", 50, "Feature extraction complete"),

    # Harmonisation & prediction (~35%)
    ("harmon", 55, "Harmonising features"),
    ("predict", 62, "Running lesion prediction model"),
    ("classifier", 68, "Running classifier"),
    ("threshold", 72, "Thresholding predictions"),
    ("cluster", 78, "Clustering detected lesions"),

    # Reports (~15%)
    ("predictions_reports", 85, "Generating prediction reports"),
    ("Copying.*predictions", 90, "Copying results"),

    # Completion
    ("MELD Graph completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  SegmentHA_T1  (~20-40 min)
# ══════════════════════════════════════════════════════════════════════
SEGMENTHA_T1: List[PhaseMilestone] = [
    ("SUBJECTS_DIR", 3, "Setting up SUBJECTS_DIR"),
    ("segmentHA_T1", 8, "Starting hippocampal segmentation"),

    # Processing stages (FreeSurfer segmentHA outputs progress to stdout)
    ("Reading input", 12, "Reading input volumes"),
    ("Building model", 18, "Building segmentation model"),
    ("Optimizing", 25, "Optimizing mesh"),
    ("left.*hippo", 35, "Segmenting left hippocampus"),
    ("right.*hippo", 55, "Segmenting right hippocampus"),
    ("left.*amygdala", 65, "Segmenting left amygdala"),
    ("right.*amygdala", 75, "Segmenting right amygdala"),
    ("Writing.*volumes", 85, "Writing output volumes"),
    ("Writing.*stats", 90, "Writing statistics"),

    # Completion
    ("SegmentHA_T1 completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  SegmentHA_T2  (~25-50 min, uses T2 for sharper boundaries)
# ══════════════════════════════════════════════════════════════════════
SEGMENTHA_T2: List[PhaseMilestone] = [
    ("SUBJECTS_DIR", 3, "Setting up SUBJECTS_DIR"),
    ("segmentHA_T2", 8, "Starting hippocampal segmentation (T1+T2)"),

    # Processing stages
    ("Reading input", 10, "Reading input volumes"),
    ("Reading.*T2", 14, "Reading T2 volume"),
    ("Building model", 18, "Building segmentation model"),
    ("Registering T2", 22, "Registering T2 to T1"),
    ("Optimizing", 28, "Optimizing mesh"),
    ("left.*hippo", 35, "Segmenting left hippocampus"),
    ("right.*hippo", 52, "Segmenting right hippocampus"),
    ("left.*amygdala", 62, "Segmenting left amygdala"),
    ("right.*amygdala", 72, "Segmenting right amygdala"),
    ("Writing.*volumes", 82, "Writing output volumes"),
    ("Writing.*stats", 90, "Writing statistics"),

    # Completion
    ("SegmentHA_T2 completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  HS Postprocess  (~2-10 min)
# ══════════════════════════════════════════════════════════════════════
HS_POSTPROCESS: List[PhaseMilestone] = [
    ("SUBJECTS_DIR", 3, "Setting up directories"),
    ("BUNDLE_ROOT", 5, "Preparing bundle directory"),

    # Processing stages
    ("neuroinsight_hs.postprocess", 10, "Starting HS postprocessing"),
    ("subject-id", 12, "Processing subject"),
    ("Loading.*volumes", 18, "Loading segmentation volumes"),
    ("asymmetry", 25, "Computing asymmetry index"),
    ("laterality", 32, "Analyzing laterality"),
    ("metrics", 40, "Computing metrics"),
    ("qc", 50, "Generating QC images"),
    ("overlay", 60, "Creating overlay images"),
    ("PDF.*report", 72, "Generating PDF report"),
    ("NiiVue", 80, "Creating 3D viewer data"),
    ("Writing.*json", 88, "Writing metrics JSON"),

    # Completion
    ("postprocess.*complete", 95, "Postprocessing complete"),
    ("HS postprocess completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  dcm2niix / HeuDiConv  (~1-10 min)
# ══════════════════════════════════════════════════════════════════════
DCM2NIIX: List[PhaseMilestone] = [
    ("Running.*dcm2niix", 5, "Starting DICOM conversion"),
    ("dcm2niix", 8, "Running dcm2niix"),

    # Conversion progress
    ("Found.*DICOM", 15, "Found DICOM files"),
    ("Convert", 25, "Converting series"),
    ("Compressing", 45, "Compressing NIfTI"),
    ("Anonymiz", 55, "Anonymizing headers"),
    ("Sorting", 65, "Sorting output files"),
    ("slices", 70, "Processing slices"),
    ("Warning", 75, "Processing (with warnings)"),
    ("\\.nii", 82, "NIfTI files generated"),
    ("\\.json", 88, "JSON sidecars generated"),

    # Completion
    ("DICOM to NIfTI conversion completed", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  Generic fallback (any plugin without specific milestones)
#
#  Matches common patterns found across many neuroimaging tools:
#  setup echoes, processing markers, completion messages.
# ══════════════════════════════════════════════════════════════════════
GENERIC: List[PhaseMilestone] = [
    # Setup phase
    ("mkdir -p", 3, "Creating directories"),
    ("set -e", 4, "Initializing"),
    ("SUBJECTS_DIR", 5, "Setting up environment"),
    ("Starting|Initializing|Loading", 8, "Starting"),

    # Early processing
    ("Reading|Importing|Found", 15, "Reading inputs"),
    ("Running|Processing|Executing", 25, "Processing"),
    ("Converting|Building|Preparing", 35, "Processing"),

    # Mid processing
    ("Finished|Complete|Done", 50, "Mid-point reached"),
    ("Writing|Saving|Generating", 65, "Writing outputs"),

    # Late processing
    ("Report|Summary|Statistics|Stats", 80, "Generating reports"),
    ("Copying|Moving|Extracting", 88, "Finalizing outputs"),

    # Completion
    ("completed successfully", 95, "Nearly complete"),
    ("completed|finished|done", 100, "Completed"),
]


# ══════════════════════════════════════════════════════════════════════
#  Registry: plugin_id -> milestone list
#
#  Every plugin defined in plugins/*.yaml MUST have an entry here.
# ══════════════════════════════════════════════════════════════════════
MILESTONES: Dict[str, List[PhaseMilestone]] = {
    # FreeSurfer family
    "freesurfer_recon": FREESURFER_RECON,
    "freesurfer_autorecon_volonly": FREESURFER_VOLONLY,
    "freesurfer_longitudinal": FREESURFER_LONGITUDINAL,
    "freesurfer_longitudinal_stats": FREESURFER_LONGITUDINAL_STATS,
    "segmentha_t1": SEGMENTHA_T1,
    "segmentha_t2": SEGMENTHA_T2,

    # FastSurfer
    "fastsurfer": FASTSURFER,
    "fastsurfer_seg": FASTSURFER,

    # Diffusion
    "qsiprep": QSIPREP,
    "qsirecon": QSIRECON,

    # fMRI
    "fmriprep": FMRIPREP,
    "xcpd": XCPD,

    # Cortical lesion detection
    "meld_graph": MELD_GRAPH,

    # HS detection
    "hs_postprocess": HS_POSTPROCESS,

    # DICOM conversion
    "dcm2niix": DCM2NIIX,
}

# Shared system phases (prepended to all plugins)
SYSTEM_PHASES: List[PhaseMilestone] = []

# ══════════════════════════════════════════════════════════════════════
#  Workflow Step Weights
#
#  Maps workflow_id -> list of fractional weights for each step.
#  Weights reflect approximate wall-clock time ratios so the overall
#  progress bar advances smoothly across steps.
#
#  Sum of weights per workflow should equal 1.0.
# ══════════════════════════════════════════════════════════════════════
WORKFLOW_STEP_WEIGHTS: Dict[str, List[float]] = {
    # fMRI Full: fmriprep (~4h) + xcpd (~1h)
    "fmri_full": [0.80, 0.20],

    # Diffusion Full: qsiprep (~4h) + qsirecon (~1.5h)
    "diffusion_full": [0.75, 0.25],

    # FreeSurfer Longitudinal Full: freesurfer_longitudinal (~20h) + stats (~10min)
    "wf_freesurfer_longitudinal_full": [0.97, 0.03],

    # Cortical Lesion Detection: freesurfer_recon (~6h) + meld_graph (~1h)
    "cortical_lesion_detection": [0.85, 0.15],

    # HS Detection: freesurfer_autorecon_volonly (~30min) + hs_postprocess (~5min)
    "wf_hs_detection_v1": [0.85, 0.15],

    # Hippocampal Subfields T1: freesurfer_recon (~6h) + segmentha_t1 (~30min)
    "hippo_subfields_t1": [0.92, 0.08],

    # Hippocampal Subfields T1+T2: freesurfer_recon (~6h) + segmentha_t2 (~40min)
    "hippo_subfields_t2": [0.90, 0.10],

    # Tuberous Sclerosis Detection weighted phases: 5,10,15,20,25
    # Normalized to sum 1.0 for step-scaling fallback logic.
    "tuberous_sclerosis_detection": [
        0.0666666667,  # 5/75
        0.1333333333,  # 10/75
        0.2000000000,  # 15/75
        0.2666666667,  # 20/75
        0.3333333333,  # 25/75
    ],
}

# Workflow-level checkpoints (global percentages across whole workflow).
# These are used to provide stable stage progress for multi-step workflows.
WORKFLOW_MILESTONES: Dict[str, List[WorkflowMilestone]] = {
    "fmri_full": [
        ("fMRIPrep started", 5, "fMRIPrep initializing"),
        ("Executing.*brain_extraction_wf", 10, "Anatomical brain extraction"),
        ("Executing.*gcareg", 20, "FreeSurfer autorecon started"),
        ("Finished.*autorecon2_vol", 35, "FreeSurfer volume stage complete"),
        ("Finished.*autorecon_surfs", 50, "FreeSurfer surface stage complete"),
        ("Finished.*anat_norm", 60, "Anatomical normalization complete"),
        ("Finished.*slice_timing_correction", 70, "BOLD timing correction complete"),
        ("Finished.*bold_confounds_wf\\.concat", 80, "fMRIPrep confounds complete"),
        ("fMRIPrep finished", 85, "fMRIPrep complete"),
        ("xcp_d", 90, "XCP-D started"),
        ("Finished.*connectivity", 95, "XCP-D connectivity complete"),
        ("XCP-D completed successfully", 99, "XCP-D complete"),
    ],
    "diffusion_full": [
        ("qsiprep_wf", 5, "QSIPrep workflow started"),
        ("anat_preproc_wf", 10, "Anatomical preprocessing"),
        ("Finished.*anat_nlin_normalization", 20, "Anatomical normalization complete"),
        ("dwi_preproc_wf", 30, "DWI preprocessing"),
        ("Finished.*eddy", 45, "Eddy correction complete"),
        ("Finished.*merge_dwis", 55, "DWI merge complete"),
        ("Finished.*dwi_resampling", 65, "DWI resampling complete"),
        ("QSIPrep completed successfully", 75, "QSIPrep complete"),
        ("qsirecon", 80, "QSIRecon started"),
        ("Finished.*tractography", 88, "Tractography complete"),
        ("Finished.*connectivity", 94, "Connectivity complete"),
        ("QSIRecon completed successfully", 99, "QSIRecon complete"),
    ],
    "cortical_lesion_detection": [
        ("recon-all", 5, "FreeSurfer started"),
        ("MotionCor(?:rect)?", 10, "FreeSurfer motion correction"),
        ("Talairach", 15, "Talairach alignment"),
        ("CA\\s*Reg|CA Register", 20, "Atlas registration"),
        ("SubCort\\s*Seg|SubCortSeg", 30, "Subcortical segmentation"),
        ("Tessellate", 45, "Surface tessellation"),
        ("SphericalMapping", 58, "Surface mapping"),
        ("CorticalParcellation", 70, "Cortical parcellation"),
        ("FreeSurfer recon-all completed", 80, "FreeSurfer complete"),
        ("Running MELD Graph", 85, "MELD Graph started"),
        ("feature.*complete", 90, "Feature extraction complete"),
        ("cluster", 95, "Lesion clustering"),
        ("MELD Graph completed successfully", 99, "MELD Graph complete"),
    ],
    "tuberous_sclerosis_detection": [
        ("TSC_STAGE:DATA_PREP_DONE", 5, "TSC data preparation complete"),
        ("TSC_STAGE:SKULL_STRIP_DONE", 15, "Skull stripping complete"),
        ("TSC_STAGE:T2_COMBINE_DONE", 30, "T2 combination complete"),
        ("TSC_STAGE:REGISTRATION_DONE", 50, "MNI registration complete"),
        ("TSC_STAGE:SEGMENTATION_DONE", 75, "Tuber segmentation complete"),
    ],
    "wf_freesurfer_longitudinal_full": [
        ("STAGE 1.*Cross-sectional", 10, "Cross-sectional stage"),
        ("SubCortSeg", 20, "Cross subcortical segmentation"),
        ("CorticalParcellation", 35, "Cross cortical parcellation"),
        ("STAGE 2.*Base template", 50, "Base template stage"),
        ("recon-all -base", 60, "Building base template"),
        ("STAGE 3.*Longitudinal", 70, "Longitudinal stage"),
        ("recon-all -long", 80, "Longitudinal recon-all running"),
        ("longitudinal processing complete", 90, "Longitudinal recon complete"),
        ("Extracting longitudinal stats", 94, "Stats extraction started"),
        ("Written summary", 98, "Stats summary written"),
        ("Longitudinal stats extraction completed", 99, "Longitudinal workflow complete"),
    ],
    "wf_hs_detection_v1": [
        ("Running FreeSurfer autorecon1", 10, "FreeSurfer volonly started"),
        ("Talairach", 20, "Talairach registration"),
        ("SkullStripping", 35, "Skull stripping complete"),
        ("SubCortSeg", 55, "Subcortical segmentation"),
        ("aseg.stats", 70, "Volume stats written"),
        ("FreeSurfer VolOnly.*completed", 82, "Volumetric stage complete"),
        ("neuroinsight_hs.postprocess", 88, "HS postprocess started"),
        ("asymmetry", 93, "Asymmetry analysis"),
        ("PDF.*report", 96, "Report generation"),
        ("HS postprocess completed", 99, "HS workflow complete"),
    ],
    "hippo_subfields_t1": [
        ("recon-all", 5, "FreeSurfer started"),
        ("SkullStripping", 15, "Skull stripping"),
        ("SubCortSeg", 25, "Subcortical segmentation"),
        ("Tessellate", 40, "Surface tessellation"),
        ("SphericalMapping", 55, "Surface mapping"),
        ("CorticalParcellation", 65, "Parcellation"),
        ("FreeSurfer recon-all completed", 80, "FreeSurfer complete"),
        ("segmentHA_T1", 88, "SegmentHA T1 started"),
        ("right.*amygdala", 95, "Amygdala segmentation"),
        ("SegmentHA_T1 completed successfully", 99, "Hippo subfields complete"),
    ],
    "hippo_subfields_t2": [
        ("recon-all", 5, "FreeSurfer started"),
        ("SkullStripping", 15, "Skull stripping"),
        ("SubCortSeg", 25, "Subcortical segmentation"),
        ("Tessellate", 40, "Surface tessellation"),
        ("SphericalMapping", 55, "Surface mapping"),
        ("CorticalParcellation", 65, "Parcellation"),
        ("FreeSurfer recon-all completed", 80, "FreeSurfer complete"),
        ("segmentHA_T2", 88, "SegmentHA T2 started"),
        ("Registering T2", 92, "T2 registration"),
        ("right.*amygdala", 96, "Amygdala segmentation"),
        ("SegmentHA_T2 completed successfully", 99, "Hippo subfields complete"),
    ],
}


def get_workflow_step_weights(workflow_id: str, num_steps: int) -> List[float]:
    """Get step weights for a workflow, falling back to equal weights."""
    weights = WORKFLOW_STEP_WEIGHTS.get(workflow_id, [])
    if len(weights) == num_steps:
        return weights
    return [1.0 / num_steps] * num_steps


def get_milestones(plugin_id: str) -> List[PhaseMilestone]:
    """Get phase milestones for a plugin, falling back to generic."""
    return MILESTONES.get(plugin_id, GENERIC)


def get_workflow_milestones(workflow_id: str) -> List[WorkflowMilestone]:
    """Get workflow-level stage checkpoints for stable progress tracking."""
    return WORKFLOW_MILESTONES.get(workflow_id, [])


def get_plugin_checkpoint_milestones(plugin_id: str, step: int = 5) -> List[PhaseMilestone]:
    """Get plugin milestones quantized into coarse stage checkpoints.

    This normalizes plugin progress into stable increments (default 5%),
    while preserving marker ordering and monotonicity.
    """
    base = get_milestones(plugin_id)
    if not base:
        return []

    qstep = max(1, int(step))
    checkpoints: List[PhaseMilestone] = []
    last_pct = 0

    for marker, pct, label in base:
        qpct = int(round(float(pct) / qstep) * qstep)
        qpct = max(qstep, min(100, qpct))
        if qpct <= last_pct:
            continue
        checkpoints.append((marker, qpct, label))
        last_pct = qpct

    return checkpoints


def get_coverage_report() -> Dict[str, str]:
    """Return a mapping of plugin_id -> 'specific' | 'generic' for all known plugins.

    Useful for verifying that every plugin has dedicated milestones.
    """
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        report = {}
        for plugin in registry.list_plugins(user_selectable_only=False):
            if plugin.id in MILESTONES:
                report[plugin.id] = "specific"
            else:
                report[plugin.id] = "generic (fallback)"
        return report
    except Exception:
        return {pid: "specific" for pid in MILESTONES}
