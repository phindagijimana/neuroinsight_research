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
"""

from typing import Dict, List, Tuple

#
# Type: List of (log_marker_regex_or_substring, pct, label)
#
PhaseMilestone = Tuple[str, int, str]

#
# FreeSurfer recon-all (~6-8 hours)
#
# Phases and their typical wall-clock weight:
#   autorecon1 (motion correct, talairach, skull strip)   ~15 min -> 3%
#   autorecon2 (intensity norm, white matter seg, tessellate,
#               smooth, inflate, register, parcellate)    ~4-5 h  -> 70%
#   autorecon3 (sphere, cortical thickness, stats)        ~1-2 h  -> 20%
#   Post-processing (stats, bundle extraction)            ~10 min -> 5%
#
FREESURFER_RECON: List[PhaseMilestone] = [
    # Setup & input validation
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

#
# FastSurfer (~10-60 min depending on GPU/CPU)
#
# Phases:
#   Segmentation CNN       ~1-5 min  -> 35%
#   Surface reconstruction ~5-45 min -> 50%
#   Stats                  ~2 min    -> 10%
#
FASTSURFER: List[PhaseMilestone] = [
    # Setup
    ("run_fastsurfer", 2, "Starting FastSurfer"),
    ("SUBJECTS_DIR", 3, "Setting up directories"),

    # Segmentation (CNN)
    ("Running FastSurferCNN", 5, "Loading segmentation model"),
    ("Loading checkpoint", 8, "Loading model checkpoint"),
    ("Evaluating", 12, "Running CNN segmentation"),
    ("sagittal", 18, "Segmenting sagittal plane"),
    ("coronal", 24, "Segmenting coronal plane"),
    ("axial", 30, "Segmenting axial plane"),
    ("ViewAggregation", 35, "Aggregating views"),

    # Surface reconstruction
    ("recon-surf", 38, "Starting surface recon"),
    ("mri_convert", 40, "Converting volumes"),
    ("mris_inflate", 50, "Inflating surfaces"),
    ("mris_sphere", 58, "Spherical mapping"),
    ("mris_register", 65, "Surface registration"),
    ("mris_ca_label", 72, "Cortical parcellation"),
    ("mris_anatomical_stats", 80, "Anatomical statistics"),
    ("mri_aparc2aseg", 85, "aparc+aseg creation"),

    # Stats & metrics
    ("aseg.stats", 90, "Writing statistics"),
    ("Metrics extracted", 95, "Extracting metrics"),

    # Completion
    ("FastSurfer completed", 100, "Completed"),
]

#
# fMRIPrep (~2-6 hours)
#
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

#
# Generic fallback (any unknown plugin)
# Uses simple elapsed-time fractions of the max time
#
GENERIC: List[PhaseMilestone] = [
    ("Starting", 5, "Initializing"),
    ("Processing", 25, "Processing"),
    ("Running", 50, "Running"),
    ("Writing", 75, "Writing outputs"),
    ("completed", 100, "Completed"),
]

#
# Registry: plugin_id -> milestone list
#
MILESTONES: Dict[str, List[PhaseMilestone]] = {
    "freesurfer_recon": FREESURFER_RECON,
    "freesurfer_recon_long": FREESURFER_RECON,  # same pipeline
    "fastsurfer": FASTSURFER,
    "fastsurfer_seg": FASTSURFER,
    "fmriprep": FMRIPREP,
}

# Shared system phases (prepended to all plugins)
SYSTEM_PHASES: List[PhaseMilestone] = [
    # These are set by the Celery task directly, not from log markers
]


def get_milestones(plugin_id: str) -> List[PhaseMilestone]:
    """Get phase milestones for a plugin, falling back to generic."""
    return MILESTONES.get(plugin_id, GENERIC)
