#!/usr/bin/env python3
"""
NIR spike_detection — baseline epileptiform candidate detector using MNE + scipy.

This is a research default (band-limited signal, Hilbert envelope, adaptive threshold),
not a clinical gold standard. Replace with SpikeNet or a validated detector when needed.

Tutorial alignment:
  https://mne.tools/stable/auto_tutorials/preprocessing/index.html (filtering)
  Event/annotation patterns for downstream workflows

Environment:
  NIR_INPUT_ROOT, NIR_OUTPUT_ROOT (default /data/input, /data/output)

Inputs:
  $NIR_INPUT_ROOT/eeg/clean_raw.fif
  optional: $NIR_INPUT_ROOT/metadata/spike_detection_config.yaml

Outputs:
  $NIR_OUTPUT_ROOT/events/spike_events.tsv
  $NIR_OUTPUT_ROOT/events/spike_channels.json
  $NIR_OUTPUT_ROOT/events/spike_scores.json
  $NIR_OUTPUT_ROOT/logs/spike_detection.log
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import mne
import numpy as np
from scipy.signal import find_peaks, hilbert


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    import yaml

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "spike_detection.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    cfg_path = in_root / "metadata" / "spike_detection_config.yaml"
    cfg = _load_yaml(cfg_path)

    l_hz = float(cfg.get("spike_band_low_hz", 20.0))
    h_hz = float(cfg.get("spike_band_high_hz", 70.0))
    z_thresh = float(cfg.get("z_threshold", 5.0))
    min_dist_ms = float(cfg.get("min_peak_distance_ms", 80.0))
    merge_win_ms = float(cfg.get("merge_window_ms", 50.0))

    raw_path = in_root / "eeg" / "clean_raw.fif"
    try:
        if not raw_path.is_file():
            raise FileNotFoundError(f"Missing {raw_path}")

        raw = mne.io.read_raw_fif(raw_path, preload=True, verbose="ERROR")
        picks = mne.pick_types(raw.info, eeg=True, exclude="bads")
        if len(picks) == 0:
            raise RuntimeError("No EEG picks in clean_raw.fif")

        raw.filter(l_hz, h_hz, picks=picks, fir_design="firwin", verbose="ERROR")
        data = raw.get_data(picks=picks)
        sfreq = raw.info["sfreq"]
        times = raw.times

        # Global RMS envelope across EEG channels (simple fusion)
        rms = np.sqrt(np.mean(data**2, axis=0))
        env = np.abs(hilbert(rms))
        med = float(np.median(env))
        mad = float(np.median(np.abs(env - med))) + 1e-15
        thresh = med + z_thresh * 1.4826 * mad  # robust z

        min_samples = max(1, int(min_dist_ms * sfreq / 1000.0))
        peaks, _ = find_peaks(env, height=thresh, distance=min_samples)

        events_out: list[dict[str, Any]] = []
        ch_names = [raw.ch_names[p] for p in picks]

        for pk in peaks:
            t0 = float(times[pk])
            # channel with largest amplitude at spike time
            snap = np.abs(data[:, pk])
            ci = int(np.argmax(snap))
            events_out.append(
                {
                    "onset_sec": t0,
                    "duration_sec": merge_win_ms / 1000.0,
                    "peak_channel": ch_names[ci],
                    "envelope_peak": float(env[pk]),
                    "height_z": float((env[pk] - med) / (1.4826 * mad)),
                }
            )

        # merge close events (keep max peak)
        merged: list[dict[str, Any]] = []
        win = merge_win_ms / 1000.0
        events_out.sort(key=lambda e: e["onset_sec"])
        for ev in events_out:
            if not merged:
                merged.append(ev)
                continue
            if ev["onset_sec"] - merged[-1]["onset_sec"] <= win:
                if ev["envelope_peak"] > merged[-1]["envelope_peak"]:
                    merged[-1] = ev
            else:
                merged.append(ev)

        ev_dir = out_root / "events"
        ev_dir.mkdir(parents=True, exist_ok=True)
        tsv = ev_dir / "spike_events.tsv"
        with tsv.open("w", encoding="utf-8") as f:
            f.write("onset_sec\tduration_sec\tpeak_channel\tenvelope_peak\theight_z\n")
            for ev in merged:
                f.write(
                    f"{ev['onset_sec']:.6f}\t{ev['duration_sec']:.6f}\t"
                    f"{ev['peak_channel']}\t{ev['envelope_peak']:.8f}\t{ev['height_z']:.4f}\n"
                )

        ch_json = {
            "peak_channels": [ev["peak_channel"] for ev in merged],
            "mne_version": mne.__version__,
        }
        (ev_dir / "spike_channels.json").write_text(
            json.dumps(ch_json, indent=2), encoding="utf-8"
        )
        (ev_dir / "spike_scores.json").write_text(
            json.dumps(
                {
                    "events": merged,
                    "threshold_robust_z": z_thresh,
                    "band_hz": [l_hz, h_hz],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        _log(f"Detected {len(merged)} spike candidates → {tsv}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
