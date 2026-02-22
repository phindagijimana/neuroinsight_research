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
    ("ds_report", 82, "Writing reports"),
    ("ds_dwi", 85, "Writing DWI derivatives"),
    ("confounds", 88, "Computing confounds"),
    ("carpetplot", 90, "Generating carpet plot"),

    # Completion
    ("Subject results", 93, "Writing subject results"),
    ("Generating boilerplate", 95, "Generating citation boilerplate"),
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
    ("ds_report", 82, "Writing reports"),
    ("ds_recon", 85, "Writing reconstruction outputs"),
    ("atlas", 88, "Atlas-based analysis"),
    ("Generating boilerplate", 92, "Generating citation boilerplate"),

    # Completion
    ("QSIRecon completed successfully", 100, "Completed"),
]

# ══════════════════════════════════════════════════════════════════════
#  fMRIPrep  (~2-6 hours)
# ══════════════════════════════════════════════════════════════════════
FMRIPREP: List[PhaseMilestone] = [
    ("fMRIPrep", 2, "Initializing fMRIPrep"),
    ("Anatomical processing", 8, "Anatomical preprocessing"),
    ("Brain extraction", 15, "Brain extraction"),
    ("Tissue segmentation", 22, "Tissue segmentation"),
    ("Surface reconstruction", 35, "Surface reconstruction"),
    ("BOLD processing", 50, "BOLD preprocessing"),
    ("Slice-timing correction", 55, "Slice-timing correction"),
    ("Head-motion estimation", 60, "Head-motion estimation"),
    ("Susceptibility distortion", 65, "Susceptibility distortion correction"),
    ("Registration", 72, "Registration to standard"),
    ("Confound estimation", 82, "Confound estimation"),
    ("BOLD resampling", 90, "BOLD resampling"),
    ("Generating report", 95, "Generating report"),
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
    ("Generating boilerplate", 94, "Generating citation boilerplate"),
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


def get_milestones(plugin_id: str) -> List[PhaseMilestone]:
    """Get phase milestones for a plugin, falling back to generic."""
    return MILESTONES.get(plugin_id, GENERIC)


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
