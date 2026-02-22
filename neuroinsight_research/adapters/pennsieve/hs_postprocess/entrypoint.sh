#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
SUBJECTS_DIR="${SUBJECTS_DIR:-$INPUT_DIR/subjects}"
BUNDLE_ROOT="$OUTPUT_DIR/bundle"

LEFT_HS_THRESHOLD="${LEFT_HS_THRESHOLD:--0.070839747728063}"
RIGHT_HS_THRESHOLD="${RIGHT_HS_THRESHOLD:-0.046915816971433}"
LEFT_HIPPO_LABEL="${LEFT_HIPPO_LABEL:-17}"
RIGHT_HIPPO_LABEL="${RIGHT_HIPPO_LABEL:-53}"
QC_ORIENTATION="${QC_ORIENTATION:-coronal}"
QC_SLICE_AXIS="${QC_SLICE_AXIS:-1}"
QC_TOP10_COUNT="${QC_TOP10_COUNT:-10}"
QC_THRESH_FRAC="${QC_THRESH_FRAC:-0.05}"
PDF_OVERLAY_OPACITY="${PDF_OVERLAY_OPACITY:-0.30}"
REPORT_SLICES="${REPORT_SLICES:-3,4,5,6}"
REPORT_INDEXING="${REPORT_INDEXING:-one_based}"
REPORT_TITLE="${REPORT_TITLE:-NeuroInsight Hippocampal Analysis Report}"
NIIVUE_OVERLAY_OPACITY="${NIIVUE_OVERLAY_OPACITY:-0.35}"
NIIVUE_ORIENTATION="${NIIVUE_ORIENTATION:-coronal}"

mkdir -p "$BUNDLE_ROOT"

echo "Running HS Detection Postprocess for subject: $SUBJECT_ID"

python -m neuroinsight_hs.postprocess \
    --subject-id "$SUBJECT_ID" \
    --subjects-dir "$SUBJECTS_DIR" \
    --bundle-root "$BUNDLE_ROOT" \
    --left-label "$LEFT_HIPPO_LABEL" \
    --right-label "$RIGHT_HIPPO_LABEL" \
    --ai-left-th "$LEFT_HS_THRESHOLD" \
    --ai-right-th "$RIGHT_HS_THRESHOLD" \
    --qc-orientation "$QC_ORIENTATION" \
    --qc-slice-axis "$QC_SLICE_AXIS" \
    --qc-top10 "$QC_TOP10_COUNT" \
    --qc-thresh-frac "$QC_THRESH_FRAC" \
    --pdf-opacity "$PDF_OVERLAY_OPACITY" \
    --report-slices "$REPORT_SLICES" \
    --report-indexing "$REPORT_INDEXING" \
    --report-title "$REPORT_TITLE" \
    --niivue-opacity "$NIIVUE_OVERLAY_OPACITY" \
    --niivue-orientation "$NIIVUE_ORIENTATION"

echo "HS Detection Postprocess complete. Output in $BUNDLE_ROOT"
