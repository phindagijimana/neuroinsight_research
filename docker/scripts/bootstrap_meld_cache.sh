#!/usr/bin/env bash
# Download MELD params + models from Figshare into a directory suitable for
# build_and_push_meld_graph_nir.sh (same layout as meld_graph.download_data).
#
# Usage:
#   ./docker/scripts/bootstrap_meld_cache.sh /abs/path/to/meld_cache
#
# Requires: curl, unzip

set -euo pipefail

OUT="${1:?Usage: $0 /abs/path/to/meld_cache}"

mkdir -p "${OUT}"
TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

# URLs from meld_graph/download_data.py (v2.2.4)
PARAMS_URL="https://figshare.com/ndownloader/files/46176921?private_link=34b4a30c57a328a1e111"
MODELS_URL="https://figshare.com/ndownloader/files/46176927?private_link=7f983b7321bba527ffef"

echo "Downloading meld_params.zip ..."
curl -fsSL -o "${TMP}/meld_params.zip" "${PARAMS_URL}"
echo "Unpacking to ${OUT} ..."
unzip -q -o "${TMP}/meld_params.zip" -d "${OUT}"

echo "Downloading models.zip ..."
curl -fsSL -o "${TMP}/models.zip" "${MODELS_URL}"
mkdir -p "${OUT}/models"
unzip -q -o "${TMP}/models.zip" -d "${OUT}/models"

REQ1="${OUT}/meld_params/fsaverage_sym/surf/lh.inflated"
REQ2="${OUT}/meld_params/fsaverage_sym/surf/rh.inflated"
if [[ ! -f "${REQ1}" || ! -f "${REQ2}" ]]; then
  echo "ERROR: Expected surfaces missing after unpack. Got:"
  find "${OUT}" -name lh.inflated 2>/dev/null || true
  exit 1
fi
if [[ -z "$(ls -A "${OUT}/models" 2>/dev/null)" ]]; then
  echo "ERROR: models/ empty after unpack."
  exit 1
fi

echo "OK: MELD cache ready at ${OUT}"
