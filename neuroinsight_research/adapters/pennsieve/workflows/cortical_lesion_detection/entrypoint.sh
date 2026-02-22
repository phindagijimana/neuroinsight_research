#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export FREESURFER_HOME=/usr/local/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh" 2>/dev/null || true

export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR" "$OUTPUT_DIR/meld"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-4}"

T1W=$(find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -1)
if [ -z "$T1W" ]; then
    echo "ERROR: No NIfTI file found in $INPUT_DIR" >&2
    exit 1
fi

echo "=== Step 1/2: FreeSurfer recon-all ==="
recon-all -i "$T1W" -s "$SUBJECT_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

echo "=== Step 2/2: MELD Graph lesion detection ==="
cd /app
python scripts/new_patient_pipeline/new_pt_pipeline.py \
    -id "$SUBJECT_ID" \
    -sd "$SUBJECTS_DIR" \
    -od "$OUTPUT_DIR/meld"

echo "Cortical Lesion Detection workflow complete. Output in $OUTPUT_DIR"
