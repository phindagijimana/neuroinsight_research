#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"
WORK_DIR="/data/work"

mkdir -p "$OUTPUT_DIR" "$WORK_DIR"

QSIPREP_DIR=$(find "$INPUT_DIR" -name "dataset_description.json" -exec dirname {} \; | head -1)
if [ -z "$QSIPREP_DIR" ]; then
    QSIPREP_DIR="$INPUT_DIR"
fi

PARTICIPANT="${PARTICIPANT_LABEL:-sub-01}"
NPROCS="${NPROCS:-4}"
MEM_MB="${MEM_MB:-8000}"

echo "Running QSIRecon on: $QSIPREP_DIR"
echo "Participant: $PARTICIPANT"

qsirecon "$QSIPREP_DIR" "$OUTPUT_DIR" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --nprocs "$NPROCS" \
    --mem-mb "$MEM_MB" \
    --work-dir "$WORK_DIR" \
    --notrack

echo "QSIRecon complete. Output in $OUTPUT_DIR"
