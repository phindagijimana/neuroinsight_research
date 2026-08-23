"""Human-readable labels for jobs (subject, session, input summary)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

_SUB_RE = re.compile(r"sub-([^/]+)", re.I)
_SES_RE = re.compile(r"ses-([^/]+)", re.I)
_SUB_FILE_RE = re.compile(r"sub-([^_\.]+)", re.I)
_SES_FILE_RE = re.compile(r"ses-([^_\.]+)", re.I)
_UNSAFE_PATH = re.compile(r"[^\w.\-]+", re.ASCII)

# Short pipeline tokens for output folder names (sub-001_fs_76625681).
_PIPELINE_SLUGS: dict[str, str] = {
    "freesurfer_recon": "fs",
    "freesurfer_autorecon_volonly": "fs",
    "freesurfer_longitudinal": "fslong",
    "freesurfer_longitudinal_stats": "fslong",
    "fastsurfer": "fastsurfer",
    "fmriprep": "fmriprep",
    "meld_graph": "meld",
    "qsiprep": "qsiprep",
    "qsirecon": "qsirecon",
    "xcp_d": "xcpd",
    "xcpd": "xcpd",
    "dcm2niix": "dcm2niix",
    "hs_postprocess": "hs",
    "segmentha_t1": "segmentha",
    "segmentha_t2": "segmentha",
}


def _sanitize_segment(value: str, max_len: int = 48) -> str:
    cleaned = _UNSAFE_PATH.sub("", (value or "").strip().replace(" ", "-"))
    cleaned = cleaned.strip("._-")
    return (cleaned[:max_len] if cleaned else "job")


def _normalize_sub_id(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.lower().startswith("sub-"):
        return value if value.startswith("sub-") else f"sub-{value[4:]}"
    return f"sub-{value}"


def _normalize_ses_id(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.lower().startswith("ses-"):
        return value if value.startswith("ses-") else f"ses-{value[4:]}"
    return f"ses-{value}"


def _basename_label(path: str) -> str:
    name = Path(path.replace("\\", "/")).name
    lower = name.lower()
    if lower.endswith(".nii.gz"):
        return name[:-7]
    if lower.endswith(".nii"):
        return name[:-4]
    return name


def _parse_subject_session(
    parameters: Mapping[str, Any], input_files: Sequence[str]
) -> tuple[str, str]:
    params = parameters or {}
    subject_id = str(params.get("subject_id") or "").strip()
    session_id = str(
        params.get("session_id") or params.get("session") or params.get("session_label") or ""
    ).strip()

    primary_input = str(input_files[0]) if input_files else ""
    if primary_input:
        normalized = primary_input.replace("\\", "/")
        name = Path(normalized).name
        if not subject_id:
            sub_match = _SUB_FILE_RE.search(name)
            if sub_match:
                subject_id = sub_match.group(1)
        if not session_id:
            ses_match = _SES_FILE_RE.search(name)
            if ses_match:
                session_id = ses_match.group(1)
        if not subject_id:
            sub_match = _SUB_RE.search(normalized)
            if sub_match:
                subject_id = sub_match.group(1)
        if not session_id:
            ses_match = _SES_RE.search(normalized)
            if ses_match:
                session_id = ses_match.group(1)

    return subject_id, session_id


def subject_folder_segment(
    parameters: Mapping[str, Any] | None = None,
    input_files: Sequence[str] | None = None,
) -> str:
    """Filesystem-safe subject segment, e.g. sub-001 or sub-001_ses-1."""
    subject_id, session_id = _parse_subject_session(parameters or {}, input_files or [])
    if not subject_id:
        return ""
    segment = _sanitize_segment(_normalize_sub_id(subject_id))
    if session_id:
        segment = f"{segment}_{_sanitize_segment(_normalize_ses_id(session_id))}"
    return segment


def pipeline_slug(plugin_id: str = "", pipeline_name: str = "") -> str:
    pid = (plugin_id or "").strip().lower()
    if pid in _PIPELINE_SLUGS:
        return _PIPELINE_SLUGS[pid]
    if pid.startswith("freesurfer"):
        return "fs"
    if pid:
        return _sanitize_segment(pid.replace("_", "-"), 16)

    name = (pipeline_name or "").lower()
    if "freesurfer" in name:
        return "fs"
    if "fmriprep" in name:
        return "fmriprep"
    if "fastsurfer" in name:
        return "fastsurfer"
    if "meld" in name:
        return "meld"
    if pipeline_name:
        token = pipeline_name.split()[0].lower()
        return _sanitize_segment(token, 16)
    return "job"


def build_output_folder_basename(
    job_id: str,
    *,
    parameters: Mapping[str, Any] | None = None,
    input_files: Sequence[str] | None = None,
    plugin_id: str = "",
    pipeline_name: str = "",
    workflow_steps: Sequence[str] | None = None,
) -> str:
    """Human-readable output folder basename, e.g. sub-001_fs_76625681."""
    params = parameters or {}
    inputs = input_files or []
    pid = plugin_id or str(params.get("_plugin_id") or "")
    if not pid and workflow_steps:
        pid = workflow_steps[0]
    if not pid:
        steps = params.get("_workflow_steps")
        if isinstance(steps, list) and steps:
            pid = str(steps[0])

    subject = subject_folder_segment(params, inputs)
    slug = pipeline_slug(pid, pipeline_name)
    short = _sanitize_segment((job_id or "").split("-")[0][:8], 8)

    if subject:
        return f"{subject}_{slug}_{short}"
    if slug and short:
        return f"{slug}_{short}"
    return job_id


def build_job_output_dir(
    data_dir: str | Path,
    job_id: str,
    *,
    parameters: Mapping[str, Any] | None = None,
    input_files: Sequence[str] | None = None,
    plugin_id: str = "",
    pipeline_name: str = "",
    workflow_steps: Sequence[str] | None = None,
) -> Path:
    """Absolute path to a job output directory with a human-readable folder name."""
    folder = build_output_folder_basename(
        job_id,
        parameters=parameters,
        input_files=input_files,
        plugin_id=plugin_id,
        pipeline_name=pipeline_name,
        workflow_steps=workflow_steps,
    )
    return Path(data_dir) / "outputs" / folder


@dataclass(frozen=True)
class JobLabels:
    subject_label: str = ""
    input_label: str = ""
    output_folder: str = ""

    def as_dict(self) -> dict[str, Optional[str]]:
        return {
            "subject_label": self.subject_label or None,
            "input_label": self.input_label or None,
            "output_folder": self.output_folder or None,
        }


def extract_job_labels(job: Any) -> JobLabels:
    """Derive subject/session and input labels from stored job fields."""
    params = job.parameters if isinstance(getattr(job, "parameters", None), dict) else {}
    input_files = getattr(job, "input_files", None)
    if not isinstance(input_files, list):
        input_files = []

    subject_id, session_id = _parse_subject_session(params, input_files)

    subject_label = ""
    if subject_id:
        subject_label = _normalize_sub_id(subject_id)
        if session_id:
            subject_label = f"{subject_label} · {_normalize_ses_id(session_id)}"

    primary_input = str(input_files[0]) if input_files else ""
    input_label = _basename_label(primary_input) if primary_input else ""
    if not subject_label and input_label:
        subject_label = input_label

    output_folder = ""
    if getattr(job, "output_dir", None):
        output_folder = Path(str(job.output_dir)).name
    elif getattr(job, "id", None):
        output_folder = build_output_folder_basename(
            str(job.id),
            parameters=params,
            input_files=input_files,
            pipeline_name=str(getattr(job, "pipeline_name", "") or ""),
        )

    return JobLabels(
        subject_label=subject_label,
        input_label=input_label,
        output_folder=output_folder,
    )


def build_job_label_fields(job: Any) -> dict[str, Optional[str]]:
    return extract_job_labels(job).as_dict()
