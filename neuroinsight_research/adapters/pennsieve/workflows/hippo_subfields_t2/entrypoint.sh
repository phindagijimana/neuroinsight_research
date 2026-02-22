#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
THREADS="${THREADS:-4}"

T1W=$(find "$INPUT_DIR" -name "*T1*" -name "*.nii.gz" -o -name "*T1*" -name "*.nii" | head -1)
if [ -z "$T1W" ]; then
    T1W=$(find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -1)
fi

T2W=$(find "$INPUT_DIR" -name "*T2*" -name "*.nii.gz" -o -name "*T2*" -name "*.nii" | head -1)

if [ -z "$T1W" ]; then
    echo "ERROR: No T1 NIfTI file found in $INPUT_DIR" >&2
    exit 1
fi

echo "=== Step 1/2: FreeSurfer recon-all ==="
recon-all -i "$T1W" -s "$SUBJECT_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

echo "=== Step 2/2: segmentHA_T2 ==="
if [ -n "$T2W" ]; then
    segmentHA_T2.sh "$SUBJECT_ID" "$T2W" T2 1 "$SUBJECTS_DIR"
else
    echo "WARNING: No T2 file found, running T1-only segmentation"
    segmentHA_T2.sh "$SUBJECT_ID" "$SUBJECTS_DIR"
fi

echo "Hippocampal Subfields T1+T2 workflow complete. Output in $SUBJECTS_DIR/$SUBJECT_ID"
