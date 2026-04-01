#!/usr/bin/env python3
"""
NIR forward_model — MNE make_forward_solution.

Tutorial basis:
  https://mne.tools/stable/auto_tutorials/forward/30_forward.html

Required inputs (under NIR_INPUT_ROOT):
  eeg/clean_raw.fif          — channel info + EEG geometry
  One of:
    coreg/trans.fif          — head<->MRI transform (MNE -trans.fif)
    coreg/eeg_to_mri_trans.fif
  models/src.fif             — optional; source space (or first *-src.fif under models/)
  models/bem_sol.fif         — optional; BEM solution or *-bem-sol.fif under models/

If models/ is missing src and/or bem files, a reproducible fallback is used: EEG
multi-layer sphere (make_sphere_model) + volume source space on that sphere
(setup_volume_source_space). Logged as WARNING — use subject-specific BEM/src for research.

Optional:
  metadata/forward_config.yaml — mindist_mm, n_jobs
  NIR_FORWARD_SPHERE_GRID_MM — grid spacing for auto volume source space (default 25)

Outputs:
  models/forward_solution.fif
  logs/forward_model.log
"""

from __future__ import annotations

import os
from pathlib import Path

import mne
import numpy as np
import yaml


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _find_first(dir_path: Path, patterns: tuple[str, ...]) -> Path | None:
    if not dir_path.is_dir():
        return None
    for pat in patterns:
        for p in sorted(dir_path.glob(pat)):
            if p.is_file():
                return p
    return None


def _relabeled_auxiliary_channels(ch_name: str) -> str | None:
    """Match eeg-mne-preprocessing: EDF/FIF often mark EKG/ECG as EEG; forward needs scalp EEG only."""
    c = ch_name.lower().strip()
    if any(s in c for s in ("ekg", "ecg", "lead", "cardiac")):
        return "ecg"
    if "emg" in c:
        return "emg"
    if any(s in c for s in ("eog", "veog", "heog")):
        return "eog"
    if any(s in c for s in ("exg", "dc chan", "trigger", "trig", "photo", "pulse")):
        return "misc"
    return None


