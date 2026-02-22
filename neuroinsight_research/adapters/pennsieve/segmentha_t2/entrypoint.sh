#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$INPUT_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"
T2_FILE="${T2_FILE:-}"

if [ -z "$T2_FILE" ]; then
    T2_FILE=$(find "$INPUT_DIR" -name "*T2*" -o -name "*t2*" | head -1)
fi

echo "Running FreeSurfer segmentHA_T2.sh on: $SUBJECTS_DIR/$SUBJECT_ID"

if [ -n "$T2_FILE" ]; then
    segmentHA_T2.sh "$SUBJECT_ID" "$T2_FILE" T2 1
else
    segmentHA_T2.sh "$SUBJECT_ID"
fi

cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/lh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true
cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/rh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true

echo "SegmentHA_T2 complete. Output in $OUTPUT_DIR"
