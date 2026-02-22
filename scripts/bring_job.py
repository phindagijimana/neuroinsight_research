#!/usr/bin/env python3
"""
NeuroInsight job recovery utility.
Recreates a completed job from existing output files.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from backend.core.config import get_settings
from backend.core.database import SessionLocal
from backend.models.job import Job, JobStatus
from backend.models.metric import Metric
from backend.services.job_service import JobService


def _parse_recon_all_start_time(status_log: Path) -> datetime | None:
    if not status_log.exists():
        return None
    for line in status_log.read_text().splitlines():
        if line.startswith("#@#"):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            timestamp_str = parts[2].strip()
            for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y"):
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
    return None


def _find_uploaded_file(upload_dir: Path, job_id: str) -> tuple[str | None, str | None]:
    if not upload_dir.exists():
        return None, None
    matches = list(upload_dir.glob(f"*{job_id}*"))
    if not matches:
        return None, None
    newest = max(matches, key=lambda p: p.stat().st_mtime)
    return str(newest), newest.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover a completed job by ID.")
    parser.add_argument("job_id", help="Job ID to recover (8 characters).")
    args = parser.parse_args()

    job_id = args.job_id.strip()
    settings = get_settings()
    output_dir = Path(settings.output_dir) / job_id

    if not output_dir.exists():
        print(f"Job {job_id} not found in outputs. Nothing to recover.")
        return

    status_log = (
        output_dir
        / "freesurfer"
        / "freesurfer_docker"
        / f"freesurfer_docker_{job_id}"
        / "scripts"
        / "recon-all-status.log"
    )

    started_at = _parse_recon_all_start_time(status_log)
    completed_at = datetime.fromtimestamp(output_dir.stat().st_mtime)
    if not started_at:
        started_at = completed_at

    upload_dir = Path(settings.upload_dir)
    file_path, filename = _find_uploaded_file(upload_dir, job_id)
    if not filename:
        filename = f"{job_id}.nii.gz"

    # Load patient information if available
    patient_info_file = output_dir / "patient_info.json"
    patient_info = {}
    if patient_info_file.exists():
        try:
            with open(patient_info_file, 'r') as f:
                patient_info = json.load(f)
            print(f"Loaded patient information from {patient_info_file}")
        except Exception as e:
            print(f"Warning: Failed to load patient info: {e}")

    db = SessionLocal()
    try:
        existing = db.query(Job).filter(Job.id == job_id).first()
        if existing:
            print(f"Job {job_id} already exists in the database.")
            return

        job = Job(
            id=job_id,
            filename=filename,
            file_path=file_path,
            status=JobStatus.COMPLETED,
            created_at=started_at or datetime.utcnow(),
            started_at=started_at,
            completed_at=completed_at,
            result_path=str(output_dir),
            progress=100,
            current_step="Processing completed successfully",
            visualizations=json.dumps(JobService.build_visualization_payload(job_id)),
            patient_name=patient_info.get('patient_name'),
            patient_id=patient_info.get('patient_id'),
            patient_age=patient_info.get('patient_age'),
            patient_sex=patient_info.get('patient_sex'),
            scanner_info=patient_info.get('scanner_info'),
            sequence_info=patient_info.get('sequence_info'),
            notes=patient_info.get('notes'),
        )
        db.add(job)
        db.commit()

        metrics_path = output_dir / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            for metric in metrics:
                if metric.get("region") is None:
                    continue
                if metric.get("left_volume") is None or metric.get("right_volume") is None:
                    continue
                if metric.get("asymmetry_index") is None:
                    continue
                exists = db.query(Metric).filter(
                    Metric.job_id == job_id,
                    Metric.region == metric.get("region"),
                ).first()
                if exists:
                    continue
                db.add(
                    Metric(
                        job_id=job_id,
                        region=metric.get("region"),
                        left_volume=metric.get("left_volume"),
                        right_volume=metric.get("right_volume"),
                        asymmetry_index=metric.get("asymmetry_index"),
                    )
                )
            db.commit()

        print(f"Job {job_id} recovered successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

