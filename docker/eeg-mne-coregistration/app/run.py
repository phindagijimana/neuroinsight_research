#!/usr/bin/env python3
"""
NIR eeg_mri_coregistration — head↔MRI alignment artifacts for MNE pipelines.

Full interactive Coregistration (mne.coreg.Coregistration) needs a FreeSurfer subject
tree under SUBJECTS_DIR; this container supports **batch** workflows:

1) **Passthrough:** if `coreg/trans.fif` or `coreg/eeg_to_mri_trans.fif` is provided, copy to output.
2) **JSON matrix:** `metadata/eeg_to_mri_transform.json` with a 4×4 `"matrix"` (head→MRI, meters)
   builds an MNE Transform and writes `eeg_to_mri_trans.fif`.

Also writes `electrode_coords_mri.json` (approximate) by applying the transform to sensor
locations from the montage in `eeg/clean_raw.fif` when possible.

Transform search order (batch workflows):
  (1) `NIR_INPUT_ROOT` (usually prior-step EEG output, e.g. eeg_preprocessing)
  (2) `/data/inputs/input_dir` when present (original staging folder with metadata/coreg)
If none are found, an identity head→MRI transform is written and a WARNING is logged
(reproducible default for pipeline testing; use a real alignment for clinical/research use).

Tutorial references:
  https://mne.tools/stable/auto_tutorials/forward/20_source_alignment.html
  https://mne.tools/stable/auto_tutorials/forward/30_forward.html

Inputs:
  eeg/clean_raw.fif (required for electrode export)
  mri/T1.nii.gz (optional QC reference; not always required for passthrough)
  coreg/trans.fif OR metadata/eeg_to_mri_transform.json

Outputs:
  coreg/eeg_to_mri_trans.fif
  coreg/electrode_coords_mri.json
  logs/coregistration.log
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import mne
import numpy as np
from mne import Transform
from mne.io.constants import FIFF
from mne.transforms import apply_trans


def _staging_input_dir() -> Path | None:
    """Original workflow staging directory (bind-mounted as input_dir in NIR jobs)."""
    p = Path("/data/inputs/input_dir")
    if p.is_dir():
        return p
    return None


def _find_transform_sources(in_root: Path) -> tuple[Path | None, Path | None]:
    """Return (trans_fif_path, json_path) if found under in_root or staging input_dir."""
    roots: list[Path] = [in_root]
    staged = _staging_input_dir()
    if staged is not None and staged.resolve() != in_root.resolve():
        roots.append(staged)

    for root in roots:
        for cand in (root / "coreg" / "trans.fif", root / "coreg" / "eeg_to_mri_trans.fif"):
            if cand.is_file():
                return cand, None
        jpath = root / "metadata" / "eeg_to_mri_transform.json"
        if jpath.is_file():
            return None, jpath
    return None, None


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "coregistration.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    try:
        raw_path = in_root / "eeg" / "clean_raw.fif"
        if not raw_path.is_file():
            raise FileNotFoundError(f"Missing {raw_path}")
        raw = mne.io.read_raw_fif(raw_path, preload=False, verbose="ERROR")

        out_coreg = out_root / "coreg"
        out_coreg.mkdir(parents=True, exist_ok=True)
        out_trans = out_coreg / "eeg_to_mri_trans.fif"

        trans_in, jpath = _find_transform_sources(in_root)

        if trans_in is not None:
            shutil.copy2(trans_in, out_trans)
            trans = mne.read_trans(out_trans)
            _log(f"Using passthrough transform from {trans_in}", log_path)
        elif jpath is not None:
            data = json.loads(jpath.read_text(encoding="utf-8"))
            mat = np.array(data["matrix"], dtype=float)
            if mat.shape != (4, 4):
                raise ValueError("eeg_to_mri_transform.json: 'matrix' must be 4x4")
            # MNE convention: head → MRI (surface RAS)
            t = Transform("head", "mri", trans=mat)
            mne.write_trans(str(out_trans), t)
            trans = t
            _log(f"Built transform from {jpath}", log_path)
        else:
            mat = np.eye(4, dtype=float)
            t = Transform("head", "mri", trans=mat)
            mne.write_trans(str(out_trans), t)
            trans = t
            _log(
                "WARNING: No coreg/trans.fif, coreg/eeg_to_mri_trans.fif, or "
                "metadata/eeg_to_mri_transform.json under NIR_INPUT_ROOT or "
                "/data/inputs/input_dir. Using identity head→MRI transform "
                "(reproducible default for pipeline continuity). Replace with a "
                "fiducial- or ICP-based alignment for publication or clinical use.",
                log_path,
            )

        # Electrode positions in MRI coordinates (approximate, from channel locs in head)
        locs: dict[str, list[float]] = {}
        for ch in raw.info["chs"]:
            if ch["kind"] != FIFF.FIFFV_EEG_CH:
                continue
            loc = ch["loc"][:3]
            if not np.any(np.isfinite(loc)):
                continue
            mri_h = apply_trans(trans, loc.reshape(1, 3))[0]
            locs[ch["ch_name"]] = [float(x) for x in mri_h]

        (out_coreg / "electrode_coords_mri.json").write_text(
            json.dumps(
                {
                    "coords_m": locs,
                    "frame": "mri",
                    "mne_version": mne.__version__,
                    "note": "Approximate; verify against fiducial-based coreg when available.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        _log(f"Wrote {out_trans} and electrode_coords_mri.json", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
