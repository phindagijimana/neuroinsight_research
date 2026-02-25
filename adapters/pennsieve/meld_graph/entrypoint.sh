#!/bin/bash
set -euo pipefail

source /shared/detect_inputs.sh

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

export FS_LICENSE=/license/license.txt
export MELD_LICENSE=/run/secrets/meld_license.txt
export PYTHONNOUSERSITE=1

cd /app

mkdir -p "$OUTPUT_DIR"

SUBJECT_ID="${SUBJECT_ID:-sub-01}"

# Ensure MELD data (params + models) is present
if [ ! -d "/data/meld_params" ]; then
    echo "Downloading MELD parameters..."
    python -c "from meld_graph.download_data import get_meld_params; get_meld_params()" \
        || { echo "ERROR: Could not download meld_params." >&2; exit 1; }
fi
if [ ! -d "/data/models" ] || [ -z "$(ls /data/models/ 2>/dev/null)" ]; then
    echo "Downloading MELD models..."
    python -c "from meld_graph.download_data import get_model; get_model()" \
        || { echo "ERROR: Could not download MELD models." >&2; exit 1; }
fi

# Locate FreeSurfer SUBJECTS_DIR from input
SUBJECTS_DIR=$(find "$INPUT_DIR" -maxdepth 2 -name "surf" -exec dirname {} \; | head -1)
if [ -z "$SUBJECTS_DIR" ]; then
    SUBJECTS_DIR="$INPUT_DIR"
else
    SUBJECT_ID=$(basename "$SUBJECTS_DIR")
    SUBJECTS_DIR=$(dirname "$SUBJECTS_DIR")
fi

export SUBJECTS_DIR

# Stage T1w into MELD's expected layout (exclude derived files)
mkdir -p /data/input/"$SUBJECT_ID"/T1

T1W=$(find_t1w "$INPUT_DIR")
if [ -n "$T1W" ]; then
    ln -sf "$T1W" /data/input/"$SUBJECT_ID"/T1/
    echo "Staged T1w: $(basename "$T1W")"
fi

FLAIR_FLAG=""
FLAIR=$(find_flair "$INPUT_DIR")
if [ -n "$FLAIR" ]; then
    mkdir -p /data/input/"$SUBJECT_ID"/FLAIR
    ln -sf "$FLAIR" /data/input/"$SUBJECT_ID"/FLAIR/
    FLAIR_FLAG="--is_flair"
    echo "Staged FLAIR: $(basename "$FLAIR") (will improve lesion detection)"
else
    echo "No FLAIR found (optional - detection will use T1w only)"
fi

echo "Running Focal Cortical Lesion Detection on: $SUBJECTS_DIR/$SUBJECT_ID"

MELD_CMD="python scripts/new_patient_pipeline/new_pt_pipeline.py"
MELD_CMD="$MELD_CMD -id $SUBJECT_ID"
MELD_CMD="$MELD_CMD -sd $SUBJECTS_DIR"
MELD_CMD="$MELD_CMD -od $OUTPUT_DIR"
[ -n "$FLAIR_FLAG" ] && MELD_CMD="$MELD_CMD $FLAIR_FLAG"

echo "Command: $MELD_CMD"
eval $MELD_CMD

echo "Focal Cortical Lesion Detection complete. Output in $OUTPUT_DIR"
