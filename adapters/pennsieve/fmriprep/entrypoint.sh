#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt

mkdir -p "$OUTPUT_DIR" /tmp/work/fmriprep

BIDS_DIR=$(find "$INPUT_DIR" -name "dataset_description.json" -exec dirname {} \; | head -1)
if [ -z "$BIDS_DIR" ]; then
    BIDS_DIR="$INPUT_DIR"
fi

PARTICIPANT="${PARTICIPANT_LABEL:-sub-01}"
NPROCS="${NPROCS:-4}"
MEM_MB="${MEM_MB:-8000}"

echo "Running fMRIPrep on: $BIDS_DIR"
echo "Participant: $PARTICIPANT"

fmriprep "$BIDS_DIR" "$OUTPUT_DIR" participant \
    --participant-label "${PARTICIPANT#sub-}" \
    --fs-license-file "$FS_LICENSE" \
    --nprocs "$NPROCS" \
    --mem-mb "$MEM_MB" \
    --work-dir /tmp/work/fmriprep \
    --output-spaces MNI152NLin2009cAsym \
    --skip-bids-validation \
    --notrack

echo "fMRIPrep complete. Output in $OUTPUT_DIR"
