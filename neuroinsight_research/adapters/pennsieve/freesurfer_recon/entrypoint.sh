#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt

T1W=$(find_t1w "$INPUT_DIR")

if [ -z "$T1W" ]; then
    echo "ERROR: No T1w NIfTI file found in $INPUT_DIR" >&2
    echo "Searched: flat, anat/, ses-*/anat/" >&2
    find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -10 >&2
    exit 1
fi

SUBJECT_ID="${SUBJECT_ID:-sub-01}"

echo "Running FreeSurfer recon-all on: $T1W"
echo "Subject ID: $SUBJECT_ID"

recon-all \
    -i "$T1W" \
    -s "$SUBJECT_ID" \
    -sd "$OUTPUT_DIR" \
    -all

echo "FreeSurfer recon-all complete. Output in $OUTPUT_DIR/$SUBJECT_ID"
