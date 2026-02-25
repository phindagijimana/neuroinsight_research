#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-8}"

T1W=$(find_t1w "$INPUT_DIR")
if [ -z "$T1W" ]; then
    echo "ERROR: No T1w NIfTI file found in $INPUT_DIR" >&2
    exit 1
fi

echo "Running FreeSurfer autorecon1 + autorecon2-volonly on: $T1W"
echo "Subject ID: $SUBJECT_ID"

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

echo "FreeSurfer VolOnly + segstats complete. Output in $SUBJECTS_DIR/$SUBJECT_ID"
