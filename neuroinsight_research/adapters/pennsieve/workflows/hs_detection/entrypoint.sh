#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export FREESURFER_HOME=/usr/local/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh" 2>/dev/null || true

export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
BUNDLE_ROOT="$OUTPUT_DIR/bundle"
mkdir -p "$SUBJECTS_DIR" "$BUNDLE_ROOT"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-8}"

LEFT_HS_THRESHOLD="${LEFT_HS_THRESHOLD:--0.070839747728063}"
RIGHT_HS_THRESHOLD="${RIGHT_HS_THRESHOLD:-0.046915816971433}"
QC_ORIENTATION="${QC_ORIENTATION:-coronal}"
REPORT_SLICES="${REPORT_SLICES:-3,4,5,6}"
NIIVUE_OVERLAY_OPACITY="${NIIVUE_OVERLAY_OPACITY:-0.35}"

T1W=$(find_t1w "$INPUT_DIR")
if [ -z "$T1W" ]; then
    echo "ERROR: No T1w NIfTI file found in $INPUT_DIR" >&2
    echo "Searched: flat, anat/, ses-*/anat/" >&2
    exit 1
fi
echo "Using T1w: $T1W"

echo "=== Step 1/2: FreeSurfer autorecon1 + autorecon2-volonly ==="
recon-all \
    -i "$T1W" \
    -s "$SUBJECT_ID" \
    -sd "$SUBJECTS_DIR" \
    -autorecon1 \
    -autorecon2-volonly \
    -parallel \
    -openmp "$THREADS"

echo "Running mri_segstats on aseg..."
mri_segstats \
    --seg "$SUBJECTS_DIR/$SUBJECT_ID/mri/aseg.auto.mgz" \
    --excludeid 0 \
    --sum "$SUBJECTS_DIR/$SUBJECT_ID/stats/aseg.stats" \
    --i "$SUBJECTS_DIR/$SUBJECT_ID/mri/brain.mgz"

echo "=== Step 2/2: HS Detection Postprocess ==="
python -m neuroinsight_hs.postprocess \
    --subject-id "$SUBJECT_ID" \
    --subjects-dir "$SUBJECTS_DIR" \
    --bundle-root "$BUNDLE_ROOT" \
    --left-label 17 \
    --right-label 53 \
    --ai-left-th "$LEFT_HS_THRESHOLD" \
    --ai-right-th "$RIGHT_HS_THRESHOLD" \
    --qc-orientation "$QC_ORIENTATION" \
    --qc-slice-axis 1 \
    --qc-top10 10 \
    --qc-thresh-frac 0.05 \
    --pdf-opacity 0.30 \
    --report-slices "$REPORT_SLICES" \
    --report-indexing one_based \
    --report-title "NeuroInsight Hippocampal Analysis Report" \
    --niivue-opacity "$NIIVUE_OVERLAY_OPACITY" \
    --niivue-orientation "$QC_ORIENTATION"

echo "HS Detection workflow complete. Output in $OUTPUT_DIR"
