#!/usr/bin/env bash
set -euo pipefail

# Build/push NeuroInsight MELD Graph image.
# Usage:
#   MELD_CACHE_SRC=/absolute/path/to/meld_cache ./docker/processors/build_and_push_meld_graph_nir.sh
# Optional:
#   IMAGE_REPO=phindagijimana321/meld_graph IMAGE_TAG=v2.2.4-nir2 ./docker/processors/build_and_push_meld_graph_nir.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE_REPO="${IMAGE_REPO:-phindagijimana321/meld_graph}"
IMAGE_TAG="${IMAGE_TAG:-v2.2.4-nir2}"
IMAGE="${IMAGE_REPO}:${IMAGE_TAG}"
MELD_CACHE_SRC="${MELD_CACHE_SRC:-}"

if [[ -z "${MELD_CACHE_SRC}" ]]; then
  echo "ERROR: MELD_CACHE_SRC is required."
  echo "Example:"
  echo "  MELD_CACHE_SRC=/absolute/path/to/meld_cache ./docker/processors/build_and_push_meld_graph_nir.sh"
  exit 1
fi

if [[ ! -d "${MELD_CACHE_SRC}" ]]; then
  echo "ERROR: MELD_CACHE_SRC does not exist: ${MELD_CACHE_SRC}"
  exit 1
fi

REQ1="${MELD_CACHE_SRC}/meld_params/fsaverage_sym/surf/lh.inflated"
REQ2="${MELD_CACHE_SRC}/meld_params/fsaverage_sym/surf/rh.inflated"
MODELS_DIR="${MELD_CACHE_SRC}/models"
if [[ ! -f "${REQ1}" || ! -f "${REQ2}" ]]; then
  echo "ERROR: MELD cache missing required surfaces:"
  echo "  ${REQ1}"
  echo "  ${REQ2}"
  exit 1
fi
if [[ ! -d "${MODELS_DIR}" ]] || [[ -z "$(ls -A "${MODELS_DIR}" 2>/dev/null)" ]]; then
  echo "ERROR: MELD cache models directory missing or empty: ${MODELS_DIR}"
  exit 1
fi

TMP_CONTEXT="$(mktemp -d)"
cleanup() { rm -rf "${TMP_CONTEXT}"; }
trap cleanup EXIT

mkdir -p "${TMP_CONTEXT}/build_meld_cache"
cp "${ROOT_DIR}/docker/meld-graph-custom/Dockerfile" "${TMP_CONTEXT}/Dockerfile"
cp -a "${MELD_CACHE_SRC}/meld_params" "${TMP_CONTEXT}/build_meld_cache/meld_params"
cp -a "${MELD_CACHE_SRC}/models" "${TMP_CONTEXT}/build_meld_cache/models"

echo "Building ${IMAGE} ..."
docker build -t "${IMAGE}" -f "${TMP_CONTEXT}/Dockerfile" "${TMP_CONTEXT}"

echo "Pushing ${IMAGE} ..."
docker push "${IMAGE}"

echo "Done: ${IMAGE}"
