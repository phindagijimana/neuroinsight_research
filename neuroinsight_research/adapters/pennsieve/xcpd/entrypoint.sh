#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

mkdir -p "$OUTPUT_DIR" /tmp/work/xcpd

FMRIPREP_DIR=$(find "$INPUT_DIR" -name "dataset_description.json" -exec dirname {} \; | head -1)
if [ -z "$FMRIPREP_DIR" ]; then
    FMRIPREP_DIR="$INPUT_DIR"
fi

PARTICIPANT="${PARTICIPANT_LABEL:-sub-01}"
NPROCS="${NPROCS:-4}"
MEM_MB="${MEM_MB:-8000}"

echo "Running XCP-D on: $FMRIPREP_DIR"
echo "Participant: $PARTICIPANT"

xcp_d "$FMRIPREP_DIR" "$OUTPUT_DIR" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --nprocs "$NPROCS" \
    --mem-gb "$(( MEM_MB / 1000 ))" \
    --work-dir /tmp/work/xcpd \
    --notrack

echo "XCP-D complete. Output in $OUTPUT_DIR"
