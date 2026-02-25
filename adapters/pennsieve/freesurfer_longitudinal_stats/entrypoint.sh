#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export SUBJECTS_DIR="$INPUT_DIR"

BASE_ID="${BASE_ID:-base}"

mkdir -p "$OUTPUT_DIR"

echo "=== Extracting Longitudinal Stats ==="
echo "SUBJECTS_DIR: $SUBJECTS_DIR"
echo "BASE_ID: $BASE_ID"

for d in "$SUBJECTS_DIR"/*.long."$BASE_ID"; do
    [ -d "$d" ] || continue
    LONG_ID=$(basename "$d")
    echo "Processing: $LONG_ID"

    for hemi in lh rh; do
        for meas in thickness area volume; do
            aparcstats2table --subjects "$LONG_ID" \
                --hemi "$hemi" --meas "$meas" \
                --tablefile "$OUTPUT_DIR/${hemi}_${meas}_${LONG_ID}.csv" \
                --sd "$SUBJECTS_DIR" 2>/dev/null || true
        done
    done

    asegstats2table --subjects "$LONG_ID" \
        --tablefile "$OUTPUT_DIR/aseg_${LONG_ID}.csv" \
        --sd "$SUBJECTS_DIR" 2>/dev/null || true
done

echo "Longitudinal stats extraction complete. Output in $OUTPUT_DIR"
