#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

# Pennsieve provides data in /data/input and expects results in /data/output.
# FreeSurfer license must be mounted at /license/license.txt.

export FS_LICENSE=/license/license.txt

# Find NIfTI T1w input
T1W=$(find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -1)

if [ -z "$T1W" ]; then
    echo "ERROR: No NIfTI file found in $INPUT_DIR" >&2
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
