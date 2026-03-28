"""Host-side merged input trees for multimodal EEG workflows (local Docker + SLURM helpers)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _staging_dir_from_input_files(input_files: list[str]) -> Optional[Path]:
    for p in input_files or []:
        pp = Path(p).expanduser()
        if pp.is_dir():
            return pp
    return None


def ensure_multimodal_forward_merge(output_dir: Path, input_files: list[str]) -> None:
    """Create native/forward_merge with eeg/, coreg/, and optional models/ for forward_model."""
    fm = output_dir / "native" / "forward_merge"
    if fm.exists():
        shutil.rmtree(fm)
    fm.mkdir(parents=True)
    ep_eeg = output_dir / "native" / "eeg_preprocessing" / "eeg"
    cg = output_dir / "native" / "eeg_mri_coregistration" / "coreg"
    if ep_eeg.exists():
        (fm / "eeg").symlink_to(ep_eeg.resolve(), target_is_directory=True)
    else:
        logger.warning("forward_merge: missing %s", ep_eeg)
    if cg.exists():
        (fm / "coreg").symlink_to(cg.resolve(), target_is_directory=True)
    else:
        logger.warning("forward_merge: missing %s", cg)
    staged = _staging_dir_from_input_files(input_files)
    if staged and (staged / "models").is_dir():
        (fm / "models").symlink_to((staged / "models").resolve(), target_is_directory=True)


def ensure_multimodal_source_merge(output_dir: Path) -> None:
    """Create native/source_merge with eeg/, models/, events/ for source_localization."""
    sm = output_dir / "native" / "source_merge"
    if sm.exists():
        shutil.rmtree(sm)
    sm.mkdir(parents=True)
    eeg = output_dir / "native" / "eeg_preprocessing" / "eeg"
    models = output_dir / "native" / "forward_model" / "models"
    events = output_dir / "native" / "spike_detection" / "events"
    if eeg.exists():
        (sm / "eeg").symlink_to(eeg.resolve(), target_is_directory=True)
    if models.exists():
        (sm / "models").symlink_to(models.resolve(), target_is_directory=True)
    if events.exists():
        (sm / "events").symlink_to(events.resolve(), target_is_directory=True)
