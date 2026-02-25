#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$INPUT_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"

echo "Running FreeSurfer segmentHA_T1.sh on: $SUBJECTS_DIR/$SUBJECT_ID"

segmentHA_T1.sh "$SUBJECT_ID"

cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/lh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true
cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/rh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true

echo "SegmentHA_T1 complete. Output in $OUTPUT_DIR"
