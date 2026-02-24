#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

BASE_ID="${BASE_ID:-base}"
THREADS="${THREADS:-4}"

echo "=== FreeSurfer Longitudinal Processing ==="
echo "Searching for T1w timepoints in $INPUT_DIR ..."

# Collect all T1w timepoints (flat + BIDS ses-*/anat/)
TP_IDS=()
TP_PATHS=()

while IFS= read -r nii; do
    [ -n "$nii" ] || continue
    tp_id=$(extract_tp_id "$nii")
    # Deduplicate
    already=false
    for existing in "${TP_IDS[@]+"${TP_IDS[@]}"}"; do
        [ "$existing" = "$tp_id" ] && already=true
    done
    $already && continue
    TP_IDS+=("$tp_id")
    TP_PATHS+=("$nii")
    echo "  Found timepoint: $tp_id -> $nii"
done < <(find_all_t1w "$INPUT_DIR")

if [ ${#TP_IDS[@]} -lt 2 ]; then
    echo "ERROR: Need at least 2 timepoints, found ${#TP_IDS[@]}" >&2
    echo "Directory contents:" >&2
    find "$INPUT_DIR" -name "*.nii.gz" -o -name "*.nii" | head -20 >&2
    exit 1
fi

echo "Total timepoints: ${#TP_IDS[@]}"

# STAGE 1: CROSS-SECTIONAL recon-all per timepoint
echo "=== STAGE 1: Cross-sectional processing ==="
for i in "${!TP_IDS[@]}"; do
    tp_id="${TP_IDS[$i]}"
    nii="${TP_PATHS[$i]}"
    echo "  Processing CROSS: $tp_id ($nii)"
    recon-all -i "$nii" -s "$tp_id" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
done

# STAGE 2: BASE template
echo "=== STAGE 2: Base template ($BASE_ID) ==="
TP_FLAGS=""
for tp in "${TP_IDS[@]}"; do
    TP_FLAGS="$TP_FLAGS -tp $tp"
done

echo "  Creating BASE from ${#TP_IDS[@]} timepoints"
recon-all -base "$BASE_ID" $TP_FLAGS -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

# STAGE 3: LONGITUDINAL recon-all per timepoint
echo "=== STAGE 3: Longitudinal processing ==="
for tp in "${TP_IDS[@]}"; do
    LONG_ID="${tp}.long.${BASE_ID}"
    echo "  Processing LONG: $LONG_ID"
    recon-all -long "$tp" "$BASE_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
done

echo "FreeSurfer longitudinal processing complete. Output in $SUBJECTS_DIR"
