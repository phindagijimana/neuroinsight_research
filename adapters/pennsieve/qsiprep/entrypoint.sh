#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt

mkdir -p "$OUTPUT_DIR" /tmp/work/qsiprep

BIDS_DIR=$(find "$INPUT_DIR" -name "dataset_description.json" -exec dirname {} \; | head -1)
if [ -z "$BIDS_DIR" ]; then
    BIDS_DIR="$INPUT_DIR"
fi

PARTICIPANT="${PARTICIPANT_LABEL:-sub-01}"
NPROCS="${NPROCS:-4}"
MEM_MB="${MEM_MB:-8000}"

echo "Running QSIPrep on: $BIDS_DIR"
echo "Participant: $PARTICIPANT"

qsiprep "$BIDS_DIR" "$OUTPUT_DIR" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --fs-license-file "$FS_LICENSE" \
    --nprocs "$NPROCS" \
    --mem-mb "$MEM_MB" \
    --work-dir /tmp/work/qsiprep \
    --output-resolution 1.25 \
    --skip-bids-validation \
    --notrack

echo "QSIPrep complete. Output in $OUTPUT_DIR"
