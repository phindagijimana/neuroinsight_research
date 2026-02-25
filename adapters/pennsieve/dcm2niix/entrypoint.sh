#!/bin/bash
set -euo pipefail

INPUT_DIR="/data/input"
OUTPUT_DIR="/data/output"

mkdir -p "$OUTPUT_DIR"

DICOM_DIR=$(find "$INPUT_DIR" -name "*.dcm" -exec dirname {} \; | sort -u | head -1)
if [ -z "$DICOM_DIR" ]; then
    DICOM_DIR="$INPUT_DIR"
fi

COMPRESS="${COMPRESS:-y}"

echo "Running dcm2niix on: $DICOM_DIR"

dcm2niix -z "$COMPRESS" -o "$OUTPUT_DIR" "$DICOM_DIR"

echo "dcm2niix complete. Output in $OUTPUT_DIR"
