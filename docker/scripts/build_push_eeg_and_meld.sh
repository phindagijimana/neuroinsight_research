#!/usr/bin/env bash
# Build and push NeuroInsight-managed EEG MNE images + optional MELD v2.2.4-nir2.
# Tags match plugins/*.yaml — see eeg/docker/README.md.
#
# Usage (from repo root):
#   docker login   # phindagijimana321 or your registry
#   ./docker/scripts/build_push_eeg_and_meld.sh
#
# MELD (bakes params/models; requires a prepared cache tree):
#   MELD_CACHE_SRC=/abs/path/to/meld_cache ./docker/scripts/build_push_eeg_and_meld.sh
#
# Env:
#   REGISTRY=phindagijimana321   (default)
#   SKIP_PUSH=1                  build only, no docker push
#   SKIP_BEM_SOURCE_SPACE=1      skip eeg-bem-source-space-mne (e.g. no dnf/mirror network)
# Non-interactive registry login (optional, e.g. CI):
#   DOCKERHUB_USER + DOCKERHUB_TOKEN  → docker login before push

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

REGISTRY="${REGISTRY:-phindagijimana321}"
SKIP_PUSH="${SKIP_PUSH:-0}"
SKIP_BEM="${SKIP_BEM_SOURCE_SPACE:-0}"

if [[ -n "${DOCKERHUB_USER:-}" && -n "${DOCKERHUB_TOKEN:-}" ]]; then
  echo "${DOCKERHUB_TOKEN}" | docker login -u "${DOCKERHUB_USER}" --password-stdin
fi

build_one() {
  local dockerfile=$1
  local context=$2
  local image=$3
  echo ""
  echo "========== BUILD ${image} =========="
  docker build -t "${image}" -f "${dockerfile}" "${context}"
}

push_one() {
  local image=$1
  echo "========== PUSH ${image} =========="
  docker push "${image}"
}

# --- EEG / multimodal stack (plugins). BEM is last: requires FreeSurfer base + dnf network. ---
build_one docker/eeg-mne-preprocessing/Dockerfile docker/eeg-mne-preprocessing "${REGISTRY}/eeg-preprocessing-mne:1.0.3"
build_one docker/eeg-mne-legacy-to-bids/Dockerfile docker/eeg-mne-legacy-to-bids "${REGISTRY}/eeg-legacy-to-bids-mne:1.0.0"
build_one docker/eeg-mne-spike-detection/Dockerfile docker/eeg-mne-spike-detection "${REGISTRY}/eeg-spike-detection-mne:1.0.1"
build_one docker/eeg-mne-coregistration/Dockerfile docker/eeg-mne-coregistration "${REGISTRY}/eeg-mri-coregistration-mne:1.0.2"
build_one docker/eeg-mne-forward-model/Dockerfile docker/eeg-mne-forward-model "${REGISTRY}/eeg-forward-model-mne:1.0.10"
build_one docker/eeg-mne-source-localization/Dockerfile docker/eeg-mne-source-localization "${REGISTRY}/eeg-source-localization-mne:1.0.3"
build_one docker/eeg-roi-feature-extraction/Dockerfile docker/eeg-roi-feature-extraction "${REGISTRY}/eeg-roi-feature-extraction:1.0.1"
build_one docker/eeg-biomarker-scoring/Dockerfile docker/eeg-biomarker-scoring "${REGISTRY}/eeg-biomarker-scoring:1.0.0"

if [[ "${SKIP_BEM}" == "1" ]]; then
  echo ""
  echo "========== SKIP eeg-bem-source-space-mne (SKIP_BEM_SOURCE_SPACE=1) =========="
else
  echo ""
  echo "========== BUILD ${REGISTRY}/eeg-bem-source-space-mne:1.0.0 (FreeSurfer base) =========="
  set +e
  build_one docker/eeg-mne-bem-source-space/Dockerfile docker/eeg-mne-bem-source-space "${REGISTRY}/eeg-bem-source-space-mne:1.0.0"
  BEM_RC=$?
  set -e
  if [[ "${BEM_RC}" -ne 0 ]]; then
    echo "WARNING: BEM/source-space image build failed (often dnf/mirror DNS). Other EEG images are already built." >&2
  fi
fi

EEG_IMAGES=(
  "${REGISTRY}/eeg-preprocessing-mne:1.0.3"
  "${REGISTRY}/eeg-legacy-to-bids-mne:1.0.0"
  "${REGISTRY}/eeg-spike-detection-mne:1.0.1"
  "${REGISTRY}/eeg-mri-coregistration-mne:1.0.2"
  "${REGISTRY}/eeg-forward-model-mne:1.0.10"
  "${REGISTRY}/eeg-source-localization-mne:1.0.3"
  "${REGISTRY}/eeg-roi-feature-extraction:1.0.1"
  "${REGISTRY}/eeg-biomarker-scoring:1.0.0"
  "${REGISTRY}/eeg-bem-source-space-mne:1.0.0"
)

# --- MELD nir2 (optional; needs MELD_CACHE_SRC) ---
if [[ -n "${MELD_CACHE_SRC:-}" ]]; then
  echo ""
  echo "========== MELD v2.2.4-nir2 (MELD_CACHE_SRC set) =========="
  MELD_CACHE_SRC="${MELD_CACHE_SRC}" "${ROOT}/docker/processors/build_and_push_meld_graph_nir.sh"
else
  echo ""
  echo "Skipping MELD v2.2.4-nir2 (set MELD_CACHE_SRC to build; see docker/processors/README.md)."
fi

if [[ "${SKIP_PUSH}" == "1" ]]; then
  echo "SKIP_PUSH=1 — not pushing."
  exit 0
fi

echo ""
echo "========== PUSH EEG images (skip tags not present locally) =========="
for img in "${EEG_IMAGES[@]}"; do
  if docker image inspect "${img}" >/dev/null 2>&1; then
    push_one "${img}"
  else
    echo "========== SKIP PUSH (not built): ${img} =========="
  fi
done

echo ""
echo "Done. (MELD push ran inside build_and_push_meld_graph_nir.sh when MELD_CACHE_SRC was set.)"
