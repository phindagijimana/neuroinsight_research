#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"
WORK_DIR="/data/work"

export FS_LICENSE=/license/license.txt

mkdir -p "$OUTPUT_DIR/fmriprep" "$OUTPUT_DIR/xcpd" "$WORK_DIR"

BIDS_DIR=$(find "$INPUT_DIR" -name "dataset_description.json" -exec dirname {} \; | head -1)
if [ -z "$BIDS_DIR" ]; then
    BIDS_DIR="$INPUT_DIR"
fi

PARTICIPANT="${PARTICIPANT_LABEL:-sub-01}"
NPROCS="${NPROCS:-4}"
MEM_MB="${MEM_MB:-8000}"

echo "=== Step 1/2: fMRIPrep ==="
fmriprep "$BIDS_DIR" "$OUTPUT_DIR/fmriprep" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --fs-license-file "$FS_LICENSE" \
    --nprocs "$NPROCS" \
    --mem-mb "$MEM_MB" \
    --work-dir "$WORK_DIR/fmriprep" \
    --output-spaces MNI152NLin2009cAsym \
    --skip-bids-validation \
    --notrack

echo "=== Step 2/2: XCP-D ==="
xcp_d "$OUTPUT_DIR/fmriprep" "$OUTPUT_DIR/xcpd" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --nprocs "$NPROCS" \
    --mem-gb "$(( MEM_MB / 1000 ))" \
    --work-dir "$WORK_DIR/xcpd" \
    --notrack

echo "fMRI Full Pipeline workflow complete. Output in $OUTPUT_DIR"
