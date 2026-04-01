"""Build native/roi_merge under the job output tree before feature extraction.

Writes source/, segmentation/, metadata/ under {job_root}/native/roi_merge so
NIR_INPUT_ROOT=/data/inputs/roi_merge (same path on host) matches the merged tree.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_FS_ROI = {
    "hippocampus_left": {"label_ids": [17]},
    "hippocampus_right": {"label_ids": [53]},
}


def _staging_dir_from_input_files(input_files: list[str]) -> Optional[Path]:
    for p in input_files or []:
        pp = Path(p).expanduser()
        if pp.is_dir():
            return pp
    return None


def _find_aseg_mgz(output_dir: Path) -> Optional[Path]:
    subjects = output_dir / "native" / "mri_segmentation" / "SUBJECTS_DIR"
    if not subjects.is_dir():
        return None
    for subj in sorted(subjects.iterdir()):
        if not subj.is_dir():
            continue
        for name in ("aseg.auto.mgz", "aseg.mgz"):
            p = subj / "mri" / name
            if p.is_file():
                return p
    return None


def ensure_multimodal_roi_merge(output_dir: Path, input_files: list[str]) -> None:
    """Create native/roi_merge with source/, segmentation/, metadata/ for roi_feature_extraction."""
    rm = output_dir / "native" / "roi_merge"
    if rm.exists():
        shutil.rmtree(rm)
    rm.mkdir(parents=True)

    src_sl = output_dir / "native" / "source_localization" / "source"
    if src_sl.is_dir():
        (rm / "source").symlink_to(src_sl.resolve(), target_is_directory=True)
    else:
        logger.warning("roi_merge: missing %s", src_sl)

    seg_out = rm / "segmentation"
    seg_out.mkdir(parents=True)
    staged = _staging_dir_from_input_files(input_files)

    if staged and (staged / "segmentation").is_dir():
        for p in (staged / "segmentation").iterdir():
            if p.is_file():
                shutil.copy2(p, seg_out / p.name)

    if not any(seg_out.glob("*.nii.gz")):
        aseg = _find_aseg_mgz(output_dir)
        if aseg is not None and aseg.is_file():
            try:
                import nibabel as nib
            except ImportError:
                logger.warning(
                    "roi_merge: nibabel unavailable; cannot convert %s — "
                    "stage segmentation/*.nii.gz under the workflow input directory.",
                    aseg,
                )
            else:
                try:
                    img = nib.load(str(aseg))
                    nib.save(img, str(seg_out / "region_labels.nii.gz"))
                    logger.info("roi_merge: wrote region_labels.nii.gz from %s", aseg)
                except Exception as e:
                    logger.warning("roi_merge: could not convert aseg to NIfTI: %s", e)
        else:
            logger.warning(
                "roi_merge: no label NIfTI in segmentation/ and no aseg.mgz under mri_segmentation"
            )

    meta_out = rm / "metadata"
    meta_out.mkdir(parents=True)
    roi_def_path = meta_out / "roi_definitions.json"
    staged_roi = None
    if staged and (staged / "metadata" / "roi_definitions.json").is_file():
        staged_roi = staged / "metadata" / "roi_definitions.json"
    if staged_roi is not None:
        shutil.copy2(staged_roi, roi_def_path)
    else:
        roi_def_path.write_text(json.dumps(_DEFAULT_FS_ROI, indent=2), encoding="utf-8")
        logger.info("roi_merge: wrote default roi_definitions.json (FS aseg labels 17/53)")


def resolve_job_output_root() -> Path:
    """Root directory that contains native/ (same as host job outputs/)."""
    p = os.environ.get("NIR_JOB_OUTPUT_ROOT")
    if p:
        return Path(p)
    out = Path(os.environ.get("NIR_OUTPUT_ROOT", "/data/output"))
    if len(out.parts) >= 2 and out.parts[-1] == "roi_feature_extraction" and out.parts[-2] == "native":
        return out.parent.parent
    return Path("/data/outputs")


def resolve_staged_input_files() -> list[str]:
    """Ordered candidate workflow input directories (first match used for staged metadata/segmentation)."""
    files: list[str] = []
    e = os.environ.get("NIR_STAGED_INPUT_DIR")
    if e:
        ep = Path(e)
        if ep.is_dir():
            files.append(str(ep.resolve()))
    d = Path("/data/inputs/input_dir")
    if d.is_dir() and str(d.resolve()) not in files:
        files.append(str(d.resolve()))
    return files
