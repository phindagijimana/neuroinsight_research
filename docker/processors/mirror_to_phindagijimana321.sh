#!/usr/bin/env bash
set -euo pipefail

# Mirrors tested processor images to phindagijimana321/*
# Usage:
#   ./docker/processors/mirror_to_phindagijimana321.sh
# Optional:
#   DRY_RUN=1 ./docker/processors/mirror_to_phindagijimana321.sh

DRY_RUN="${DRY_RUN:-0}"

PAIRS=(
  "nipy/heudiconv:1.3.4 phindagijimana321/heudiconv:1.3.4"
  "deepmi/fastsurfer:cpu-v2.4.2 phindagijimana321/fastsurfer:cpu-v2.4.2"
  "nipreps/fmriprep:23.2.1 phindagijimana321/fmriprep:23.2.1"
  "freesurfer/freesurfer:7.4.1 phindagijimana321/freesurfer:7.4.1"
  "meldproject/meld_graph:v2.2.4 phindagijimana321/meld_graph:v2.2.4"
  "pennbbl/qsiprep:0.20.0 phindagijimana321/qsiprep:0.20.0"
  "pennlinc/qsirecon:1.1.1 phindagijimana321/qsirecon:1.1.1"
  "pennlinc/xcp_d:0.6.1 phindagijimana321/xcp_d:0.6.1"
  "phindagijimana321/freesurfer-mcr:7.4.1 phindagijimana321/freesurfer-mcr:7.4.1"
  "phindagijimana321/hs-postprocess:1.0.0 phindagijimana321/hs-postprocess:1.0.0"
)

echo "Mirroring ${#PAIRS[@]} processor images..."
for pair in "${PAIRS[@]}"; do
  src="${pair%% *}"
  dst="${pair##* }"

  echo
  echo "SOURCE: ${src}"
  echo "TARGET: ${dst}"

  if [[ "$DRY_RUN" == "1" ]]; then
    continue
  fi

  docker pull "$src"
  docker tag "$src" "$dst"
  docker push "$dst"
done

echo
echo "Done."
