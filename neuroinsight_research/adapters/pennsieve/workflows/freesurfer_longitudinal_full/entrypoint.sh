#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$OUTPUT_DIR/subjects"
mkdir -p "$SUBJECTS_DIR"

BASE_ID="${BASE_ID:-base}"
THREADS="${THREADS:-4}"

# =========================================================================
# STAGE 1: FreeSurfer Longitudinal recon-all (CROSS -> BASE -> LONG)
# =========================================================================
echo "=== FreeSurfer Longitudinal Full Workflow ==="
echo "=== STAGE 1: Longitudinal recon-all ==="

TP_IDS=()
for nii in "$INPUT_DIR"/*.nii.gz "$INPUT_DIR"/*.nii; do
    [ -f "$nii" ] || continue
    fname=$(basename "$nii" .nii.gz)
    fname=$(basename "$fname" .nii)
    TP_ID="tp_${fname}"
    echo "=== CROSS: recon-all on $nii -> $TP_ID ==="
    recon-all -i "$nii" -s "$TP_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
    TP_IDS+=("$TP_ID")
done

if [ ${#TP_IDS[@]} -lt 2 ]; then
    echo "ERROR: Need at least 2 timepoints, found ${#TP_IDS[@]}" >&2
    exit 1
fi

TP_FLAGS=""
for tp in "${TP_IDS[@]}"; do TP_FLAGS="$TP_FLAGS -tp $tp"; done

echo "=== BASE: Creating template $BASE_ID ==="
recon-all -base "$BASE_ID" $TP_FLAGS -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"

for tp in "${TP_IDS[@]}"; do
    echo "=== LONG: ${tp}.long.${BASE_ID} ==="
    recon-all -long "$tp" "$BASE_ID" -sd "$SUBJECTS_DIR" -all -openmp "$THREADS"
done

echo "=== STAGE 1 complete ==="

# =========================================================================
# STAGE 2: Stats extraction (QDEC tables, aseg stats, slopes)
# =========================================================================
echo "=== STAGE 2: Longitudinal stats extraction ==="

STATS_DIR="$OUTPUT_DIR/stats"
mkdir -p "$STATS_DIR"

for d in "$SUBJECTS_DIR"/*.long."$BASE_ID"; do
    [ -d "$d" ] || continue
    LONG_ID=$(basename "$d")
    echo "Extracting stats for: $LONG_ID"

    for hemi in lh rh; do
        for meas in thickness area volume; do
            aparcstats2table --subjects "$LONG_ID" \
                --hemi "$hemi" --meas "$meas" \
                --tablefile "$STATS_DIR/${hemi}_${meas}_${LONG_ID}.csv" \
                --sd "$SUBJECTS_DIR" 2>/dev/null || true
        done
    done

    asegstats2table --subjects "$LONG_ID" \
        --tablefile "$STATS_DIR/aseg_${LONG_ID}.csv" \
        --sd "$SUBJECTS_DIR" 2>/dev/null || true
done

echo "=== FreeSurfer Longitudinal Full workflow complete ==="
echo "SUBJECTS_DIR: $SUBJECTS_DIR"
echo "Stats: $STATS_DIR"
