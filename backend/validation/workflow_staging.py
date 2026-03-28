"""Workflow-specific rules for input path layout (API validation before submit)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List


def _looks_like_nifti(path: str) -> bool:
    name = Path(path.strip()).name.lower()
    return name.endswith(".nii.gz") or name.endswith(".nii")


def _staging_folder_for_path(path: str) -> str:
    """Return the single staging directory that must contain EEG + imaging for multimodal runs."""
    pp = Path(path.strip()).expanduser()
    if _looks_like_nifti(str(pp)):
        return os.path.normpath(str(pp.parent))
    return os.path.normpath(str(pp))


def validate_multimodal_epilepsy_biomarker_inputs(input_files: List[str]) -> None:
    """
    Require one staging folder: EEG layout (e.g. eeg/raw/) and T1w.nii.gz must live under
    the same directory. Every submitted path must resolve to that same folder (directory
    path) or to a file inside it (e.g. .../T1w.nii.gz).
    """
    if not input_files:
        raise ValueError(
            "Multimodal Epilepsy Biomarker requires a staging directory plus inputs; "
            "input_files is empty."
        )

    roots = [_staging_folder_for_path(p) for p in input_files]
    unique = sorted(set(roots))
    if len(unique) != 1:
        raise ValueError(
            "Multimodal Epilepsy Biomarker requires a single staging folder: put the EEG dataset "
            "(e.g. eeg/raw/) and the T1-weighted image (T1w.nii.gz) in the same directory, then "
            "submit that folder and/or paths under it only. "
            f"Paths resolve to different locations: {unique}"
        )

    if len(input_files) == 1 and _looks_like_nifti(input_files[0]):
        raise ValueError(
            "Submit the staging directory that contains both EEG and T1w (for example the folder "
            "with eeg/raw/ and T1w.nii.gz), not only the T1 NIfTI file."
        )
