#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt

mkdir -p "$OUTPUT_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
SUBJECTS_DIR=$(find "$INPUT_DIR" -maxdepth 2 -name "surf" -exec dirname {} \; | head -1)
if [ -z "$SUBJECTS_DIR" ]; then
    SUBJECTS_DIR="$INPUT_DIR"
else
    SUBJECT_ID=$(basename "$SUBJECTS_DIR")
    SUBJECTS_DIR=$(dirname "$SUBJECTS_DIR")
fi

export SUBJECTS_DIR

echo "Running MELD Graph on: $SUBJECTS_DIR/$SUBJECT_ID"

cd /app
python scripts/new_patient_pipeline/new_pt_pipeline.py \
    -id "$SUBJECT_ID" \
    -sd "$SUBJECTS_DIR" \
    -od "$OUTPUT_DIR"

echo "MELD Graph complete. Output in $OUTPUT_DIR"
