#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

BASE_ID="${BASE_ID:-base}"
THREADS="${THREADS:-4}"

echo "=== FreeSurfer Longitudinal Processing ==="

TP_IDS=()
for nii in "$INPUT_DIR"/*.nii.gz "$INPUT_DIR"/*.nii; do
    [ -f "$nii" ] || continue
    fname=$(basename "$nii" .nii.gz)
    fname=$(basename "$fname" .nii)
    TP_ID="tp_${fname}"
    echo "Running recon-all CROSS on: $nii -> $TP_ID"
    recon-all -i "$nii" -s "$TP_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
    TP_IDS+=("$TP_ID")
done

if [ ${#TP_IDS[@]} -lt 2 ]; then
    echo "ERROR: Need at least 2 timepoints, found ${#TP_IDS[@]}" >&2
    exit 1
fi

TP_FLAGS=""
for tp in "${TP_IDS[@]}"; do
    TP_FLAGS="$TP_FLAGS -tp $tp"
done

echo "Creating BASE template: $BASE_ID from ${#TP_IDS[@]} timepoints"
recon-all -base "$BASE_ID" $TP_FLAGS -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

for tp in "${TP_IDS[@]}"; do
    LONG_ID="${tp}.long.${BASE_ID}"
    echo "Running LONG stream: $LONG_ID"
    recon-all -long "$tp" "$BASE_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
done

echo "FreeSurfer longitudinal processing complete. Output in $SUBJECTS_DIR"
