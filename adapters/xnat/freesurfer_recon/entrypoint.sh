#!/bin/bash
set -euo pipefail

INPUT_DIR="/input"
OUTPUT_DIR="/output"

export FS_LICENSE=/license/license.txt

T1W=$(find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -1)

if [ -z "$T1W" ]; then
    echo "ERROR: No NIfTI file found in $INPUT_DIR" >&2
    exit 1
fi

SUBJECT_ID="${SUBJECT_ID:-sub-01}"

echo "Running FreeSurfer recon-all on: $T1W"
recon-all \
    -i "$T1W" \
    -s "$SUBJECT_ID" \
    -sd "$OUTPUT_DIR" \
    -all

echo "FreeSurfer recon-all complete."
