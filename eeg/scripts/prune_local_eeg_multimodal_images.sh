#!/usr/bin/env bash
# Remove local Docker images for EEG + multimodal plugin repos, keeping only the
# tags that match plugins/*.yaml (canonical "latest" for NIR).
#
# Does NOT delete anything from Docker Hub — use hub UI or API for registry cleanup.
#
# Usage:
#   ./eeg/scripts/prune_local_eeg_multimodal_images.sh        # dry-run (print only)
#   ./eeg/scripts/prune_local_eeg_multimodal_images.sh --apply

set -euo pipefail

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

# repository -> tag (must stay aligned with plugins/*.yaml)
declare -A KEEP=(
  [phindagijimana321/eeg-preprocessing-mne]=1.0.3
  [phindagijimana321/eeg-legacy-to-bids-mne]=1.0.0
  [phindagijimana321/eeg-spike-detection-mne]=1.0.1
  [phindagijimana321/eeg-mri-coregistration-mne]=1.0.2
  [phindagijimana321/eeg-forward-model-mne]=1.0.10
  [phindagijimana321/eeg-source-localization-mne]=1.0.3
  [phindagijimana321/eeg-roi-feature-extraction]=1.0.1
  [phindagijimana321/eeg-biomarker-scoring]=1.0.0
  [phindagijimana321/freesurfer-autorecon-volonly]=7.4.1
)

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found; nothing to prune."
  exit 0
fi

for repo in "${!KEEP[@]}"; do
  want="${KEEP[$repo]}"
  while IFS= read -r tag; do
    [[ -z "$tag" ]] && continue
    if [[ "$tag" == "$want" ]]; then
      continue
    fi
    img="${repo}:${tag}"
    echo "Would remove: $img (keep ${repo}:${want})"
    if [[ "$APPLY" -eq 1 ]]; then
      docker rmi -f "$img" 2>/dev/null || true
    fi
  done < <(docker images "$repo" --format '{{.Tag}}' 2>/dev/null || true)
done

# Dangling layers (optional)
if [[ "$APPLY" -eq 1 ]]; then
  docker image prune -f >/dev/null 2>&1 || true
fi

if [[ "$APPLY" -eq 0 ]]; then
  echo ""
  echo "Dry-run only. Re-run with: $0 --apply"
fi
