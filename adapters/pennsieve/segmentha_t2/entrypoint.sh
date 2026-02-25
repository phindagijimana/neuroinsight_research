#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$INPUT_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"

T2W=$(find_t2w "$INPUT_DIR")

echo "Running FreeSurfer segmentHA_T2.sh on: $SUBJECTS_DIR/$SUBJECT_ID"

if [ -n "$T2W" ]; then
    echo "Using T2w: $T2W"
    segmentHA_T2.sh "$SUBJECT_ID" "$T2W" T2 1
else
    echo "No T2w found, running without T2"
    segmentHA_T2.sh "$SUBJECT_ID"
fi

cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/lh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true
cp -r "$SUBJECTS_DIR/$SUBJECT_ID/mri/rh.hippoAmygLabels"* "$OUTPUT_DIR/" 2>/dev/null || true

echo "SegmentHA_T2 complete. Output in $OUTPUT_DIR"
