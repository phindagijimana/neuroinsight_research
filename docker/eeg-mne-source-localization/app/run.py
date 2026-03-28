#!/usr/bin/env python3
"""
NIR source localization plugin — MNE-Python minimum-norm / dSPM-style inverse.

Tutorial basis:
  https://mne.tools/stable/auto_tutorials/inverse/30_mne_dspm_loreta.html

Environment:
  NIR_INPUT_ROOT   default /data/input
  NIR_OUTPUT_ROOT  default /data/output

Inputs:
  $NIR_INPUT_ROOT/eeg/clean_raw.fif   (required)
  $NIR_INPUT_ROOT/models/forward_solution.fif  (required)
  optional: $NIR_INPUT_ROOT/events/spike_events.tsv  (first column: onset in seconds)

Outputs:
  $NIR_OUTPUT_ROOT/source/source_estimate-*.stc  (lh + rh)
  $NIR_OUTPUT_ROOT/source/peak_coordinates.json
  $NIR_OUTPUT_ROOT/source/laterality_summary.json
  $NIR_OUTPUT_ROOT/logs/source_localization.log

Note: NIfTI volume export (`source_map.nii.gz`) is not produced here; use morphing
or a follow-up plugin when subject MRI alignment is available.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import mne
import numpy as np
from mne.minimum_norm import apply_inverse, make_inverse_operator


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _load_spike_onsets_sec(path: Path) -> list[float] | None:
    if not path.is_file():
        return None
    onsets: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace(",", "\t").split("\t")
        if not parts:
            continue
        try:
            onsets.append(float(parts[0]))
        except ValueError:
            continue
    return onsets if onsets else None


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "source_localization.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    raw_path = in_root / "eeg" / "clean_raw.fif"
    fwd_path = in_root / "models" / "forward_solution.fif"
    spike_path = in_root / "events" / "spike_events.tsv"

    try:
        if not raw_path.is_file():
            raise FileNotFoundError(f"Missing {raw_path}")
        if not fwd_path.is_file():
            raise FileNotFoundError(f"Missing {fwd_path}")

        _log(f"Loading raw {raw_path}", log_path)
        raw = mne.io.read_raw_fif(raw_path, preload=True, verbose="ERROR")
        eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        if len(eeg_picks) == 0:
            raise RuntimeError("No EEG channels in raw; expected EEG for inverse.")

        _log(f"Loading forward {fwd_path}", log_path)
        forward = mne.read_forward_solution(fwd_path, verbose="ERROR")

        _log("Computing noise covariance from raw (first 60 s)", log_path)
        tmax = min(60.0, float(raw.times[-1]))
        noise_cov = mne.compute_raw_covariance(
            raw,
            tmax=tmax,
            picks=eeg_picks,
            method="shrunk",
            verbose="ERROR",
        )

        inv = make_inverse_operator(
            raw.info,
            forward,
            noise_cov,
            loose=0.2,
            depth=0.8,
            verbose="ERROR",
        )

        sfreq = raw.info["sfreq"]
        onsets = _load_spike_onsets_sec(spike_path)
        if onsets:
            events = np.array(
                [[int(o * sfreq), 0, 1] for o in onsets],
                dtype=np.int64,
            )
            _log(f"Using {len(onsets)} spike-aligned epochs from {spike_path}", log_path)
        else:
            mid = max(int(sfreq * 2.0), raw.n_times // 2)
            events = np.array([[mid, 0, 1]], dtype=np.int64)
            _log("No spike_events.tsv; using single synthetic epoch at mid-recording.", log_path)

        epochs = mne.Epochs(
            raw,
            events,
            event_id=1,
            tmin=-0.2,
            tmax=0.5,
            baseline=(None, 0),
            picks=eeg_picks,
            preload=True,
            verbose="ERROR",
        )
        evoked = epochs.average()

        lambda2 = 1.0 / 9.0
        stc = apply_inverse(
            evoked,
            inv,
            lambda2,
            method="dSPM",
            pick_ori=None,
            verbose="ERROR",
        )

        src_dir = out_root / "source"
        src_dir.mkdir(parents=True, exist_ok=True)
        stem = src_dir / "source_estimate"
        stc.save(str(stem))

        v_lh, t_lh = stc.get_peak(hemi="lh", time_as_index=False)
        v_rh, t_rh = stc.get_peak(hemi="rh", time_as_index=False)

        n_lh = len(stc.vertices[0])
        lh_max = float(np.max(np.abs(stc.data[:n_lh])))
        rh_max = float(np.max(np.abs(stc.data[n_lh:])))
        stronger = "lh" if lh_max >= rh_max else "rh"

        peak_coords = {
            "lh": {"vertex": int(v_lh), "time_s": float(t_lh)},
            "rh": {"vertex": int(v_rh), "time_s": float(t_rh)},
            "mne_version": mne.__version__,
            "method": "dSPM",
            "note": "Vertices are in source space; not MNI mm without morphing.",
        }
        lat = {
            "stronger_hemisphere": stronger,
            "lh_peak_abs_max": lh_max,
            "rh_peak_abs_max": rh_max,
        }

        (src_dir / "peak_coordinates.json").write_text(
            json.dumps(peak_coords, indent=2), encoding="utf-8"
        )
        (src_dir / "laterality_summary.json").write_text(
            json.dumps(lat, indent=2), encoding="utf-8"
        )

        _log(f"Wrote {stem}-lh.stc / {stem}-rh.stc", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
