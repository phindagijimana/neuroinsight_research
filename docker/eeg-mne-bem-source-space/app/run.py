#!/usr/bin/env python3
"""
NIR plugin: BEM + cortical source space from a T1 NIfTI (MNE + FreeSurfer watershed).

Writes:
  models/bem_sol.fif
  models/src.fif

Requires FreeSurfer tools (mri_convert, mri_watershed) on PATH — use the
eeg-mne-bem-source-space image based on freesurfer/freesurfer.

Input (NIR_INPUT_ROOT):
  T1w.nii.gz or T1.nii.gz  (also searches one level deep)

Optional metadata/bem_source_config.yaml:
  subject_id: str       # FreeSurfer subject id (default: subject)
  volume_grid_mm: float # volume source grid spacing in mm (default: 7.0)
  ico: int              # BEM surface decimation (default: 4)

Environment:
  NIR_SUBJECTS_DIR   SUBJECTS_DIR (default: under NIR_OUTPUT_ROOT/freesurfer_subjects)
  NIR_FS_SUBJECT     Subject name (default: subject)

Watershed BEM does not produce cortical lh/rh surfaces; src.fif is a *volume* source space
bounded by the BEM (inner skull), which forward_model accepts as models/src.fif.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import mne
import yaml


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _find_t1(in_root: Path) -> Path | None:
    for name in ("T1w.nii.gz", "T1.nii.gz"):
        p = in_root / name
        if p.is_file():
            return p
    for sub in in_root.iterdir():
        if sub.is_dir():
            for name in ("T1w.nii.gz", "T1.nii.gz"):
                p = sub / name
                if p.is_file():
                    return p
    return None


def _freesurfer_home() -> Path:
    env = os.environ.get("FREESURFER_HOME")
    if env:
        return Path(env)
    for p in ("/opt/freesurfer", "/usr/local/freesurfer"):
        if Path(p).is_dir():
            return Path(p)
    raise RuntimeError(
        "FREESURFER_HOME not set and no default FreeSurfer install found."
    )


def _run_fs_cmd(args: list[str], log_fp: Path) -> None:
    fs_home = _freesurfer_home()
    setup = fs_home / "SetUpFreeSurfer.sh"
    if not setup.is_file():
        raise FileNotFoundError(f"Missing {setup}")
    inner = " ".join(shlex.quote(a) for a in args)
    cmd = [
        "bash",
        "-lc",
        f"set -euo pipefail && source {shlex.quote(str(setup))} && exec {inner}",
    ]
    _log("Running: " + " ".join(args), log_fp)
    subprocess.run(cmd, check=True)


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "bem_source_space.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    subject = os.environ.get("NIR_FS_SUBJECT", os.environ.get("SUBJECT_ID", "subject"))
    default_subjects = out_root / "freesurfer_subjects"
    subjects_dir = Path(os.environ.get("NIR_SUBJECTS_DIR", str(default_subjects)))
    subjects_dir.mkdir(parents=True, parents=True)
    os.environ.setdefault("SUBJECTS_DIR", str(subjects_dir))

    cfg_path = in_root / "metadata" / "bem_source_config.yaml"
    volume_grid_mm = 7.0
    ico = 4
    if cfg_path.is_file():
        with cfg_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        if isinstance(cfg, dict):
            subject = str(cfg.get("subject_id", subject))
            volume_grid_mm = float(cfg.get("volume_grid_mm", volume_grid_mm))
            ico = int(cfg.get("ico", ico))

    try:
        t1 = _find_t1(in_root)
        if t1 is None:
            raise FileNotFoundError(
                "Missing T1w.nii.gz or T1.nii.gz under input (same layout as multimodal staging)."
            )
        _log(f"Using T1: {t1}", log_path)

        subj_mri = subjects_dir / subject / "mri"
        subj_mri.mkdir(parents=True, parents=True)
        t1_mgz = subj_mri / "T1.mgz"
        _run_fs_cmd(["mri_convert", str(t1), str(t1_mgz)], log_path)

        from mne.bem import make_watershed_bem

        _log("Running watershed BEM surfaces (FreeSurfer)…", log_path)
        make_watershed_bem(
            subject,
            subjects_dir=str(subjects_dir),
            overwrite=True,
            T1=str(t1_mgz),
            verbose="ERROR",
        )

        conductivities = (0.3, 0.006, 0.3)
        _log(f"make_bem_model ico={ico} …", log_path)
        surfaces = mne.make_bem_model(
            subject=subject,
            ico=ico,
            conductivity=conductivities,
            subjects_dir=str(subjects_dir),
            verbose="ERROR",
        )
        bem_sol = mne.make_bem_solution(surfaces, verbose="ERROR")

        models = out_root / "models"
        models.mkdir(parents=True, exist_ok=True)
        bem_out = models / "bem_sol.fif"
        mne.write_bem_solution(str(bem_out), bem_sol, overwrite=True, verbose="ERROR")
        _log(f"Wrote {bem_out}", log_path)

        _log(f"setup_volume_source_space pos={volume_grid_mm} mm (BEM-bounded) …", log_path)
        src = mne.setup_volume_source_space(
            subject=subject,
            pos=volume_grid_mm,
            bem=bem_sol,
            subjects_dir=str(subjects_dir),
            mindist=5.0,
            verbose="ERROR",
        )
        src_out = models / "src.fif"
        mne.write_source_spaces(str(src_out), src, overwrite=True, verbose="ERROR")
        _log(f"Wrote {src_out}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
