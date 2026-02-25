#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-4}"

T1W=$(find_t1w "$INPUT_DIR")
if [ -z "$T1W" ]; then
    echo "ERROR: No T1w NIfTI file found in $INPUT_DIR" >&2
    echo "Searched: flat, anat/, ses-*/anat/" >&2
    exit 1
fi
echo "Using T1w: $T1W"

T2W=$(find_t2w "$INPUT_DIR")

echo "=== Step 1/2: FreeSurfer recon-all ==="
recon-all -i "$T1W" -s "$SUBJECT_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

echo "=== Step 2/2: segmentHA_T2 ==="
if [ -n "$T2W" ]; then
    echo "Using T2w: $T2W"
    segmentHA_T2.sh "$SUBJECT_ID" "$T2W" T2 1 "$SUBJECTS_DIR"
else
    echo "WARNING: No T2w file found, running T1-only segmentation"
    segmentHA_T2.sh "$SUBJECT_ID" "$SUBJECTS_DIR"
fi

echo "Hippocampal Subfields T1+T2 workflow complete. Output in $SUBJECTS_DIR/$SUBJECT_ID"
