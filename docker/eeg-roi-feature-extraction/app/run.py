#!/usr/bin/env python3
"""
NIR roi_feature_extraction — fuse source map (NIfTI) + segmentation into per-ROI features.

Inputs (NIR_INPUT_ROOT):
  source/source_map.nii.gz     — required
  segmentation/              — region_labels.nii.gz (FreeSurfer-style ints) and/or
                               structural_metrics.json / hippocampal_volumes.json
  metadata/roi_definitions.json — {"roi_name": {"label_ids": [int, ...]}, ...}

Outputs (NIR_OUTPUT_ROOT):
  features/roi_source_features.json
  features/roi_structural_features.json
  features/concordance_features.json
  logs/roi_feature_extraction.log
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import nibabel as nib
from nibabel.processing import resample_from_to


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _find_labels_nii(seg_dir: Path) -> Path | None:
    for pat in ("region_labels.nii.gz", "aseg_in_source_space.nii.gz", "*labels*.nii.gz"):
        for p in sorted(seg_dir.glob(pat)):
            if p.is_file():
                return p
    return None


def _load_structural_json(seg_dir: Path) -> dict[str, Any] | None:
    for name in ("structural_metrics.json", "hippocampal_volumes.json"):
        p = seg_dir / name
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            # normalize: expect per-ROI dict of metrics or nested "per_roi"
            if isinstance(data, dict) and "per_roi" in data:
                return data["per_roi"]
            if isinstance(data, dict):
                return data
    return None


def _mean_abs_in_labels(
    source_data: np.ndarray,
    label_data: np.ndarray,
    label_ids: list[int],
) -> float:
    mask = np.zeros(label_data.shape, dtype=bool)
    for lid in label_ids:
        mask |= label_data == int(lid)
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs(source_data[mask])))


def _volume_mm3_per_label(label_data: np.ndarray, label_id: int, zooms: tuple[float, ...]) -> float:
    nvox = int(np.sum(label_data == int(label_id)))
    vox_mm3 = float(np.prod(zooms))
    return nvox * vox_mm3


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "roi_feature_extraction.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    try:
        src_path = in_root / "source" / "source_map.nii.gz"
        roi_path = in_root / "metadata" / "roi_definitions.json"
        seg_dir = in_root / "segmentation"

        if not src_path.is_file():
            raise FileNotFoundError(f"Missing {src_path}")
        if not roi_path.is_file():
            raise FileNotFoundError(f"Missing {roi_path}")
        if not seg_dir.is_dir():
            raise FileNotFoundError(f"Missing segmentation dir {seg_dir}")

        roi_def = json.loads(roi_path.read_text(encoding="utf-8"))
        if not isinstance(roi_def, dict):
            raise ValueError("roi_definitions.json must be a JSON object")

        source_img = nib.load(str(src_path))
        labels_path = _find_labels_nii(seg_dir)
        if labels_path is None:
            raise FileNotFoundError(
                f"No label volume in {seg_dir} — add region_labels.nii.gz (or *labels*.nii.gz) "
                "aligned with source space (resampling is applied if shapes differ)."
            )

        structural_json = _load_structural_json(seg_dir)
        labels_img = nib.load(str(labels_path))
        if source_img.shape[:3] != labels_img.shape[:3]:
            _log(
                f"Resampling source ({source_img.shape}) to label grid ({labels_img.shape})",
                log_path,
            )
            source_img = resample_from_to(source_img, labels_img, order=1)
        source_data = np.asanyarray(source_img.dataobj)
        label_data = np.asanyarray(labels_img.dataobj).astype(np.int32)
        zooms = labels_img.header.get_zooms()[:3]

        roi_source: dict[str, Any] = {}
        roi_struct: dict[str, Any] = {}
        conc: dict[str, Any] = {}

        for roi_name, spec in roi_def.items():
            if not isinstance(spec, dict) or "label_ids" not in spec:
                continue
            lids = [int(x) for x in spec["label_ids"]]

            roi_source[roi_name] = {
                "mean_abs_source": _mean_abs_in_labels(source_data, label_data, lids),
                "label_ids": lids,
            }
            vols = [_volume_mm3_per_label(label_data, lid, zooms) for lid in lids]
            roi_struct[roi_name] = {
                "volume_mm3_sum": float(np.sum(vols)),
                "volume_mm3_per_label": {str(lids[i]): vols[i] for i in range(len(lids))},
            }

            if structural_json and roi_name in structural_json:
                roi_struct[roi_name]["metrics_from_segmentation_json"] = structural_json[roi_name]

            conc[roi_name] = {
                "mean_abs_source": roi_source[roi_name].get("mean_abs_source"),
                "volume_mm3_sum": roi_struct[roi_name].get("volume_mm3_sum"),
            }

        feat_dir = out_root / "features"
        feat_dir.mkdir(parents=True, exist_ok=True)
        (feat_dir / "roi_source_features.json").write_text(
            json.dumps(roi_source, indent=2), encoding="utf-8"
        )
        (feat_dir / "roi_structural_features.json").write_text(
            json.dumps(roi_struct, indent=2), encoding="utf-8"
        )
        (feat_dir / "concordance_features.json").write_text(
            json.dumps(conc, indent=2), encoding="utf-8"
        )
        _log(f"Wrote features under {feat_dir}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
