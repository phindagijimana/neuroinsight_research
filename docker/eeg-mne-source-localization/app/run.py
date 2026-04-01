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
  $NIR_OUTPUT_ROOT/source/source_estimate-*.stc  (lh + rh for surface; volume STC otherwise)
  $NIR_OUTPUT_ROOT/source/source_map.nii.gz  (volume-grid inverses only; mean abs over time)
  $NIR_OUTPUT_ROOT/source/peak_coordinates.json
  $NIR_OUTPUT_ROOT/source/laterality_summary.json
  $NIR_OUTPUT_ROOT/logs/source_localization.log

Surface-only SourceEstimate does not write source_map.nii.gz (use volume forward for ROI NIfTI).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import mne
import nibabel as nib
import numpy as np
from mne.minimum_norm import apply_inverse, make_inverse_operator


def _vol_stc_vertex_positions(stc: mne.VolSourceEstimate, forward: mne.Forward) -> np.ndarray:
    """RAS positions (n_vertices, 3) for each row of stc.data (volume source space)."""
    rr_out: list[np.ndarray] = []
    for si, s in enumerate(forward["src"]):
        v = stc.vertices[si]
        if len(v) == 0:
            continue
        r = s["rr"]
        for i in v:
            if i >= len(r):
                raise RuntimeError(
                    f"vertex index {i} out of bounds for src space {si} (rr len {len(r)})"
                )
            rr_out.append(r[i])
    pos = np.asarray(rr_out, dtype=float)
    if pos.shape[0] != stc.data.shape[0]:
        raise RuntimeError(
            f"vertex position count {pos.shape[0]} != stc.data rows {stc.data.shape[0]}"
        )
    return pos


def _peak_and_laterality(
    stc: mne.SourceEstimate | mne.VolSourceEstimate,
    forward: mne.Forward,
) -> tuple[dict[str, object], dict[str, object]]:
    """Surface STC supports hemi= on get_peak; volume STC does not (MNE 1.8)."""
    if isinstance(stc, mne.VolSourceEstimate):
        pos = _vol_stc_vertex_positions(stc, forward)
        data_abs = np.abs(stc.data)
        peak_amp = np.max(data_abs, axis=1)
        left = pos[:, 0] < 0.0
        lh_max = float(np.max(peak_amp[left])) if np.any(left) else 0.0
        rh_max = float(np.max(peak_amp[~left])) if np.any(~left) else 0.0
        stronger = "lh" if lh_max >= rh_max else "rh"

        def _peak_vert_time(mask: np.ndarray) -> tuple[int, float]:
            if not np.any(mask):
                return 0, 0.0
            idx_local = np.where(mask)[0]
            j = int(np.argmax(peak_amp[mask]))
            im = int(idx_local[j])
            t_i = int(np.argmax(np.abs(stc.data[im])))
            return int(np.concatenate(stc.vertices)[im]), float(stc.times[t_i])

        v_lh, t_lh = _peak_vert_time(left)
        v_rh, t_rh = _peak_vert_time(~left)
        peak_coords = {
            "lh": {"vertex": v_lh, "time_s": t_lh},
            "rh": {"vertex": v_rh, "time_s": t_rh},
            "mne_version": mne.__version__,
            "method": "dSPM",
            "source_space": "volume",
            "note": "Volume grid inverse; hemisphere split by RAS x<0 (left). Not MNI mm without morphing.",
        }
        lat = {
            "stronger_hemisphere": stronger,
            "lh_peak_abs_max": lh_max,
            "rh_peak_abs_max": rh_max,
        }
        return peak_coords, lat

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
        "source_space": "surface",
        "note": "Vertices are in source space; not MNI mm without morphing.",
    }
    lat = {
        "stronger_hemisphere": stronger,
        "lh_peak_abs_max": lh_max,
        "rh_peak_abs_max": rh_max,
    }
    return peak_coords, lat


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
        raw.set_eeg_reference("average", projection=True, verbose="ERROR")
        eeg_picks = mne.pick_types(raw.info, eeg=True, exclude=[])
        if len(eeg_picks) == 0:
            raise RuntimeError("No EEG channels in raw; expected EEG for inverse.")

        _log(f"Loading forward {fwd_path}", log_path)
        forward = mne.read_forward_solution(fwd_path, verbose="ERROR")

        _log("Computing noise covariance from raw (first 60 s)", log_path)
        tmax = min(60.0, float(raw.times[-1]))
        # empirical: no scikit-learn (shrunk/auto require sklearn in many MNE builds)
        noise_cov = mne.compute_raw_covariance(
            raw,
            tmax=tmax,
            picks=eeg_picks,
            method="empirical",
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
        fs = int(raw.first_samp)
        if onsets:
            # Onsets are seconds from the start of this Raw; events use absolute file samples.
            events = np.array(
                [[fs + int(o * sfreq), 0, 1] for o in onsets],
                dtype=np.int64,
            )
            _log(f"Using {len(onsets)} spike-aligned epochs from {spike_path}", log_path)
        else:
            mid = fs + max(int(sfreq * 2.0), raw.n_times // 2)
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

        peak_coords, lat = _peak_and_laterality(stc, forward)

        (src_dir / "peak_coordinates.json").write_text(
            json.dumps(peak_coords, indent=2), encoding="utf-8"
        )
        (src_dir / "laterality_summary.json").write_text(
            json.dumps(lat, indent=2), encoding="utf-8"
        )

        if isinstance(stc, mne.VolSourceEstimate):
            try:
                _log(
                    "Exporting volume source map to NIfTI (source/source_map.nii.gz)",
                    log_path,
                )
                vol_img = stc.as_volume(
                    forward["src"], dest="mri", mri_resolution=False
                )
                data = np.asarray(vol_img.dataobj)
                if data.ndim == 4:
                    data = np.mean(np.abs(data), axis=-1)
                else:
                    data = np.abs(np.squeeze(data))
                if data.ndim != 3:
                    raise RuntimeError(
                        f"Expected 3D volume after reduction, got shape {data.shape}"
                    )
                out_img = nib.Nifti1Image(data, vol_img.affine)
                nib.save(out_img, str(src_dir / "source_map.nii.gz"))
                _log("Wrote source/source_map.nii.gz", log_path)
            except Exception as e:
                _log(f"WARNING: could not export volume NIfTI: {e}", log_path)
        else:
            _log(
                "Surface SourceEstimate: source_map.nii.gz not written (volume inverse only).",
                log_path,
            )

        _log(f"Wrote STC under {stem}*", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
