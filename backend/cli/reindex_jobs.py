"""
Re-index jobs from on-disk output directories into the jobs database.

Intended for disaster recovery when DB volumes were reset but job outputs
still exist under data/outputs/<job_id>/.

Usage:
  python3 -m backend.cli.reindex_jobs
  python3 -m backend.cli.reindex_jobs --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.core.database import get_db_context
from backend.core.hpc_config_store import load_hpc_config
from backend.core.ssh_manager import SSHConnectionError, get_ssh_manager
from backend.models.job import Job, JobStatusEnum

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _dt_from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _has_any_files(path: Path) -> bool:
    if not path.exists():
        return False
    for p in path.rglob("*"):
        if p.is_file():
            return True
    return False


def _infer_status(job_dir: Path) -> tuple[str, int | None, str | None]:
    logs_dir = job_dir / "logs"
    log_texts: list[str] = []
    if logs_dir.exists():
        for lf in logs_dir.glob("*.log"):
            try:
                log_texts.append(lf.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
    joined = "\n".join(log_texts)

    if re.search(r"exited with code\s+([1-9]\d*)", joined, flags=re.IGNORECASE):
        return JobStatusEnum.FAILED.value, 1, "Recovered from logs: non-zero exit code"
    if re.search(r"exited with code\s+0", joined, flags=re.IGNORECASE):
        return JobStatusEnum.COMPLETED.value, 0, None

    # Prefer output evidence over generic "ERROR" words in logs.
    if _has_any_files(job_dir / "bundle") or _has_any_files(job_dir / "native"):
        return JobStatusEnum.COMPLETED.value, 0, None

    if re.search(r"\b(ERROR|Traceback)\b", joined):
        return JobStatusEnum.FAILED.value, 1, "Recovered from logs: error signature detected"

    return JobStatusEnum.FAILED.value, 1, "Recovered with unknown terminal state"


def _infer_backend_type(spec: dict[str, Any], input_files: list[str]) -> str:
    joined_inputs = " ".join(input_files).lower()
    if "workflow_id" in spec or "/mnt/nfs/" in joined_inputs:
        return "slurm"
    return "local_docker"


def _recover_or_update_job(
    db,
    *,
    job_id: str,
    spec: dict[str, Any],
    status: str,
    exit_code: int | None,
    error_message: str | None,
    submitted_at: datetime,
    output_dir: str,
    source_label: str,
    dry_run: bool,
    update_existing: bool,
) -> tuple[bool, bool]:
    """
    Returns (created, updated).
    """
    existing = db.query(Job).filter(Job.id == job_id).first()
    input_files = spec.get("input_files") if isinstance(spec.get("input_files"), list) else []
    parameters = spec.get("parameters") if isinstance(spec.get("parameters"), dict) else {}
    resources = spec.get("resources") if isinstance(spec.get("resources"), dict) else {}
    if "execution_mode" in spec and "execution_mode" not in parameters:
        parameters["execution_mode"] = spec.get("execution_mode")
    if "workflow_id" in spec and "_workflow_id" not in parameters:
        parameters["_workflow_id"] = spec.get("workflow_id")

    pipeline_name = str(spec.get("pipeline_name") or "").strip() or "Recovered Job"
    container_image = str(spec.get("container_image") or "").strip() or "unknown/recovered"
    progress = 100 if status == JobStatusEnum.COMPLETED.value else 0
    completed_at = submitted_at if status in (
        JobStatusEnum.COMPLETED.value,
        JobStatusEnum.FAILED.value,
        JobStatusEnum.CANCELLED.value,
    ) else None

    if existing:
        if not update_existing:
            return False, False
        if dry_run:
            print(f"[DRY-RUN] Would update {job_id} ({pipeline_name}) [{status}] from {source_label}")
            return False, True
        existing.backend_type = _infer_backend_type(spec, input_files)
        existing.pipeline_name = pipeline_name
        existing.pipeline_version = str(spec.get("pipeline_version") or "recovered")
        existing.container_image = container_image
        existing.input_files = input_files
        existing.parameters = parameters
        existing.resources = resources
        existing.status = status
        existing.progress = progress
        existing.current_phase = f"Recovered from {source_label}"
        existing.submitted_at = submitted_at
        existing.started_at = submitted_at
        existing.completed_at = completed_at
        existing.output_dir = output_dir
        existing.exit_code = exit_code
        existing.error_message = error_message
        existing.deleted = False
        print(f"[OK] Updated {job_id} ({pipeline_name}) [{status}] from {source_label}")
        return False, True

    if dry_run:
        print(f"[DRY-RUN] Would restore {job_id} ({pipeline_name}) [{status}] from {source_label}")
        return True, False

    db.add(Job(
        id=job_id,
        backend_type=_infer_backend_type(spec, input_files),
        backend_job_id=None,
        pipeline_name=pipeline_name,
        pipeline_version=str(spec.get("pipeline_version") or "recovered"),
        container_image=container_image,
        input_files=input_files,
        parameters=parameters,
        resources=resources,
        status=status,
        progress=progress,
        current_phase=f"Recovered from {source_label}",
        submitted_at=submitted_at,
        started_at=submitted_at,
        completed_at=completed_at,
        output_dir=output_dir,
        exit_code=exit_code,
        error_message=error_message,
        deleted=False,
    ))
    print(f"[OK] Restored {job_id} ({pipeline_name}) [{status}] from {source_label}")
    return True, False


def _connect_hpc_if_configured():
    cfg = load_hpc_config()
    if not cfg:
        return None, None, None
    ssh = get_ssh_manager()
    try:
        if not ssh.is_connected:
            ssh.configure(
                host=cfg["ssh_host"],
                username=cfg["ssh_user"],
                port=int(cfg.get("ssh_port", 22)),
            )
            ssh.connect()
        code, out, _ = ssh.execute(f'eval echo "{cfg.get("work_dir", "~")}"', timeout=20)
        work_dir = out.strip() if code == 0 and out.strip().startswith("/") else str(cfg.get("work_dir", "~"))
        return cfg, ssh, work_dir
    except SSHConnectionError as e:
        print(f"[WARN] Could not connect to HPC for recovery: {e}")
        return cfg, None, None


def _remote_read_json(ssh, path: str) -> dict[str, Any]:
    code, out, _ = ssh.execute(f'cat "{path}" 2>/dev/null', timeout=20)
    if code != 0 or not out.strip():
        return {}
    try:
        return json.loads(out)
    except Exception:
        return {}


def _infer_status_remote(ssh, job_dir: str, output_dir: str) -> tuple[str, int | None, str | None]:
    # Prefer explicit SLURM success/failure markers when available.
    code, slurm_log, _ = ssh.execute(
        f'ls "{job_dir}"/logs/slurm-*.out 2>/dev/null | head -1',
        timeout=20,
    )
    if code == 0 and slurm_log.strip():
        slurm_log = slurm_log.strip().splitlines()[0]
        _, tail_text, _ = ssh.execute(f'tail -n 200 "{slurm_log}" 2>/dev/null', timeout=25)
        if re.search(r"(completed successfully|exited with code 0)", tail_text, flags=re.IGNORECASE):
            return JobStatusEnum.COMPLETED.value, 0, None
        if re.search(r"(exited with code\s+[1-9]\d*|Traceback)", tail_text, flags=re.IGNORECASE):
            return JobStatusEnum.FAILED.value, 1, "Recovered from SLURM log failure markers"

    # If outputs are present, classify as completed.
    code2, out2, _ = ssh.execute(
        f'find "{output_dir}/bundle" "{output_dir}/native" -type f 2>/dev/null | head -1',
        timeout=20,
    )
    if code2 == 0 and out2.strip():
        return JobStatusEnum.COMPLETED.value, 0, None

    return JobStatusEnum.FAILED.value, 1, "Recovered with unknown terminal state"


def reindex_jobs(
    dry_run: bool = False,
    include_hpc: bool = True,
    update_existing: bool = False,
) -> dict[str, int]:
    settings = get_settings()
    outputs_root = Path(settings.output_dir).resolve()

    created = 0
    updated = 0
    skipped_existing = 0
    found_local_dirs = 0
    found_remote_dirs = 0
    invalid_dirs = 0

    with get_db_context() as db:
        # Local outputs recovery.
        if outputs_root.exists():
            for d in sorted(outputs_root.iterdir()):
                if not d.is_dir():
                    continue
                if not UUID_RE.match(d.name):
                    invalid_dirs += 1
                    continue
                found_local_dirs += 1

                exists = db.query(Job).filter(Job.id == d.name).first()
                if exists and not update_existing:
                    skipped_existing += 1
                    continue

                spec = _read_json(d / "job_spec.json")
                status, exit_code, error_message = _infer_status(d)
                ts = d.stat().st_mtime
                submitted_at = _dt_from_ts(ts)

                did_create, did_update = _recover_or_update_job(
                    db,
                    job_id=d.name,
                    spec=spec,
                    status=status,
                    exit_code=exit_code,
                    error_message=error_message,
                    submitted_at=submitted_at,
                    output_dir=str(d),
                    source_label="local outputs",
                    dry_run=dry_run,
                    update_existing=update_existing,
                )
                created += int(did_create)
                updated += int(did_update)
        else:
            print(f"[WARN] Local outputs directory not found: {outputs_root}")

        # Optional HPC outputs recovery.
        if include_hpc:
            _, ssh, work_dir = _connect_hpc_if_configured()
            if ssh and work_dir:
                code, out, _ = ssh.execute(
                    f'find "{work_dir}/neuroinsight/jobs" -mindepth 1 -maxdepth 1 -type d 2>/dev/null',
                    timeout=45,
                )
                if code == 0 and out.strip():
                    for job_dir in [ln.strip() for ln in out.splitlines() if ln.strip()]:
                        job_id = Path(job_dir).name
                        if not UUID_RE.match(job_id):
                            continue
                        found_remote_dirs += 1
                        output_dir = f"{job_dir}/outputs"
                        spec = _remote_read_json(ssh, f"{job_dir}/scripts/job_spec.json")
                        try:
                            status, exit_code, error_message = _infer_status_remote(ssh, job_dir, output_dir)
                        except Exception as e:
                            # Best-effort reconnect once, then continue scan.
                            print(f"[WARN] HPC probe failed for {job_id}: {e}. Retrying once...")
                            _, ssh_retry, _ = _connect_hpc_if_configured()
                            if not ssh_retry:
                                print(f"[WARN] Could not reconnect SSH for {job_id}; skipping.")
                                continue
                            ssh = ssh_retry
                            try:
                                status, exit_code, error_message = _infer_status_remote(ssh, job_dir, output_dir)
                            except Exception as e2:
                                print(f"[WARN] Skipping {job_id} after retry failure: {e2}")
                                continue

                        # Remote mtime as submitted_at fallback.
                        c2, o2, _ = ssh.execute(f'stat -c %Y "{job_dir}" 2>/dev/null', timeout=15)
                        try:
                            ts = float(o2.strip()) if c2 == 0 and o2.strip() else datetime.utcnow().timestamp()
                        except Exception:
                            ts = datetime.utcnow().timestamp()
                        submitted_at = _dt_from_ts(ts)

                        exists = db.query(Job).filter(Job.id == job_id).first()
                        if exists and not update_existing:
                            skipped_existing += 1
                            continue

                        did_create, did_update = _recover_or_update_job(
                            db,
                            job_id=job_id,
                            spec=spec,
                            status=status,
                            exit_code=exit_code,
                            error_message=error_message,
                            submitted_at=submitted_at,
                            output_dir=output_dir,
                            source_label="HPC outputs",
                            dry_run=dry_run,
                            update_existing=update_existing,
                        )
                        created += int(did_create)
                        updated += int(did_update)

        if not dry_run:
            db.commit()

    return {
        "found_local_dirs": found_local_dirs,
        "found_remote_dirs": found_remote_dirs,
        "created": created,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "invalid_dirs": invalid_dirs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-index jobs from data/outputs back into the DB",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview recovered jobs without writing to DB",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Recover only from local data/outputs (skip HPC scan)",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update already-present recovered jobs with fresh inferred metadata/status",
    )
    args = parser.parse_args()

    stats = reindex_jobs(
        dry_run=args.dry_run,
        include_hpc=not args.local_only,
        update_existing=args.update_existing,
    )
    print(
        "[SUMMARY] "
        f"found_local_dirs={stats['found_local_dirs']} "
        f"found_remote_dirs={stats['found_remote_dirs']} "
        f"created={stats['created']} "
        f"updated={stats['updated']} "
        f"skipped_existing={stats['skipped_existing']} "
        f"invalid_dirs={stats['invalid_dirs']}"
    )


if __name__ == "__main__":
    main()

