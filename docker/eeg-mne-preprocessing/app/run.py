#!/usr/bin/env python3
"""
NIR EEG preprocessing plugin — MNE-Python implementation.

Implements steps aligned with:
  https://mne.tools/stable/auto_tutorials/preprocessing/index.html
  https://mne.tools/stable/auto_tutorials/preprocessing/40_artifact_correction_ica.html (optional ICA)

Environment:
  NIR_INPUT_ROOT   default /data/input
  NIR_OUTPUT_ROOT  default /data/output

Expected input layout (any one raw file):
  $NIR_INPUT_ROOT/eeg/raw          file (e.g. .fif, .edf, .vhdr) OR directory containing one such file
  optional: $NIR_INPUT_ROOT/metadata/preprocessing_config.yaml
  optional: $NIR_INPUT_ROOT/metadata/channels.tsv  (BIDS-style: name, type — applied before name heuristics)

Outputs:
  $NIR_OUTPUT_ROOT/eeg/clean_raw.fif
  $NIR_OUTPUT_ROOT/qc/preprocessing_qc.json
  $NIR_OUTPUT_ROOT/logs/preprocessing.log
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

import mne

# BIDS channels.tsv "type" column → MNE (subset; unknown → misc)
_BIDS_TO_MNE = {
    "EEG": "eeg",
    "EOG": "eog",
    "ECG": "ecg",
    "EMG": "emg",
    "MISC": "misc",
    "TRIG": "stim",
    "STIM": "stim",
    "RESP": "resp",
    "TEMP": "misc",
    "SYSCLOCK": "misc",
    "OTHER": "misc",
}


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _load_config(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        import yaml

        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_raw_eeg(input_root: Path) -> Path:
    raw_ref = input_root / "eeg" / "raw"
    if raw_ref.is_file():
        return raw_ref
    if raw_ref.is_dir():
        exts = (".fif", ".edf", ".bdf", ".vhdr", ".set")
        for ext in exts:
            for p in sorted(raw_ref.rglob(f"*{ext}")):
                return p
        raise FileNotFoundError(f"No EEG file under {raw_ref}")
    # allow flat layout: eeg/*.fif
    eeg_dir = input_root / "eeg"
    if eeg_dir.is_dir():
        for ext in (".fif", ".edf", ".bdf", ".vhdr"):
            for p in sorted(eeg_dir.glob(f"*{ext}")):
                return p
    raise FileNotFoundError(
        f"Could not resolve raw EEG under {input_root}/eeg/raw (file or directory)"
    )


def _apply_channels_tsv(raw: mne.io.BaseRaw, tsv_path: Path, log_path: Path) -> int:
    """Apply BIDS channels.tsv types. Returns count of relabeled channels."""
    with tsv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
    if not rows:
        return 0
    fields = reader.fieldnames or ()
    if "name" not in fields or "type" not in fields:
        raise ValueError("channels.tsv must include 'name' and 'type' columns")
    mapping: dict[str, str] = {}
    for row in rows:
        name = str(row["name"]).strip()
        btype = str(row["type"]).strip().upper()
        if name not in raw.ch_names:
            continue
        mne_t = _BIDS_TO_MNE.get(btype, "misc")
        mapping[name] = mne_t
    if mapping:
        raw.set_channel_types(mapping, verbose="ERROR")
        _log(f"Applied metadata/channels.tsv ({len(mapping)} channel types)", log_path)
    return len(mapping)


def _relabeled_auxiliary_channels(ch_name: str) -> str | None:
    """If ch_name looks like ECG/EMG/EOG/aux, return MNE channel type; else None."""
    c = ch_name.lower().strip()
    # Order matters: more specific first
    if any(s in c for s in ("ekg", "ecg", "lead", "cardiac")):
        return "ecg"
    if "emg" in c:
        return "emg"
    if any(s in c for s in ("eog", "veog", "heog")):
        return "eog"
    if any(s in c for s in ("exg", "dc chan", "trigger", "trig", "photo", "pulse")):
        return "misc"

    return None


def _restrict_to_eeg_channels(
    raw: mne.io.BaseRaw, log_path: Path
) -> tuple[mne.io.BaseRaw, dict[str, str]]:
    """Relabel obvious non-scalp channels and keep only EEG for downstream forward/source steps.

    Clinical EDFs often mark EKG/ECG as type EEG; forward modeling then fails (no 3D positions).
    """
    mapping: dict[str, str] = {}
    for i, name in enumerate(raw.ch_names):
        if mne.channel_type(raw.info, i) != "eeg":
            continue
        kind = _relabeled_auxiliary_channels(name)
        if kind is not None:
            mapping[name] = kind
    if mapping:
        raw.set_channel_types(mapping, verbose="ERROR")
        _log(f"Relabeled non-scalp/aux channels (were mis-typed EEG): {mapping}", log_path)

    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(picks) == 0:
        raise RuntimeError(
            "No EEG channels after excluding ECG/EMG/EOG; check channel labels or types."
        )
    raw.pick(picks)
    return raw, mapping


def _read_raw(path: Path) -> mne.io.BaseRaw:
    suf = path.suffix.lower()
    if suf == ".fif":
        return mne.io.read_raw_fif(path, preload=True, verbose="ERROR")
    if suf == ".edf":
        return mne.io.read_raw_edf(path, preload=True, verbose="ERROR")
    if suf == ".bdf":
        return mne.io.read_raw_bdf(path, preload=True, verbose="ERROR")
    if suf == ".vhdr":
        return mne.io.read_raw_brainvision(path, preload=True, verbose="ERROR")
    if suf == ".set":
        return mne.io.read_raw_eeglab(path, preload=True, verbose="ERROR")
    raise ValueError(f"Unsupported EEG extension: {path}")


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    cfg_path = in_root / "metadata" / "preprocessing_config.yaml"
    cfg = _load_config(cfg_path if cfg_path.is_file() else None)

    l_freq = float(cfg.get("bandpass_low_hz", cfg.get("l_freq", 1.0)))
    h_freq = float(cfg.get("bandpass_high_hz", cfg.get("h_freq", 40.0)))
    notch = cfg.get("notch_freq_hz", cfg.get("notch_freq", 60.0))
    ref = str(cfg.get("eeg_reference", "average"))

    log_path = out_root / "logs" / "preprocessing.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    try:
        raw_path = _find_raw_eeg(in_root)
        _log(f"Loading {raw_path}", log_path)
        raw = _read_raw(raw_path)

        ch_tsv = in_root / "metadata" / "channels.tsv"
        tsv_count = 0
        if ch_tsv.is_file():
            tsv_count = _apply_channels_tsv(raw, ch_tsv, log_path)
        else:
            _log("No metadata/channels.tsv — using file header types + name heuristics only", log_path)

        raw, aux_relabeled = _restrict_to_eeg_channels(raw, log_path)
        _log(
            f"EEG-only pipeline: {raw.info['nchan']} channels — {raw.ch_names[:8]}{'...' if len(raw.ch_names) > 8 else ''}",
            log_path,
        )

        eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        if len(eeg_picks) == 0:
            raise RuntimeError(
                "No EEG channels in recording; this plugin expects EEG (see MNE channel types)."
            )

        raw.filter(l_freq=l_freq, h_freq=h_freq, picks=eeg_picks, verbose="ERROR")
        if notch:
            raw.notch_filter(freqs=float(notch), picks=eeg_picks, verbose="ERROR")
        if ref == "average":
            raw.set_eeg_reference("average", projection=True, verbose="ERROR")
        elif ref in ("mastoid", "linked_mastoids"):
            # user must supply picks; fallback to average
            _log("Reference 'mastoid' not auto-configured; using average.", log_path)
            raw.set_eeg_reference("average", projection=True, verbose="ERROR")
        else:
            raw.set_eeg_reference(ref, verbose="ERROR")

        out_fif = out_root / "eeg" / "clean_raw.fif"
        out_fif.parent.mkdir(parents=True, exist_ok=True)
        raw.save(out_fif, overwrite=True, verbose="ERROR")

        n_bad = len(raw.info["bads"])
        qc: dict[str, Any] = {
            "input_path": str(raw_path),
            "output_path": str(out_fif),
            "mne_version": mne.__version__,
            "sfreq": float(raw.info["sfreq"]),
            "n_channels": raw.info["nchan"],
            "n_times": int(raw.n_times),
            "duration_s": float(raw.times[-1]) if raw.n_times else 0.0,
            "bad_channels": list(raw.info["bads"]),
            "n_bad_channels": n_bad,
            "bandpass_hz": [l_freq, h_freq],
            "notch_hz": float(notch) if notch else None,
            "eeg_reference": ref,
            "eeg_only": True,
            "relabeled_auxiliary_channels": aux_relabeled,
            "metadata_channels_tsv": str(ch_tsv) if ch_tsv.is_file() else None,
            "channels_tsv_types_applied": tsv_count,
        }
        qc_path = out_root / "qc" / "preprocessing_qc.json"
        qc_path.parent.mkdir(parents=True, exist_ok=True)
        qc_path.write_text(json.dumps(qc, indent=2), encoding="utf-8")
        _log(f"Wrote {out_fif}", log_path)
        _log(f"Wrote {qc_path}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
