#!/usr/bin/env python3
"""
Submit multimodal_epilepsy_biomarker via SLURM backend (SSH → HPC → sbatch).

Run from the repository root with the same env vars as the NIR server for HPC, e.g.:

  export BACKEND_TYPE=slurm
  export HPC_HOST=127.0.0.1
  export HPC_SSH_PORT=2222
  export HPC_USER=pndagiji
  export HPC_WORK_DIR='~/neuroinsight'
  export DATA_DIR=/path/to/local/data

  PYTHONPATH=. python3 scripts/submit_multimodal_slurm.py \\
    --input-dir /mnt/nfs/home/.../multimodal_sub-111220772

Paths in --input-dir must exist on the HPC host (the SSH target).
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

# Repo root = parent of scripts/
REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--input-dir",
        required=True,
        help="Staging directory on HPC (eeg/raw/ + T1w.nii.gz)",
    )
    args = ap.parse_args()
    input_dir = os.path.normpath(args.input_dir)

    os.environ.setdefault("DATA_DIR", str(REPO / "data"))
    os.makedirs(os.environ["DATA_DIR"], exist_ok=True)

    from backend.core.config import get_settings
    from backend.core.execution import JobSpec, ResourceSpec
    from backend.core.plugin_registry import get_plugin_workflow_registry
    from backend.execution import create_backend
    from backend.main import _check_licenses, _normalize_submission_parameters_for_plugins
    from backend.validation.workflow_staging import validate_multimodal_epilepsy_biomarker_inputs

    validate_multimodal_epilepsy_biomarker_inputs([input_dir])

    pw_registry = get_plugin_workflow_registry()
    workflow_id = "multimodal_epilepsy_biomarker"
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        print("ERROR: workflow not found", file=sys.stderr)
        return 1

    step_plugin_ids = [step.uses for step in workflow.steps]
    _check_licenses(step_plugin_ids)

    first_plugin = pw_registry.get_plugin(workflow.steps[0].uses)
    total_time = 0
    max_mem = 8
    max_cpus = 4
    any_gpu = False
    for step in workflow.steps:
        sp = pw_registry.get_plugin(step.uses)
        if sp and sp.resource_profiles:
            rp = sp.resource_profiles.get("default", {})
            total_time += rp.get("time_hours", 0)
            max_mem = max(max_mem, rp.get("mem_gb", 0))
            max_cpus = max(max_cpus, rp.get("cpus", 0))
            any_gpu = any_gpu or rp.get("gpus", 0) > 0
    if total_time == 0:
        total_time = 6

    resources = ResourceSpec(
        memory_gb=max_mem,
        cpus=max_cpus,
        time_hours=total_time,
        gpu=any_gpu,
    )

    job_id = str(uuid.uuid4())
    settings = get_settings()
    output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

    params = _normalize_submission_parameters_for_plugins(
        step_plugin_ids,
        {
            "eeg_raw_path": "eeg/raw",
            "subject_id": "subject",
            "threads": 8,
        },
    )
    params["_workflow_steps"] = step_plugin_ids
    params["_workflow_id"] = workflow_id

    spec = JobSpec(
        pipeline_name=workflow.name,
        container_image=first_plugin.container_image,
        input_files=[input_dir],
        output_dir=output_dir,
        parameters=params,
        resources=resources,
        workflow_id=workflow_id,
        execution_mode="workflow",
    )

    backend = create_backend()
    if getattr(backend, "backend_type", None) != "slurm":
        print(
            "ERROR: BACKEND_TYPE must be 'slurm' (got %r). "
            "Set HPC_HOST, HPC_USER, HPC_SSH_PORT, HPC_WORK_DIR."
            % os.getenv("BACKEND_TYPE", "local"),
            file=sys.stderr,
        )
        return 1

    try:
        backend.submit_job(spec, job_id=job_id)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(job_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
