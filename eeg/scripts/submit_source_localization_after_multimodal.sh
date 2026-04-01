#!/usr/bin/env bash
# Build native/source_merge on HPC (same as NeuroInsight workflow step) and submit
# source_localization via the NIR API. Use after multimodal steps 1–4 succeeded.
#
# Usage:
#   export NIR_API_URL=http://127.0.0.1:3000   # optional
#   ./submit_source_localization_after_multimodal.sh /mnt/nfs/.../neuroinsight/jobs/<JOB_UUID>
#
# Requires: ssh to HPC (same as NIR: e.g. -p 2222), curl, job path must contain
#   outputs/native/eeg_preprocessing/eeg
#   outputs/native/forward_model/models/forward_solution.fif
#   outputs/native/spike_detection/events
#
set -euo pipefail

NIR_API_URL="${NIR_API_URL:-http://127.0.0.1:3000}"
SSH="${HPC_SSH:-ssh -o BatchMode=yes -o ConnectTimeout=30 -p ${HPC_SSH_PORT:-2222} ${HPC_USER:-pndagiji}@127.0.0.1}"

JOB_ROOT="${1:?Usage: $0 /path/to/neuroinsight/jobs/<JOB_ID>}"
OUT="${JOB_ROOT%/}/outputs"
SM="${OUT}/native/source_merge"
FWD="${OUT}/native/forward_model/models/forward_solution.fif"

echo "Checking remote artifacts..."
$SSH "test -f '$FWD'" || {
  echo "ERROR: forward solution missing: $FWD" >&2
  echo "Complete forward_model (multimodal step 4) before source localization." >&2
  exit 1
}
$SSH "test -f '${OUT}/native/eeg_preprocessing/eeg/clean_raw.fif'" || {
  echo "ERROR: missing clean_raw.fif under eeg_preprocessing/eeg" >&2
  exit 1
}

echo "Creating source_merge on HPC..."
$SSH bash <<REMOTE
set -euo pipefail
OUT="$OUT"
SM="\$OUT/native/source_merge"
rm -rf "\$SM"
mkdir -p "\$SM"
ln -sfn "\$OUT/native/eeg_preprocessing/eeg" "\$SM/eeg"
ln -sfn "\$OUT/native/forward_model/models" "\$SM/models"
ln -sfn "\$OUT/native/spike_detection/events" "\$SM/events"
echo "OK: \$SM"
REMOTE

echo "Submitting source_localization to ${NIR_API_URL}..."
RESP=$(curl -sS -X POST "${NIR_API_URL}/api/plugins/source_localization/submit" \
  -H "Content-Type: application/json" \
  -d "{\"input_files\": [\"${SM}\"], \"parameters\": {}}")

echo "$RESP"
echo "$RESP" | grep -q '"job_id"' || exit 1
echo "Done."
