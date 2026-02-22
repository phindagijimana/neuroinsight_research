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

echo "Running FastSurfer on: $T1W"
/fastsurfer/run_fastsurfer.sh \
    --t1 "$T1W" \
    --sid "$SUBJECT_ID" \
    --sd "$OUTPUT_DIR" \
    --fs_license "$FS_LICENSE" \
    --parallel --batch 1

echo "FastSurfer complete."
