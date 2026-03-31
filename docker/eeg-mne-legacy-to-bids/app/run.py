#!/usr/bin/env python3
"""
NIR plugin — legacy continuous EEG → BIDS (minimal EEG-only dataset).

Reads one raw file from the same layout as eeg_preprocessing:
  $NIR_INPUT_ROOT/eeg/raw/<file>.edf|.bdf|.vhdr|.fif|...

Optional BIDS-native typing (recommended):
  $NIR_INPUT_ROOT/metadata/channels.tsv   (BIDS channel table: name, type, ...)

Optional run labels:
  $NIR_INPUT_ROOT/metadata/bids_config.yaml
    subject: "01"          # BIDS subject id without "sub-" prefix
    task: "rest"
    session: null          # or "01"
    run: "01"
    acq: null

Outputs:
  $NIR_OUTPUT_ROOT/bids_dataset/   (BIDS root with sub-*/eeg/, dataset_description.json, ...)

Notes:
  - "ERD" is not a standard EEG interchange format; convert vendor-specific exports to
    EDF / BrainVision / FIF with vendor tools first, then use this plugin.
  - If channels.tsv is absent, channel types come from the file header (often wrong for EDF);
    follow-up preprocessing can still apply heuristics on the BIDS export or on legacy EDF path.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import mne
import yaml
from mne_bids import BIDSPath, write_raw_bids


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


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
    raise FileNotFoundError(f"Missing {input_root}/eeg/raw (file or directory)")


def _read_raw(path: Path) -> mne.io.BaseRaw:
    suf = path.suffix.lower()
    if suf == ".fif":
        return mne.io.read_raw_fif(path, preload=False, verbose="ERROR")
    if suf == ".edf":
        return mne.io.read_raw_edf(path, preload=False, verbose="ERROR")
    if suf == ".bdf":
        return mne.io.read_raw_bdf(path, preload=False, verbose="ERROR")
    if suf == ".vhdr":
        return mne.io.read_raw_brainvision(path, preload=False, verbose="ERROR")
    if suf == ".set":
        return mne.io.read_raw_eeglab(path, preload=False, verbose="ERROR")
    raise ValueError(f"Unsupported extension: {path}")


# BIDS channel type string -> MNE type (subset)
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


def _apply_channels_tsv(raw: mne.io.BaseRaw, tsv_path: Path) -> None:
    """Apply BIDS channels.tsv types to Raw (tab-separated, header row)."""
    import pandas as pd

    df = pd.read_csv(tsv_path, sep="\t")
    if "name" not in df.columns or "type" not in df.columns:
        raise ValueError("channels.tsv must include 'name' and 'type' columns")
    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        btype = str(row["type"]).strip().upper()
        if name not in raw.ch_names:
            continue
        mne_t = _BIDS_TO_MNE.get(btype, "misc")
        mapping[name] = mne_t
    if mapping:
        raw.set_channel_types(mapping, verbose="ERROR")


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))

    bids_root = out_root / "bids_dataset"
    bids_root.mkdir(parents=True, exist_ok=True)
    log_path = out_root / "logs" / "legacy_to_bids.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        print(msg, flush=True)
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(msg + "\n")

    cfg_path = in_root / "metadata" / "bids_config.yaml"
    cfg = _load_yaml(cfg_path)
    subject = str(cfg.get("subject", "01"))
    subject = re.sub(r"^sub-", "", subject, flags=re.I)
    task = str(cfg.get("task", "rest"))
    session = cfg.get("session")
    run = cfg.get("run", "01")
    acquisition = cfg.get("acq") or cfg.get("acquisition")

    try:
        raw_path = _find_raw_eeg(in_root)
        log(f"Loading {raw_path}")
        raw = _read_raw(raw_path)

        ch_tsv = in_root / "metadata" / "channels.tsv"
        if ch_tsv.is_file():
            _apply_channels_tsv(raw, ch_tsv)
            log(f"Applied channel types from {ch_tsv}")
        else:
            log(
                "WARN: no metadata/channels.tsv — using file header types only. "
                "Add BIDS channels.tsv for reproducible ECG/EOG/EEG separation."
            )

        bids_path = BIDSPath(
            subject=subject,
            session=str(session) if session else None,
            task=task,
            run=str(run) if run is not None else None,
            acquisition=str(acquisition) if acquisition else None,
            datatype="eeg",
            root=bids_root,
        )

        # preload=False keeps large EDFs memory-efficient; MNE-BIDS converts to BIDS BrainVision.
        write_raw_bids(raw, bids_path, overwrite=True, verbose=False)
        log(f"Wrote BIDS dataset under {bids_root}")

        summary = {
            "bids_root": str(bids_root),
            "source_file": str(raw_path),
            "subject": subject,
            "task": task,
            "session": session,
            "run": run,
            "had_channels_tsv": ch_tsv.is_file(),
        }
        (out_root / "legacy_to_bids_summary.json").write_text(
            json.dumps(summary, indent=2),
            encoding="utf-8",
        )
        return 0
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback

        log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
