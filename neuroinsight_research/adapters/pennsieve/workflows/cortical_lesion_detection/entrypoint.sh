#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export FREESURFER_HOME=/usr/local/freesurfer
source "$FREESURFER_HOME/SetUpFreeSurfer.sh" 2>/dev/null || true

export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR" "$OUTPUT_DIR/meld"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-4}"

T1W=$(find_t1w "$INPUT_DIR")
if [ -z "$T1W" ]; then
    echo "ERROR: No T1w NIfTI file found in $INPUT_DIR" >&2
    echo "Searched: flat, anat/, ses-*/anat/" >&2
    exit 1
fi
echo "Using T1w: $T1W"

echo "=== Step 1/2: FreeSurfer recon-all ==="
recon-all -i "$T1W" -s "$SUBJECT_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

echo "=== Step 2/2: MELD Graph lesion detection ==="

# Stage T1w and FLAIR into MELD's expected layout
mkdir -p /data/input/"$SUBJECT_ID"/T1
ln -sf "$T1W" /data/input/"$SUBJECT_ID"/T1/

FLAIR_FLAG=""
FLAIR=$(find_flair "$INPUT_DIR")
if [ -n "$FLAIR" ]; then
    mkdir -p /data/input/"$SUBJECT_ID"/FLAIR
    ln -sf "$FLAIR" /data/input/"$SUBJECT_ID"/FLAIR/
    FLAIR_FLAG="--is_flair"
    echo "Using FLAIR: $FLAIR (will improve lesion detection)"
else
    echo "No FLAIR found (optional - detection will use T1w only)"
fi

cd /app
MELD_CMD="python scripts/new_patient_pipeline/new_pt_pipeline.py"
MELD_CMD="$MELD_CMD -id $SUBJECT_ID -sd $SUBJECTS_DIR -od $OUTPUT_DIR/meld"
[ -n "$FLAIR_FLAG" ] && MELD_CMD="$MELD_CMD $FLAIR_FLAG"

echo "Running: $MELD_CMD"
eval $MELD_CMD

echo "Cortical Lesion Detection workflow complete. Output in $OUTPUT_DIR"