def _restrict_to_eeg_channels(raw: mne.io.BaseRaw, log_fp: Path) -> mne.io.BaseRaw:
    """Same intent as eeg_preprocessing: remove EKG/ECG/EMG/EOG mis-typed as EEG.

    Use drop_channels (not set_channel_types): average-reference projectors block
    relabeling while projectors are still attached.
    """
    to_drop: list[str] = []
    for i, name in enumerate(raw.ch_names):
        if mne.channel_type(raw.info, i) != "eeg":
            continue
        if _relabeled_auxiliary_channels(name) is not None:
            to_drop.append(name)
    if to_drop:
        raw.drop_channels(to_drop)
        _log(f"Dropped mis-typed EEG/aux channels: {to_drop}", log_fp)
    picks = mne.pick_types(raw.info, eeg=True, exclude=[])
    if len(picks) == 0:
        raise RuntimeError(
            "No EEG channels after aux cleanup; check channel labels or types."
        )
    raw.pick(picks)
    return raw


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "forward_model.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    cfg_path = in_root / "metadata" / "forward_config.yaml"
    mindist_mm = 5.0
    n_jobs = 1
    if cfg_path.is_file():
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if isinstance(cfg, dict):
            mindist_mm = float(cfg.get("mindist_mm", mindist_mm))
            n_jobs = int(cfg.get("n_jobs", n_jobs))

    try:
        raw_path = in_root / "eeg" / "clean_raw.fif"
        if not raw_path.is_file():
            raise FileNotFoundError(f"Missing {raw_path}")
        # Preload so montage updates channel locations in-place for forward.
        raw = mne.io.read_raw_fif(raw_path, preload=True, verbose="ERROR")
        # Align with eeg_preprocessing: drop EKG/ECG/EMG/EOG mis-labeled as EEG (older clean_raw.fif).
        raw = _restrict_to_eeg_channels(raw, log_path)

        eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        if any(
            not np.any(np.isfinite(raw.info["chs"][i]["loc"][:3])) for i in eeg_picks
        ):
            _log(
                "WARNING: Some EEG channels lack 3D positions; applying "
                "standard_1020 montage with alias matching (forward fallback).",
                log_path,
            )
            raw.set_montage(
                mne.channels.make_standard_montage("standard_1020"),
                on_missing="ignore",
                match_alias=True,
            )
        still_bad = [
            raw.ch_names[i]
            for i in mne.pick_types(raw.info, eeg=True, exclude=[])
            if not np.any(np.isfinite(raw.info["chs"][i]["loc"][:3]))
        ]
        if still_bad:
            raise RuntimeError(
                "EEG channels still lack 3D positions after standard_1020 montage: "
                f"{still_bad[:12]}{'...' if len(still_bad) > 12 else ''}. "
                "Rename channels to standard labels or supply a dig montage."
            )

        trans_path = None
        for cand in (
            in_root / "coreg" / "trans.fif",
            in_root / "coreg" / "eeg_to_mri_trans.fif",
        ):
            if cand.is_file():
                trans_path = cand
                break
        if trans_path is None:
            raise FileNotFoundError(
                "Missing transform: place coreg/trans.fif or coreg/eeg_to_mri_trans.fif"
            )
        trans = mne.read_trans(trans_path)

        # Optional BEM/src on disk (staging). Do not mkdir under in_root: forward_merge is
        # often a read-only Singularity bind without models/.
        models_dir_in = in_root / "models"
        models_dir: Path | None = models_dir_in if models_dir_in.is_dir() else None

        src_path: Path | None = None
        if models_dir is not None:
            src_path = models_dir / "src.fif"
            if not src_path.is_file():
                found = _find_first(models_dir, ("*-src.fif", "*src.fif"))
                src_path = found
        src = None
        if src_path is not None and Path(src_path).is_file():
            src = mne.read_source_spaces(src_path)

        bem_path: Path | None = None
        if models_dir is not None:
            bem_path = models_dir / "bem_sol.fif"
            if not bem_path.is_file():
                bem_path = _find_first(
                    models_dir,
                    ("*-bem-sol.fif", "*bem-sol.fif", "bem_sol.fif"),
                )
        bem = None
        if bem_path is not None and Path(bem_path).is_file():
            bem = mne.read_bem_solution(str(bem_path))

        if bem is None:
            try:
                bem = mne.make_sphere_model(
                    info=raw.info,
                    r0="auto",
                    head_radius="auto",
                )
                _log(
                    "WARNING: No BEM file in models/; using EEG sphere fit from digitization "
                    "(pipeline fallback — use subject BEM for research).",
                    log_path,
                )
            except RuntimeError:
                # Continuous EEG often has no headshape digitization in raw.info["dig"].
                bem = mne.make_sphere_model(
                    r0=(0.0, 0.0, 0.04),
                    head_radius=0.09,
                )
                _log(
                    "WARNING: No BEM on disk and no digitization in raw; using standard "
                    "4-layer 90 mm scalp sphere (reproducible pipeline fallback only).",
                    log_path,
                )

        pos_mm = float(os.environ.get("NIR_FORWARD_SPHERE_GRID_MM", "25.0"))
        if src is None:
            src = mne.setup_volume_source_space(
                sphere=bem,
                pos=pos_mm,
                mindist=mindist_mm,
            )
            _log(
                f"WARNING: No source space in models/; using volume grid {pos_mm} mm "
                "inside sphere bounds (pipeline fallback).",
                log_path,
            )

        src_desc = src_path.name if src_path is not None else f"volume_grid_{pos_mm}mm"
        bem_desc = bem_path.name if bem_path is not None and bem_path.is_file() else "sphere_auto"
        _log(
            f"Computing forward: trans={trans_path.name} src={src_desc} bem={bem_desc}",
            log_path,
        )
        fwd = mne.make_forward_solution(
            raw.info,
            trans=trans,
            src=src,
            bem=bem,
            meg=False,
            eeg=True,
            mindist=mindist_mm / 1000.0,
            n_jobs=n_jobs,
            verbose="ERROR",
        )

        out_dir = out_root / "models"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_fif = out_dir / "forward_solution.fif"
        mne.write_forward_solution(out_fif, fwd, overwrite=True, verbose="ERROR")
        _log(f"Wrote {out_fif}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
