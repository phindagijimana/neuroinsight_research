#!/usr/bin/env python3
"""
Submit a single plugin job via SLURM backend (SSH → HPC → sbatch).

  export BACKEND_TYPE=slurm
  export HPC_HOST=127.0.0.1
  export HPC_SSH_PORT=2222
  export HPC_USER=pndagiji
  export HPC_WORK_DIR=/path/to/neuroinsight/on/hpc
  export DATA_DIR=./data

  PYTHONPATH=. python3 scripts/submit_plugin_slurm.py \\
    --plugin-id eeg_legacy_to_bids \\
    --input-dir /mnt/nfs/home/.../staging_with_eeg/raw
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plugin-id", required=True, help="Plugin id from plugins/*.yaml")
    ap.add_argument(
        "--input-dir",
        required=True,
        help="Staging directory on HPC (paths must exist on the SSH target)",
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

    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(args.plugin_id)
    if not plugin:
        print(f"ERROR: plugin not found: {args.plugin_id}", file=sys.stderr)
        return 1

    _check_licenses([args.plugin_id])

    rp = plugin.resource_profiles.get("default", {}) if plugin.resource_profiles else {}
    resources = ResourceSpec(
        memory_gb=rp.get("mem_gb", rp.get("memory_gb", 8)),
        cpus=rp.get("cpus", 4),
        time_hours=rp.get("time_hours", 2),
        gpu=bool(rp.get("gpus", 0)),
    )

    job_id = str(uuid.uuid4())
    settings = get_settings()
    output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

    params = _normalize_submission_parameters_for_plugins([args.plugin_id], {})
    params["_plugin_id"] = args.plugin_id

    spec = JobSpec(
        pipeline_name=plugin.name,
        container_image=plugin.container_image,
        input_files=[input_dir],
        output_dir=output_dir,
        parameters=params,
        resources=resources,
        plugin_id=args.plugin_id,
        execution_mode="plugin",
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
