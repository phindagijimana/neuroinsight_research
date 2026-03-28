"""Tests for multimodal staging folder validation."""

import pytest

from backend.validation.workflow_staging import validate_multimodal_epilepsy_biomarker_inputs


def test_accepts_single_staging_directory():
    validate_multimodal_epilepsy_biomarker_inputs(["/data/run_inputs"])


def test_accepts_dir_and_t1_in_same_folder():
    validate_multimodal_epilepsy_biomarker_inputs(
        ["/data/run_inputs", "/data/run_inputs/T1w.nii.gz"]
    )


def test_rejects_split_locations():
    with pytest.raises(ValueError, match="single staging folder"):
        validate_multimodal_epilepsy_biomarker_inputs(
            ["/data/eeg_only", "/other/T1w.nii.gz"]
        )


def test_rejects_t1_only():
    with pytest.raises(ValueError, match="staging directory"):
        validate_multimodal_epilepsy_biomarker_inputs(["/data/run_inputs/T1w.nii.gz"])


def test_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_multimodal_epilepsy_biomarker_inputs([])
