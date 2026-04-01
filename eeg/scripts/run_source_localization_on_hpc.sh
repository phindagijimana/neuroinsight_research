#!/usr/bin/env bash
# Run source_localization on HPC (Singularity/Apptainer) using outputs from a
# prior multimodal / EEG workflow run — same layout as NeuroInsight's SLURM step.
#
# Prerequisites under JOB_DIR/outputs/native/:
#   eeg_preprocessing/eeg/clean_raw.fif
#   forward_model/models/forward_solution.fif
#   spike_detection/events/   (optional; spike_events.tsv if present)
#
# Usage:
#   export JOB_DIR="$HOME/neuroinsight/jobs/<uuid>"
#   bash eeg/scripts/run_source_localization_on_hpc.sh "$JOB_DIR"
#
# Optional:
#   export SOURCE_LOC_IMAGE="docker://phindagijimana321/eeg-source-localization-mne:1.0.3"
#   sbatch --wrap "bash /path/to/run_source_localization_on_hpc.sh $JOB_DIR"
#
set -euo pipefail

JOB_DIR="${1:-}"
IMAGE="${SOURCE_LOC_IMAGE:-docker://phindagijimana321/eeg-source-localization-mne:1.0.3}"

if [[ -z "$JOB_DIR" ]]; then
  echo "Usage: $0 JOB_DIR" >&2
  echo "  JOB_DIR = NeuroInsight job directory (contains inputs/ and outputs/)." >&2
  exit 1
fi

OUT="$JOB_DIR/outputs"
EP_EEG="$OUT/native/eeg_preprocessing/eeg"
FM_MOD="$OUT/native/forward_model/models"
SP_EV="$OUT/native/spike_detection/events"
NI_SM="$OUT/native/source_merge"

for p in "$EP_EEG/clean_raw.fif" "$FM_MOD/forward_solution.fif"; do
  if [[ ! -f "$p" ]]; then
    echo "ERROR: missing required file: $p" >&2
    echo "Run eeg_preprocessing → forward_model first, or fix paths." >&2
    exit 1
  fi
done

mkdir -p "$OUT/native" "$OUT/logs" "$JOB_DIR/scripts"

echo "Building source_merge under $NI_SM"
rm -rf "$NI_SM" 2>/dev/null || true
mkdir -p "$NI_SM"
ln -sfn "$EP_EEG" "$NI_SM/eeg"
ln -sfn "$FM_MOD" "$NI_SM/models"
if [[ -d "$SP_EV" ]]; then
  ln -sfn "$SP_EV" "$NI_SM/events"
else
  echo "WARNING: no $SP_EV — plugin will use mid-recording synthetic epoch if no events dir."
  mkdir -p "$NI_SM/events"
fi

STEP_SH="$JOB_DIR/scripts/source_localization_rerun_cmd.sh"
cat > "$STEP_SH" << 'NI_CMD_EOF'
#!/bin/bash
set -e
export NIR_INPUT_ROOT=/data/inputs/source_merge
export NIR_OUTPUT_ROOT=/data/outputs/native/source_localization
mkdir -p "$NIR_OUTPUT_ROOT" /data/outputs/logs/source_localization
python /app/run.py
NI_CMD_EOF
chmod +x "$STEP_SH"

# Match SLURM: per-input binds (resolved symlinks)
declare -a INPUT_BINDS_ARR=()
shopt -s nullglob
for item in "$JOB_DIR"/inputs/*; do
  [[ -e "$item" || -L "$item" ]] || continue
  name=$(basename "$item")
  if [[ -L "$item" ]]; then
    target=$(readlink -f "$item")
    INPUT_BINDS_ARR+=(--bind "$target:/data/inputs/$name:ro")
  else
    INPUT_BINDS_ARR+=(--bind "$item:/data/inputs/$name:ro")
  fi
done
shopt -u nullglob

CONTAINER_RT=""
if command -v apptainer &>/dev/null; then
  CONTAINER_RT=apptainer
elif command -v singularity &>/dev/null; then
  CONTAINER_RT=singularity
else
  echo "ERROR: neither apptainer nor singularity found in PATH" >&2
  exit 1
fi
echo "Using: $CONTAINER_RT"

LOG="$OUT/logs/source_localization_rerun.log"
echo "Logging to $LOG"

set +e
"$CONTAINER_RT" exec --writable-tmpfs \
  --env OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}" \
  --env PYTHONNOUSERSITE=1 \
  --bind "$OUT:/data/outputs:rw" \
  "${INPUT_BINDS_ARR[@]}" \
  --bind "$NI_SM:/data/inputs/source_merge:rw" \
  --bind "$STEP_SH:/run_pipeline.sh:ro" \
  "$IMAGE" \
  bash /run_pipeline.sh 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

echo "source_localization exited with code $RC"
exit "$RC"
