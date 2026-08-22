"""Tests for backend.core.job_labels."""

from types import SimpleNamespace

from backend.core.job_labels import (
    build_output_folder_basename,
    extract_job_labels,
    pipeline_slug,
)


def _job(**kwargs):
    defaults = {"parameters": {}, "input_files": []}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_subject_from_parameters():
    labels = extract_job_labels(
        _job(parameters={"subject_id": "001", "session_id": "1"}, input_files=["/data/CIDUR_bids"])
    )
    assert labels.subject_label == "sub-001 · ses-1"


def test_subject_from_bids_path():
    path = "/Users/me/CIDUR_bids/sub-001/ses-1/anat/sub-001_ses-1_T1w.nii.gz"
    labels = extract_job_labels(_job(input_files=[path]))
    assert labels.subject_label == "sub-001 · ses-1"
    assert labels.input_label == "sub-001_ses-1_T1w"


def test_subject_from_nifti_filename_only():
    path = "/data/sub-042_T1w.nii.gz"
    labels = extract_job_labels(_job(input_files=[path]))
    assert labels.subject_label == "sub-042"
    assert labels.input_label == "sub-042_T1w"


def test_output_folder_basename_freesurfer():
    job_id = "76625681-4f2a-9b1c-8d3e-1a2b3c4d5e6f"
    path = "/Users/me/CIDUR_bids/sub-001/ses-1/anat/sub-001_ses-1_T1w.nii.gz"
    name = build_output_folder_basename(
        job_id,
        input_files=[path],
        plugin_id="freesurfer_recon",
        pipeline_name="FreeSurfer Volumetric Segmentation",
    )
    assert name == "sub-001_ses-1_fs_76625681"


def test_output_folder_basename_without_session():
    job_id = "76625681-4f2a-9b1c-8d3e-1a2b3c4d5e6f"
    name = build_output_folder_basename(
        job_id,
        parameters={"subject_id": "001"},
        input_files=["/data/CIDUR_bids"],
        plugin_id="freesurfer_recon",
    )
    assert name == "sub-001_fs_76625681"


def test_pipeline_slug_freesurfer():
    assert pipeline_slug("freesurfer_recon") == "fs"
