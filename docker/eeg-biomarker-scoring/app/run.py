#!/usr/bin/env python3
"""
NIR biomarker_scoring — aggregate ROI features into summary scores + viewer JSON.

Inputs (NIR_INPUT_ROOT):
  features/roi_source_features.json
  features/roi_structural_features.json
  features/concordance_features.json
Optional:
  metadata/biomarker_scoring_config.yaml  — keys: left_roi, right_roi (names in JSON)

Outputs (NIR_OUTPUT_ROOT):
  biomarker/biomarker_scores.json
  biomarker/laterality_score.json
  biomarker/concordance_score.json
  biomarker/viewer_summary.json
  logs/biomarker_scoring.log
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _log(msg: str, log_fp: Path) -> None:
    line = msg + "\n"
    print(msg, flush=True)
    log_fp.parent.mkdir(parents=True, exist_ok=True)
    with log_fp.open("a", encoding="utf-8") as f:
        f.write(line)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    in_root = Path(os.environ.get("NIR_INPUT_ROOT", "/data/input"))
    out_root = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    log_path = out_root / "logs" / "biomarker_scoring.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.is_file():
        log_path.unlink()

    try:
        feat = in_root / "features"
        src = _load_json(feat / "roi_source_features.json")
        struct = _load_json(feat / "roi_structural_features.json")
        conc = _load_json(feat / "concordance_features.json")

        cfg: dict[str, Any] = {}
        cfg_path = in_root / "metadata" / "biomarker_scoring_config.yaml"
        if cfg_path.is_file():
            import yaml

            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if not isinstance(cfg, dict):
            cfg = {}

        left_roi = str(cfg.get("left_roi", "hippocampus_left"))
        right_roi = str(cfg.get("right_roi", "hippocampus_right"))

        def _src_val(name: str) -> float:
            if name not in src:
                return 0.0
            v = src[name]
            if isinstance(v, dict):
                return float(v.get("mean_abs_source", 0.0))
            return float(v)

        def _vol_sum(name: str) -> float:
            if name not in struct:
                return 0.0
            v = struct[name]
            if isinstance(v, dict):
                return float(v.get("volume_mm3_sum", 0.0))
            return float(v)

        s_l, s_r = _src_val(left_roi), _src_val(right_roi)
        t_l, t_r = _vol_sum(left_roi), _vol_sum(right_roi)

        src_lat = (s_l - s_r) / (abs(s_l) + abs(s_r) + 1e-9)
        str_lat = (t_l - t_r) / (abs(t_l) + abs(t_r) + 1e-9)
        agreement = float((src_lat * str_lat) > 0)

        keys = sorted(set(src.keys()) & set(struct.keys()))
        sv = [_src_val(k) for k in keys]
        tv = [_vol_sum(k) for k in keys]
        concordance_r = 0.0
        if len(keys) >= 2:
            import numpy as np

            a, b = np.array(sv), np.array(tv)
            if np.std(a) > 1e-12 and np.std(b) > 1e-12:
                concordance_r = float(np.corrcoef(a, b)[0, 1])

        scores: dict[str, Any] = {
            "laterality": {
                "source_lateralization_index": float(src_lat),
                "structural_asymmetry_index": float(str_lat),
                "same_side_agreement": agreement,
                "left_roi": left_roi,
                "right_roi": right_roi,
            },
            "cross_modality": {
                "pearson_r_source_vs_volume": concordance_r,
                "n_rois_used": len(keys),
            },
            "concordance_block_rows": len(conc),
        }

        bio_dir = out_root / "biomarker"
        bio_dir.mkdir(parents=True, exist_ok=True)
        (bio_dir / "biomarker_scores.json").write_text(
            json.dumps(scores, indent=2), encoding="utf-8"
        )
        (bio_dir / "laterality_score.json").write_text(
            json.dumps(scores["laterality"], indent=2), encoding="utf-8"
        )
        (bio_dir / "concordance_score.json").write_text(
            json.dumps(
                {"pearson_r": concordance_r, "method": "pearson_r_across_rois"},
                indent=2,
            ),
            encoding="utf-8",
        )
        (bio_dir / "viewer_summary.json").write_text(
            json.dumps(
                {
                    "title": "Multimodal epilepsy biomarker (NIR)",
                    "bullets": [
                        f"Source lateralization (EEG): {src_lat:.4f}",
                        f"Structural asymmetry (MRI): {str_lat:.4f}",
                        f"Same-side agreement: {agreement:.0f}",
                        f"ROI correlation (source vs volume): {concordance_r:.4f}",
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        _log(f"Wrote biomarker outputs under {bio_dir}", log_path)
        return 0
    except Exception as e:
        _log(f"ERROR: {e}", log_path)
        import traceback

        _log(traceback.format_exc(), log_path)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
