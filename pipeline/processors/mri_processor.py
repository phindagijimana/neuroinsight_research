"""
MRI Processor for hippocampal analysis pipeline.

This module orchestrates the complete MRI processing workflow,
from DICOM conversion through hippocampal asymmetry calculation.
"""

import json
import threading
import time
import os
import json
from datetime import datetime
import platform
import re
import shutil
import subprocess as subprocess_module
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

import nibabel as nib
import numpy as np
import pandas as pd
import requests

from backend.core.config import get_settings
from backend.core.logging import get_logger
from pipeline.utils import asymmetry, file_utils, segmentation, visualization

logger = get_logger(__name__)
settings = get_settings()

# FreeSurfer fallback constants - use traditional FreeSurfer with recon-all support
FREESURFER_CONTAINER_IMAGE = "freesurfer/freesurfer:7.4.1"  # Use traditional FreeSurfer for recon-all compatibility
FREESURFER_CONTAINER_SIZE_GB = 20  # Updated for freesurfer/freesurfer:7.4.1
FREESURFER_PROCESSING_TIMEOUT_MINUTES = 420  # Extended for primary FreeSurfer usage (7 hours)
FREESURFER_DOWNLOAD_TIMEOUT_MINUTES = 20

# FreeSurfer Singularity constants (if available)
FREESURFER_SINGULARITY_IMAGE = None  # Will be determined dynamically
FREESURFER_SINGULARITY_SIZE_GB = 4

# FreeSurfer Native support removed - only container methods supported


class DockerNotAvailableError(Exception):
    """User-friendly exception when Docker is not available."""
    
    def __init__(self, error_type="not_installed"):
        self.error_type = error_type
        
        messages = {
            "not_installed": {
                "title": "Docker Desktop Not Installed",
                "message": "NeuroInsight requires Docker Desktop to process MRI scans.",
                "instructions": [
                    "1. Download Docker Desktop:",
                    "   • Windows/Mac: https://www.docker.com/get-started",
                    "   • Linux: https://docs.docker.com/engine/install/",
                    "",
                    "2. Install Docker Desktop (takes 10-15 minutes)",
                    "",
                    "3. Launch Docker Desktop and wait for the whale icon",
                    "",
                    "4. Return to NeuroInsight and try processing again"
                ],
                "why": "Docker is needed to run FreeSurfer, the brain segmentation tool."
            },
            "not_running": {
                "title": "Docker Desktop Not Running",
                "message": "Docker Desktop is installed but not currently running.",
                "instructions": [
                    "1. Open Docker Desktop from your Applications folder",
                    "",
                    "2. Wait for the whale icon to appear in your system tray:",
                    "   • macOS: Top menu bar",
                    "   • Windows: System tray (bottom right)",
                    "   • Linux: System tray",
                    "",
                    "3. The icon should be steady (not animating)",
                    "",
                    "4. Return to NeuroInsight and try processing again"
                ],
                "why": "Docker must be running to process MRI scans."
            },
            "image_not_found": {
                "title": "Downloading Brain Segmentation Model",
                "message": "First-time setup: Downloading FreeSurfer (~4GB).",
                "instructions": [
                    "This download happens only once and takes 10-15 minutes.",
                    "",
                    "The model will be cached for future use.",
                    "",
                    "Please keep Docker Desktop running and wait..."
                ],
                "why": "NeuroInsight needs to download the brain segmentation AI model."
            }
        }
        
        error_info = messages.get(error_type, messages["not_installed"])
        
        # Format the error message
        full_message = f"\n{'='*60}\n"
        full_message += f"{error_info['title']}\n"
        full_message += f"{'='*60}\n\n"
        full_message += f"{error_info['message']}\n\n"
        full_message += "What to do:\n"
        full_message += "\n".join(error_info['instructions'])
        full_message += f"\n\nWhy: {error_info['why']}\n"
        full_message += f"{'='*60}\n"
        
        super().__init__(full_message)
        self.title = error_info['title']
        self.user_message = error_info['message']
        self.instructions = error_info['instructions']


        self.title = error_info['title']
        self.user_message = error_info['message']
        self.instructions = error_info['instructions']



class MRIProcessor:
    """
    Main processor for MRI hippocampal analysis.

    Orchestrates the complete pipeline:
    1. File format validation/conversion
    2. FreeSurfer segmentation
    3. Hippocampal subfield extraction
    4. Volumetric analysis
    5. Asymmetry index calculation
    """
    
    def __init__(self, job_id: UUID, progress_callback=None, db_session=None):
        """
        Initialize MRI processor.

        Args:
            job_id: Unique job identifier
            progress_callback: Optional callback function(progress: int, step: str) for progress updates
            db_session: Optional database session for progress persistence
            
        Note:
            __init__ must be fast and non-blocking (<10ms).
            Patient info is saved during process() after initialization.
        """
        self.job_id = job_id
        self.db_session = db_session
        self.app_dir = Path(__file__).parent.parent.parent.absolute()  # Path to project root
        self.output_dir = Path(settings.output_dir) / str(job_id)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.process_pid = None  # Track subprocess PID for cleanup
        self.progress_callback = progress_callback

        # Check if smoke test mode is enabled (for CI/testing)
        self.smoke_test_mode = os.getenv("FASTSURFER_SMOKE_TEST") == "1"

        # Track if mock data was used during processing
        self.mock_processing = False

        # Initialize progress tracking
        self._current_progress = 0

        logger.info(
            "processor_initialized",
            job_id=str(job_id)
        )

    def _get_current_progress(self) -> int:
        """
        Get current processing progress percentage.

        Returns:
            Current progress as integer percentage (0-100)
        """
        return getattr(self, '_current_progress', 0)

    def _save_patient_info(self):
        """
        Save patient information to filesystem for recovery.
        
        This method queries the database to retrieve patient metadata
        and saves it to a JSON file in the job's output directory.
        
        This ensures patient data survives database resets and can be
        recovered by the bring command.
        
        Note:
            This is called at the START of process(), not in __init__,
            to avoid blocking the constructor with database queries (Fix #2).
        """
        import json
        
        if not self.db_session:
            logger.debug("no_db_session_skipping_patient_info_save",
                        job_id=str(self.job_id))
            return
        
        try:
            from backend.models.job import Job
            
            # Query with timeout (Fix #4)
            # If this hangs, we fail fast rather than blocking forever
            try:
                # Note: SQLAlchemy execution_options timeout support varies by driver
                # For PostgreSQL with psycopg2, statement timeout is better set at connection level
                # This is a best-effort approach
                job = self.db_session.query(Job).filter(
                    Job.id == self.job_id
                ).first()
                
                if not job:
                    logger.warning("job_not_found_for_patient_info",
                                  job_id=str(self.job_id))
                    return
                    
            except Exception as query_error:
                logger.warning("patient_info_query_failed",
                              job_id=str(self.job_id),
                              error=str(query_error),
                              message="Failed to query job for patient info - continuing without it")
                return
            
            # Collect patient information (DO NOT log patient data - Fix #6 privacy)
            patient_info = {
                'patient_name': job.patient_name,
                'patient_id': job.patient_id,
                'patient_age': job.patient_age,
                'patient_sex': job.patient_sex,
                'scanner_info': job.scanner_info,
                'sequence_info': job.sequence_info,
                'notes': job.notes
            }
            
            # Only save if there's at least one non-null field
            if any(v is not None for v in patient_info.values()):
                patient_info_file = self.output_dir / "patient_info.json"
                
                # Write with explicit error handling
                try:
                    with open(patient_info_file, 'w') as f:
                        json.dump(patient_info, f, indent=2)
                    
                    logger.info("patient_info_saved", 
                               job_id=str(self.job_id),
                               file=str(patient_info_file),
                               has_data=True)
                except IOError as io_error:
                    logger.warning("failed_to_write_patient_info_file",
                                  job_id=str(self.job_id),
                                  error=str(io_error))
            else:
                logger.debug("no_patient_info_to_save",
                            job_id=str(self.job_id))
            
        except Exception as e:
            # Don't fail the job if patient info save fails
            # This is a best-effort operation for recovery purposes
            logger.warning("failed_to_save_patient_info", 
                          job_id=str(self.job_id), 
                          error=str(e))

    def _get_freesurfer_thread_count(self) -> int:
        """
        Get a safe thread count for FreeSurfer inside Docker.

        Use a fixed thread count for predictable parallelization.
        """
        return 5

    def _get_freesurfer_thread_env(self, flag: str = "-e") -> list:
        """
        Build Docker env args for FreeSurfer threading/OpenMP.

        These apply globally inside the container; steps that support OpenMP
        will use them (e.g., CA Reg, SubCort Seg, Skull Stripping).
        """
        threads = self._get_freesurfer_thread_count()
        return [
            flag, f"OMP_NUM_THREADS={threads}",
            flag, f"ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS={threads}",
            flag, "FS_THREADED=1",
            flag, "OMP_DYNAMIC=FALSE",
            flag, "OMP_PROC_BIND=TRUE",
            flag, "OMP_PLACES=cores",
        ]

    def _capture_container_failure_artifacts(self, container_name: str, subject_output_dir: Path) -> None:
        """
        Capture deterministic Docker/container/host diagnostics for post-failure analysis.
        """
        try:
            artifacts_dir = self._get_failure_artifacts_dir(subject_output_dir)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

            def _write_command_output(filename: str, command: list, timeout: int = 10) -> tuple[str | None, str | None]:
                result_path = artifacts_dir / filename
                try:
                    result = subprocess_module.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    content = [
                        f"command: {' '.join(command)}",
                        f"returncode: {result.returncode}",
                        "stdout:",
                        result.stdout or "",
                        "stderr:",
                        result.stderr or "",
                    ]
                    result_path.write_text("\n".join(content).strip() + "\n")
                    return result.stdout, result.stderr
                except Exception as inner_exc:
                    result_path.write_text(f"command: {' '.join(command)}\nerror: {inner_exc}\n")
                    return None, None

            inspect_stdout, _ = _write_command_output(
                f"docker-inspect-{container_name}-{timestamp}.json",
                ["docker", "inspect", container_name],
                timeout=10,
            )
            _write_command_output(
                f"docker-logs-{container_name}-{timestamp}.log",
                ["docker", "logs", container_name],
                timeout=10,
            )
            _write_command_output(
                f"docker-state-{container_name}-{timestamp}.txt",
                ["docker", "inspect", "--format", "{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}} {{.State.Error}} {{.State.FinishedAt}}", container_name],
                timeout=5,
            )
            _write_command_output(
                f"docker-stats-{container_name}-{timestamp}.txt",
                ["docker", "stats", "--no-stream", container_name],
                timeout=5,
            )
            _write_command_output(
                f"docker-top-{container_name}-{timestamp}.txt",
                ["docker", "top", container_name, "-eo", "pid,ppid,cmd,%mem,%cpu"],
                timeout=5,
            )

            # Host diagnostics snapshot
            _write_command_output(
                f"host-free-{timestamp}.txt",
                ["free", "-m"],
                timeout=5,
            )
            _write_command_output(
                f"host-vmstat-{timestamp}.txt",
                ["vmstat", "1", "1"],
                timeout=5,
            )
            _write_command_output(
                f"host-uptime-{timestamp}.txt",
                ["uptime"],
                timeout=5,
            )
            _write_command_output(
                f"host-df-{timestamp}.txt",
                ["df", "-h"],
                timeout=10,
            )
            _write_command_output(
                f"host-docker-info-{timestamp}.txt",
                ["docker", "info"],
                timeout=10,
            )
            _write_command_output(
                f"host-kernel-oom-{timestamp}.txt",
                ["journalctl", "-k", "--no-pager", "-n", "200"],
                timeout=10,
            )

            # Capture docker events for the container lifecycle (best effort).
            try:
                if inspect_stdout:
                    import json

                    inspect_payload = json.loads(inspect_stdout)
                    if inspect_payload and isinstance(inspect_payload, list):
                        state = inspect_payload[0].get("State", {})
                        started_at = state.get("StartedAt")
                        finished_at = state.get("FinishedAt") or datetime.utcnow().isoformat() + "Z"
                        if started_at:
                            _write_command_output(
                                f"docker-events-{container_name}-{timestamp}.log",
                                [
                                    "docker", "events",
                                    "--since", started_at,
                                    "--until", finished_at,
                                    "--filter", f"container={container_name}",
                                ],
                                timeout=10,
                            )
            except Exception as events_exc:
                (artifacts_dir / f"docker-events-{container_name}-{timestamp}.log").write_text(
                    f"error capturing docker events: {events_exc}\n"
                )

            # Capture /proc snapshots for container process (best effort)
            container_pid = None
            if inspect_stdout:
                try:
                    import json

                    inspect_payload = json.loads(inspect_stdout)
                    if inspect_payload and isinstance(inspect_payload, list):
                        container_pid = inspect_payload[0].get("State", {}).get("Pid")
                except Exception:
                    container_pid = None

            if container_pid:
                for proc_file, suffix in [
                    ("status", "status"),
                    ("limits", "limits"),
                    ("cgroup", "cgroup"),
                    ("cmdline", "cmdline"),
                ]:
                    proc_path = Path(f"/proc/{container_pid}/{proc_file}")
                    if proc_path.exists():
                        try:
                            content = proc_path.read_text()
                            (artifacts_dir / f"container-proc-{suffix}-{container_name}-{timestamp}.txt").write_text(content)
                        except Exception as proc_exc:
                            (artifacts_dir / f"container-proc-{suffix}-{container_name}-{timestamp}.txt").write_text(
                                f"error reading {proc_path}: {proc_exc}\n"
                            )

                # cgroup v2 memory metrics if available
                cgroup_path = Path(f"/proc/{container_pid}/cgroup")
                try:
                    if cgroup_path.exists():
                        cgroup_lines = cgroup_path.read_text().splitlines()
                        unified = next((line.split("::")[-1] for line in cgroup_lines if "::" in line), None)
                        if unified:
                            cgroup_dir = Path("/sys/fs/cgroup") / unified.lstrip("/")
                            for metric in ["memory.current", "memory.max", "memory.events"]:
                                metric_path = cgroup_dir / metric
                                if metric_path.exists():
                                    (artifacts_dir / f"container-cgroup-{metric}-{container_name}-{timestamp}.txt").write_text(
                                        metric_path.read_text()
                                    )
                except Exception as cgroup_exc:
                    (artifacts_dir / f"container-cgroup-error-{container_name}-{timestamp}.txt").write_text(
                        f"error reading cgroup metrics: {cgroup_exc}\n"
                    )

            # Lightweight failure context
            try:
                context_path = artifacts_dir / f"failure-context-{container_name}-{timestamp}.json"
                context_path.write_text(
                    json.dumps(
                        {
                            "timestamp": timestamp,
                            "job_id": str(self.job_id),
                            "container_name": container_name,
                            "threads": self._get_freesurfer_thread_count(),
                            "output_dir": str(subject_output_dir),
                        },
                        indent=2,
                    )
                    + "\n"
                )
            except Exception as context_exc:
                (artifacts_dir / f"failure-context-{container_name}-{timestamp}.txt").write_text(
                    f"failed to write context: {context_exc}\n"
                )

            # Snapshot monitoring logs for postmortem analysis.
            try:
                project_root = Path(__file__).resolve().parents[2]
                for log_name in ["job_monitor.log", "dev_job_monitor.log", "neuroinsight.log", "celery_worker.log"]:
                    log_path = project_root / log_name
                    if log_path.exists():
                        (artifacts_dir / f"{log_name}-{timestamp}").write_text(
                            log_path.read_text()
                        )
            except Exception as log_exc:
                (artifacts_dir / f"log-snapshot-error-{container_name}-{timestamp}.txt").write_text(
                    f"error capturing monitor logs: {log_exc}\n"
                )

            logger.info(
                "docker_failure_artifacts_captured",
                container=container_name,
                artifacts_dir=str(artifacts_dir),
            )
        except Exception as exc:
            logger.warning("docker_failure_artifacts_capture_failed", container=container_name, error=str(exc))

    def _write_docker_failure_output(
        self,
        subject_output_dir: Path,
        container_name: str,
        stdout_output: str,
        stderr_output: str,
    ) -> None:
        """Persist docker run stdout/stderr for failure diagnostics."""
        try:
            artifacts_dir = self._get_failure_artifacts_dir(subject_output_dir)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            stdout_path = artifacts_dir / f"docker-run-stdout-{container_name}-{timestamp}.log"
            stderr_path = artifacts_dir / f"docker-run-stderr-{container_name}-{timestamp}.log"
            if stdout_output:
                stdout_path.write_text(stdout_output)
            if stderr_output:
                stderr_path.write_text(stderr_output)
        except Exception as exc:
            logger.warning("docker_failure_output_capture_failed", container=container_name, error=str(exc))

    def _get_failure_artifacts_dir(self, subject_output_dir: Path) -> Path:
        """
        Determine a writable directory for failure artifacts.

        Prefer the job output root to avoid root-owned FreeSurfer subdirs.
        """
        # outputs/<job_id> is two levels up from the subject dir
        job_root = subject_output_dir
        if len(subject_output_dir.parents) > 2:
            job_root = subject_output_dir.parents[2]

        artifacts_dir = job_root / "diagnostics"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Best-effort permission fix for root-owned outputs
        chmod_result = subprocess_module.run(
            ["chmod", "-R", "777", str(artifacts_dir)],
            capture_output=True,
            timeout=15,
        )
        if chmod_result.returncode != 0:
            logger.warning(
                "failed_to_chmod_artifacts_dir",
                path=str(artifacts_dir),
                stderr=(chmod_result.stderr or "").strip(),
            )

        return artifacts_dir

    def _capture_memory_snapshot(self, subject_output_dir: Path, label: str) -> None:
        """
        Capture a one-time snapshot of top memory users on the host.
        """
        try:
            artifacts_dir = self._get_failure_artifacts_dir(subject_output_dir)
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            snapshot_path = artifacts_dir / f"memory-snapshot-{label}-{timestamp}.log"

            commands = [
                ["ps", "-eo", "pid,ppid,%mem,%cpu,rss,cmd", "--sort=-%mem"],
                ["free", "-m"],
                ["vmstat", "1", "1"],
                ["docker", "stats", "--no-stream"],
            ]

            output_lines = []
            for cmd in commands:
                try:
                    result = subprocess_module.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    output_lines.append(f"command: {' '.join(cmd)}")
                    output_lines.append(f"returncode: {result.returncode}")
                    if result.stdout:
                        # Trim ps output to top 30 rows to keep files manageable
                        if cmd[:2] == ["ps", "-eo"]:
                            stdout_lines = result.stdout.strip().splitlines()
                            output_lines.extend(stdout_lines[:31])
                        else:
                            output_lines.append(result.stdout.strip())
                    if result.stderr:
                        output_lines.append("stderr:")
                        output_lines.append(result.stderr.strip())
                    output_lines.append("")
                except Exception as cmd_exc:
                    output_lines.append(f"command: {' '.join(cmd)}")
                    output_lines.append(f"error: {cmd_exc}")
                    output_lines.append("")

            snapshot_path.write_text("\n".join(output_lines).strip() + "\n")
        except Exception as exc:
            logger.warning("memory_snapshot_capture_failed", error=str(exc), label=label)

    def _start_resource_sampling(
        self,
        container_name: str,
        subject_output_dir: Path,
        interval_seconds: int = 30,
    ) -> tuple[threading.Event, threading.Thread]:
        """
        Periodically sample container/host resources while a job runs.
        """
        artifacts_dir = self._get_failure_artifacts_dir(subject_output_dir)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        sample_path = artifacts_dir / f"resource-samples-{container_name}-{timestamp}.log"

        stop_event = threading.Event()

        def _sampler():
            cgroup_dir = None
            while not stop_event.is_set():
                now = datetime.utcnow().isoformat() + "Z"
                docker_stats_cmd = [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.MemUsage}} {{.MemPerc}} {{.CPUPerc}} {{.PIDs}}",
                    container_name,
                ]
                try:
                    stats_result = subprocess_module.run(
                        docker_stats_cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    stats_line = stats_result.stdout.strip() if stats_result.stdout else ""
                except Exception as exc:
                    stats_line = f"error: {exc}"

                cgroup_metrics = ""
                try:
                    if cgroup_dir is None:
                        pid_result = subprocess_module.run(
                            ["docker", "inspect", "--format", "{{.State.Pid}}", container_name],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if pid_result.returncode == 0:
                            pid_value = pid_result.stdout.strip()
                            if pid_value.isdigit() and int(pid_value) > 0:
                                cgroup_path = Path(f"/proc/{pid_value}/cgroup")
                                if cgroup_path.exists():
                                    cgroup_lines = cgroup_path.read_text().splitlines()
                                    unified = next((line.split("::")[-1] for line in cgroup_lines if "::" in line), None)
                                    if unified:
                                        cgroup_dir = Path("/sys/fs/cgroup") / unified.lstrip("/")

                    if cgroup_dir and cgroup_dir.exists():
                        events_path = cgroup_dir / "memory.events"
                        current_path = cgroup_dir / "memory.current"
                        max_path = cgroup_dir / "memory.max"
                        events_value = events_path.read_text().strip() if events_path.exists() else ""
                        current_value = current_path.read_text().strip() if current_path.exists() else ""
                        max_value = max_path.read_text().strip() if max_path.exists() else ""
                        cgroup_metrics = f" cgroup_current={current_value} cgroup_max={max_value} cgroup_events={events_value.replace(chr(10), ';')}"
                except Exception:
                    cgroup_metrics = ""

                try:
                    free_result = subprocess_module.run(
                        ["free", "-m"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    free_line = free_result.stdout.strip().replace("\n", " | ")
                except Exception as exc:
                    free_line = f"error: {exc}"

                try:
                    with sample_path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            f"{now} interval={interval_seconds}s docker_stats={stats_line}{cgroup_metrics} host_free={free_line}\n"
                        )
                except Exception:
                    pass

                stop_event.wait(interval_seconds)

        thread = threading.Thread(target=_sampler, daemon=True)
        thread.start()
        return stop_event, thread

    def _restart_resource_sampling(
        self,
        container_name: str,
        subject_output_dir: Path,
        interval_seconds: int,
    ) -> None:
        """
        Restart resource sampling at a new interval.
        """
        stop_event = getattr(self, "_resource_sampler_stop_event", None)
        thread = getattr(self, "_resource_sampler_thread", None)
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=2)

        new_stop, new_thread = self._start_resource_sampling(
            container_name,
            subject_output_dir,
            interval_seconds=interval_seconds,
        )
        self._resource_sampler_stop_event = new_stop
        self._resource_sampler_thread = new_thread

    def _cleanup_named_container(self, container_name: str) -> None:
        """Best-effort stop for a named Docker container."""
        try:
            subprocess_module.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            logger.warning("docker_container_cleanup_failed", container=container_name, error=str(exc))

    def _update_progress(self, progress: int, step: str):
        """
        Update current progress and notify callback if available.
        Also persist progress to database in worker context.

        Args:
            progress: Progress percentage (0-100)
            step: Current processing step description
        """
        # Cap progress at 100% for storage and callbacks
        capped_progress = min(progress, 100)
        self._current_progress = capped_progress

        # Update database if we're in a worker context (has db_session)
        if hasattr(self, 'db_session') and self.db_session:
            try:
                from workers.tasks.processing_web import update_job_progress
                update_job_progress(self.db_session, self.job_id, capped_progress, step)
            except Exception as e:
                logger.warning("failed_to_update_job_progress_in_db", error=str(e), progress=progress, step=step)

        # Notify callback if available (for Celery task state)
        if self.progress_callback:
            self.progress_callback(capped_progress, step)

    def _store_container_id(self, container_id: str):
        """
        Store Docker container ID in database for cancellation support.
        
        Args:
            container_id: Docker container ID or name
        """
        if hasattr(self, 'db_session') and self.db_session:
            try:
                from sqlalchemy import update
                from backend.models.job import Job
                
                self.db_session.execute(
                    update(Job)
                    .where(Job.id == str(self.job_id))
                    .values(docker_container_id=container_id)
                )
                self.db_session.commit()
                logger.info("stored_container_id", job_id=str(self.job_id), container_id=container_id)
            except Exception as e:
                logger.warning("failed_to_store_container_id", error=str(e), container_id=container_id)
                self.db_session.rollback()

    def _validate_visualizations(self, visualization_paths: Dict) -> None:
        """
        Validate that visualization files were actually generated.
        
        This ensures that the job doesn't complete successfully if visualizations
        are missing, which would cause issues in the UI and PDF reports.
        
        Args:
            visualization_paths: Dictionary containing paths to visualization files
            
        Raises:
            RuntimeError: If required visualization files are missing
        """
        if not visualization_paths:
            logger.warning("no_visualization_paths_returned", job_id=str(self.job_id))
            return
        
        # Check for overlay PNG files (the most common visualization type)
        overlays = visualization_paths.get("overlays", {})
        if not overlays:
            logger.warning("no_overlays_in_visualization_paths", 
                          job_id=str(self.job_id),
                          viz_paths=visualization_paths)
            return
        
        # Count how many PNG files actually exist
        missing_files = []
        existing_files = []
        
        for orientation, slices in overlays.items():
            if isinstance(slices, dict):
                for slice_name, paths in slices.items():
                    if isinstance(paths, dict):
                        # Each slice has anatomical and overlay paths
                        for path_type, file_path in paths.items():
                            if file_path and isinstance(file_path, str) and Path(file_path).exists():
                                existing_files.append(file_path)
                            elif file_path and isinstance(file_path, str):
                                missing_files.append(file_path)
        
        logger.info("visualization_validation_complete",
                   job_id=str(self.job_id),
                   existing_count=len(existing_files),
                   missing_count=len(missing_files))
        
        # If we expect visualizations but none exist, raise an error
        if len(existing_files) == 0 and len(missing_files) > 0:
            raise RuntimeError(
                f"Visualization generation failed: Expected {len(missing_files)} files but none were created. "
                f"This may indicate a problem with matplotlib or the visualization pipeline."
            )

    def _cleanup_job_containers(self) -> None:
        """
        Stop and remove any Docker containers for this job.
        
        This prevents container name conflicts on subsequent job runs.
        """
        try:
            container_name = f"{settings.freesurfer_container_prefix}{self.job_id}"
            logger.info("cleaning_up_job_containers", job_id=str(self.job_id), container_name=container_name)

            # Stop the container if it's running
            result = subprocess_module.run(
                ["docker", "stop", container_name],
                capture_output=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("stopped_job_container", job_id=str(self.job_id), container_name=container_name)
            else:
                # Container might not be running, which is fine
                logger.debug("container_already_stopped_or_not_found",
                           job_id=str(self.job_id),
                           container_name=container_name,
                           stderr=result.stderr.decode() if result.stderr else "")

            # Remove the container to prevent name conflicts
            rm_result = subprocess_module.run(
                ["docker", "rm", container_name],
                capture_output=True,
                timeout=30
            )

            if rm_result.returncode == 0:
                logger.info("removed_job_container", job_id=str(self.job_id), container_name=container_name)
            else:
                # Container might not exist, which is fine
                logger.debug("container_removal_skipped",
                           job_id=str(self.job_id),
                           container_name=container_name,
                           stderr=rm_result.stderr.decode() if rm_result.stderr else "")

        except subprocess_module.TimeoutExpired:
            logger.warning("container_stop_timeout", job_id=str(self.job_id), container_name=container_name)
        except Exception as e:
            logger.warning("container_cleanup_failed", job_id=str(self.job_id), error=str(e))

    def validate_disk_space(self) -> None:
        """
        Validate that sufficient disk space is available for processing.

        Raises:
            OSError: If disk space is insufficient for processing
        """
        try:
            # Check disk space in the upload directory (where processing happens)
            working_dir = Path(settings.upload_dir).parent
            disk_stats = shutil.disk_usage(working_dir)

            # Available space in GB
            available_gb = disk_stats.free / (1024**3)
            total_gb = disk_stats.total / (1024**3)

            logger.info(
                "disk_space_check",
                available_gb=round(available_gb, 2),
                total_gb=round(total_gb, 2)
            )

            # Require at least 10GB free space for processing
            MIN_REQUIRED_GB = 10.0

            if available_gb < MIN_REQUIRED_GB:
                error_msg = (
                    f"Insufficient disk space for MRI processing.\n"
                    f"Available: {available_gb:.1f} GB\n"
                    f"Required: {MIN_REQUIRED_GB:.1f} GB minimum\n\n"
                    f"Processing MRI scans requires temporary storage for:\n"
                    f"• Docker container images (~4GB)\n"
                    f"• Intermediate processing files\n"
                    f"• Output visualizations and reports\n\n"
                    f"Please free up disk space and try again."
                )
                logger.error(
                    "insufficient_disk_space",
                    available_gb=available_gb,
                    required_gb=MIN_REQUIRED_GB
                )
                raise OSError(error_msg)

            # Warn if space is getting low (less than 20GB)
            if available_gb < 20.0:
                logger.warning(
                    "disk_space_low_warning",
                    available_gb=available_gb,
                    message="Disk space is getting low. Consider freeing up space for better performance."
                )

        except Exception as e:
            logger.warning("disk_space_check_failed", error=str(e))
            # Don't fail processing if we can't check disk space
            # Just log the warning

    def validate_memory(self) -> None:
        """
        Validate that sufficient RAM is available for processing.

        Raises:
            MemoryError: If system memory is insufficient
        """
        try:
            import psutil
        except ImportError:
            logger.warning("psutil_not_available_memory_check_skipped")
            return

        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            total_gb = memory.total / (1024**3)

            logger.info(
                "memory_check",
                available_gb=round(available_gb, 2),
                total_gb=round(total_gb, 2)
            )

            # Memory recommendations for different use cases
            INSTALL_MIN_GB = 7.0    # Allows installation
            PROCESS_MIN_GB = 16.0   # Reliable processing
            RECOMMENDED_GB = 32.0   # Optimal performance

            # Warnings for different memory levels
            if total_gb < PROCESS_MIN_GB:
                warning_msg = (
                    f"  LIMITED MEMORY WARNING\n\n"
                    f"System RAM: {total_gb:.1f} GB\n"
                    f"Recommended for processing: {PROCESS_MIN_GB:.1f} GB+\n\n"
                    f"With {total_gb:.1f} GB RAM, MRI processing may:\n"
                    f"• Fail due to insufficient memory\n"
                    f"• Take significantly longer\n"
                    f"• Cause system slowdowns\n\n"
                    f"For reliable MRI processing, consider upgrading to 16GB+ RAM.\n"
                    f"FreeSurfer segmentation typically requires 4-8GB per brain.\n\n"
                    f"Continuing with processing, but failures are likely..."
                )
                logger.warning(
                    "low_memory_warning",
                    total_gb=total_gb,
                    recommended_gb=PROCESS_MIN_GB,
                    message="Processing may fail due to insufficient RAM"
                )
                print(f"\n{warning_msg}\n")
                # Don't raise error - allow processing attempt but warn heavily

            elif total_gb < RECOMMENDED_GB:
                info_msg = (
                    f"[INFO] MEMORY INFO\n"
                    f"System has {total_gb:.1f} GB RAM - sufficient for basic processing.\n"
                    f"For optimal performance with multiple jobs, consider 32GB+ RAM."
                )
                logger.info(
                    "adequate_memory",
                    total_gb=total_gb,
                    recommended_gb=RECOMMENDED_GB
                )
                print(f"\n{info_msg}\n")

            else:
                logger.info(
                    "optimal_memory",
                    total_gb=total_gb,
                    message="System has optimal RAM for NeuroInsight processing"
                )

            # Warn if memory is getting low
            if available_gb < 4.0:
                logger.warning(
                    "memory_low_warning",
                    available_gb=available_gb,
                    message="Available memory is low. Processing may be slow or fail."
                )

        except Exception as e:
            logger.warning("memory_check_failed", error=str(e))
            # Don't fail processing if we can't check memory
            # Just log the warning

    def validate_network_connectivity(self) -> None:
        """
        Validate network connectivity for Docker image downloads.

        Warns if network issues are detected but doesn't fail processing.
        """
        try:
            import urllib.request
            import socket

            # Set timeout for network checks
            socket.setdefaulttimeout(10)

            # Test connection to Docker Hub
            test_urls = [
                "https://registry-1.docker.io",  # Docker Hub
                "https://hub.docker.com",        # Docker Hub website
            ]

            network_ok = False
            for url in test_urls:
                try:
                    logger.info("testing_network_connectivity", url=url)
                    req = urllib.request.Request(url, method='HEAD')
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status == 200:
                            network_ok = True
                            break
                except Exception as e:
                    logger.debug(f"network_test_failed_for_{url}", error=str(e))
                    continue

            if not network_ok:
                logger.warning(
                    "network_connectivity_issues",
                    message="Unable to reach Docker Hub. Image downloads may fail or be slow.",
                    suggestion="Check your internet connection and firewall settings."
                )
            else:
                logger.info("network_connectivity_ok")

        except Exception as e:
            logger.warning("network_check_failed", error=str(e))
            # Don't fail processing if we can't check network

    def _download_docker_image_with_progress(self, image_name: str, display_name: str, env: Dict = None) -> None:
        """
        Download Docker image with enhanced progress messages and error handling.

        Args:
            image_name: Full Docker image name (e.g., 'deepmi/fastsurfer:latest')
            display_name: Human-readable name for progress messages
            env: Environment variables for Docker command

        Raises:
            subprocess_module.CalledProcessError: If Docker pull fails
        """
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"Downloading {display_name} Docker image (~4GB). This may take 10-15 minutes..."
            )

        logger.info(f"starting_download_{image_name.replace('/', '_')}")

        if env is None:
            env = self._get_extended_env()

        env.update({
            'DOCKER_CLI_HINTS': 'false',
            'DOCKER_HIDE_LEGACY_COMMANDS': 'true',
            'DOCKER_CLI_EXPERIMENTAL': 'disabled'
        })

        try:
            # First, try to pull without quiet flag to show progress (if supported)
            # Fall back to quiet mode if progress display fails
            try:
                logger.info("attempting_docker_pull_with_progress")
                result = subprocess_module.run(
                    ["docker", "pull", image_name],
                    capture_output=False,  # Let user see progress
                    timeout=FREESURFER_DOWNLOAD_TIMEOUT_MINUTES*60,
                    env=env
                )
            except subprocess_module.TimeoutExpired:
                raise subprocess_module.TimeoutExpired(
                    cmd=["docker", "pull", image_name],
                    timeout=FREESURFER_DOWNLOAD_TIMEOUT_MINUTES*60,
                    output=None,
                    stderr=f"Docker image download timed out after {FREESURFER_DOWNLOAD_TIMEOUT_MINUTES} minutes"
                )

            if result.returncode == 0:
                logger.info(f"{image_name.replace('/', '_')}_download_successful")
                if self.progress_callback:
                    self.progress_callback(
                        self._get_current_progress(),
                        f" {display_name} ready - continuing processing..."
                    )
            else:
                error_msg = result.stderr.decode() if result.stderr else "Unknown error"

                # Enhanced error messages for common Docker issues
                if "timeout" in error_msg.lower():
                    error_msg = f"Docker image download timed out. This can happen with slow internet connections.\n\nTroubleshooting:\n• Check your internet speed\n• Try again later when network is faster\n• Use a wired connection if on WiFi\n• Original error: {error_msg}"
                elif "no space left on device" in error_msg.lower():
                    error_msg = f"Insufficient disk space for Docker image download.\n\nThe {display_name} image requires ~4GB of free space.\n\nTroubleshooting:\n• Free up at least 5GB of disk space\n• Run 'docker system prune' to clean up old images\n• Check available space with 'df -h'\n• Original error: {error_msg}"
                elif "network" in error_msg.lower() or "connection" in error_msg.lower():
                    error_msg = f"Network connectivity issue during Docker download.\n\nTroubleshooting:\n• Check your internet connection\n• Try disabling VPN if active\n• Check firewall/proxy settings\n• Try 'docker pull hello-world' to test basic connectivity\n• Original error: {error_msg}"
                elif "denied" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    error_msg = f"Docker registry access denied.\n\nTroubleshooting:\n• Ensure you're logged into Docker Hub if needed\n• Check if you're behind a corporate firewall\n• Try 'docker login' if you have Docker Hub credentials\n• Original error: {error_msg}"

                logger.error(f"{image_name.replace('/', '_')}_download_failed", error=error_msg)
                raise subprocess_module.CalledProcessError(
                    result.returncode,
                    ["docker", "pull", image_name],
                    None,
                    error_msg
                )

        except subprocess_module.TimeoutExpired as e:
            timeout_msg = f"Docker image download for {display_name} timed out after {FREESURFER_DOWNLOAD_TIMEOUT_MINUTES} minutes.\n\nThis usually happens with slow internet connections. Try:\n• Using a faster internet connection\n• Downloading during off-peak hours\n• Using a wired connection instead of WiFi\n• Contacting your network administrator if on a corporate network"
            logger.error("docker_download_timeout", image=image_name, timeout_minutes=FREESURFER_DOWNLOAD_TIMEOUT_MINUTES)
            raise subprocess_module.TimeoutExpired(e.cmd, e.timeout, e.output, timeout_msg)

        except subprocess_module.CalledProcessError:
            # Re-raise with enhanced error message
            raise

    def process(self, input_path: str) -> Dict:
        """
        Execute the complete processing pipeline.

        Args:
            input_path: Path to input MRI file (DICOM or NIfTI)

        Returns:
            Dictionary containing processing results and metrics
        """
        logger.info("processing_pipeline_started", job_id=str(self.job_id))
        print(f"DEBUG: ===== MRI PROCESSOR STARTED =====")
        print(f"DEBUG: Job ID: {self.job_id}")
        print(f"DEBUG: Input path: {input_path}")
        print(f"DEBUG: Input exists: {os.path.exists(input_path)}")
        print(f"DEBUG: Input size: {os.path.getsize(input_path) if os.path.exists(input_path) else 'N/A'}")
        print(f"DEBUG: Output dir: {self.output_dir}")
        print(f"DEBUG: Output dir exists: {self.output_dir.exists()}")
        print(f"DEBUG: Working directory: {os.getcwd()}")
        print(f"DEBUG: Process PID: {os.getpid()}")
        print(f"DEBUG: Database session: {self.db_session is not None}")

        # Save patient info at START of processing (Fix #2)
        # After initialization complete, when worker has stable resources
        # If this fails, it's caught and logged but doesn't stop processing
        self._save_patient_info()

        # PRODUCTION MODE: Always use real FreeSurfer processing - no mock fallbacks allowed
        logger.info("production_processing_mode", mock_fallbacks_disabled=True, real_processing_only=True)
        print(f"DEBUG: Starting system validation")

        # For real FreeSurfer processing (default), continue with Docker-based processing
        # Validate system requirements
        print(f"DEBUG: Validating disk space...")
        self.validate_disk_space()
        print(f"DEBUG: Disk validation passed")

        print(f"DEBUG: Validating memory...")
        self.validate_memory()
        print(f"DEBUG: Memory validation passed")

        print(f"DEBUG: Validating network...")
        self.validate_network_connectivity()
        print(f"DEBUG: Network validation passed")

        # Step 1: Convert to NIfTI if needed
        self._update_progress(10, "Preparing input file...")
        nifti_path = self._prepare_input(input_path)
        
        # Step 2: Run FreeSurfer segmentation (whole brain) - LONGEST STEP
        # Allocate the weighted FreeSurfer phases to 20-90%
        self._update_progress(20, "Starting FreeSurfer segmentation...")
        freesurfer_output = self._run_freesurfer_primary(nifti_path)
        
        # Step 3: Extract hippocampal volumes (from FreeSurfer outputs)
        self._update_progress(92, "Extracting hippocampal volumes...")
        logger.info("extracting_hippocampal_data_from_freesurfer_output", freesurfer_output=str(freesurfer_output))
        hippocampal_stats = self._extract_hippocampal_data(freesurfer_output)
        logger.info("hippocampal_stats_extracted", stats=hippocampal_stats)

        # Validate that we have real hippocampal data
        if not hippocampal_stats:
            error_msg = ("Failed to extract hippocampal volume data from FreeSurfer output. "
                        "FreeSurfer processing may have failed or produced incomplete results. "
                        f"Check FreeSurfer logs in {freesurfer_output}")

            # Production: Always fail with clear error message - no mock data fallback
            logger.error("hippocampal_extraction_failed_no_fallback",
                       error=error_msg,
                       freesurfer_output=str(freesurfer_output))
            raise RuntimeError(f"Hippocampal segmentation failed: {error_msg}")

        # Step 4: Calculate asymmetry indices
        self._update_progress(95, "Calculating asymmetry indices...")
        logger.info("calculating_asymmetry_from_stats", hippocampal_stats=hippocampal_stats)
        metrics = self._calculate_asymmetry(hippocampal_stats)
        logger.info("asymmetry_metrics_calculated", metrics=metrics, metrics_count=len(metrics))
        
        # Step 5: Generate segmentation visualizations
        self._update_progress(97, "Generating visualizations...")
        visualization_paths = self._generate_visualizations(nifti_path, freesurfer_output)
        
        # Validate that visualizations were actually generated
        self._validate_visualizations(visualization_paths)
        
        # Step 6: Save results
        self._update_progress(99, "Saving results...")
        self._save_results(metrics)
        
        logger.info(
            "processing_pipeline_completed",
            job_id=str(self.job_id),
            metrics_count=len(metrics),
        )

        # Ensure any orphaned containers for this job are cleaned up
        self._cleanup_job_containers()

        result = {
            "job_id": str(self.job_id),
            "output_dir": str(self.output_dir),
            "metrics": metrics,
            "visualizations": visualization_paths,
            "mock_processing": self.mock_processing,
        }
        print(f"DEBUG: MRI processor returning mock_processing={self.mock_processing}")
        return result
    
    def _prepare_input(self, input_path: str) -> Path:
        """
        Prepare input file for processing.
        
        Converts DICOM to NIfTI if needed, validates format.
        
        Args:
            input_path: Path to input file
        
        Returns:
            Path to NIfTI file
        """
        print(f"DEBUG: _prepare_input called with: {input_path}")
        input_file = Path(input_path)
        print(f"DEBUG: Input file path: {input_file}")
        print(f"DEBUG: Input file exists: {input_file.exists()}")
        print(f"DEBUG: Input file suffix: {input_file.suffix}")

        # If already NIfTI, validate and return
        if input_file.suffix in [".nii", ".gz"]:
            print(f"DEBUG: File is NIfTI format, validating...")
            validation_result = file_utils.validate_nifti(input_file)
            print(f"DEBUG: NIfTI validation result: {validation_result}")
            if validation_result:
                logger.info("input_validated", format="NIfTI")
                print(f"DEBUG: Returning validated NIfTI file: {input_file}")
                return input_file
            else:
                raise ValueError(f"NIfTI file validation failed: {input_file}")
        
        # Convert DICOM to NIfTI
        elif input_file.suffix in [".dcm", ".dicom"]:
            logger.info("converting_dicom_to_nifti")
            output_path = self.output_dir / "input.nii.gz"
            file_utils.convert_dicom_to_nifti(input_file, output_path)
            return output_path
        
        else:
            raise ValueError(f"Unsupported file format: {input_file.suffix}")
    
    def _is_docker_available(self) -> bool:
        """
        Quick but robust check if Docker is available (for fallback logic).

        Uses retry logic to handle transient Docker daemon issues.
        """
        import time

        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = subprocess_module.run(
                    ["docker", "version"],
                    capture_output=True,
                    timeout=5,
                    env=self._get_extended_env()
                )
                if result.returncode == 0:
                    return True

                # If failed and not last attempt, wait briefly
                if attempt < max_retries - 1:
                    time.sleep(0.5)

            except:
                # If failed and not last attempt, wait briefly
                if attempt < max_retries - 1:
                    time.sleep(0.5)

        return False

    def _is_singularity_available(self) -> bool:
        """
        Quick check if Singularity/Apptainer is available (for fallback logic).
        """
        for cmd in ["apptainer", "singularity"]:
            try:
                result = subprocess_module.run(
                    [cmd, "--version"],
                    capture_output=True,
                    timeout=5,
                    env=self._get_extended_env()
                )
                if result.returncode == 0:
                    return True
            except:
                continue
        return False

    # _is_native_freesurfer_available method removed - native FreeSurfer support disabled

    def _get_extended_env(self) -> dict:
        """
        Get environment with extended PATH for container runtimes.
        """
        env = os.environ.copy()
        current_path = env.get('PATH', '')
        user_home = os.path.expanduser('~')

        # Add common container runtime locations
        extra_paths = [
            f'{user_home}/bin',
            '/usr/local/bin',
            '/usr/bin',
            '/bin',
            '/opt/bin',
            '/snap/bin',
            '/opt/singularity/bin',
            '/opt/apptainer/bin',
        ]

        extended_path = current_path
        for path in extra_paths:
            if path not in current_path:
                extended_path = f"{path}:{extended_path}"

        env['PATH'] = extended_path
        return env

    def _check_container_runtime_availability(self) -> str:
        """
        Check which FreeSurfer container execution method is available and preferred.

        Returns:
            "docker", "singularity", or "none"
        """
        import shutil

        logger.info("checking_freesurfer_container_runtimes", note="Starting FreeSurfer container runtime detection")

        # Check container FreeSurfer execution methods only (no native support)
        docker_available = False
        singularity_available = False
        singularity_cmd = None

        # Check which command is available with extended PATH
        # Similar to Docker detection, extend PATH for common Singularity locations
        env = os.environ.copy()
        current_path = env.get('PATH', '')
        logger.info("checking_singularity_path", path=current_path)

        # Add common Singularity/Apptainer locations to PATH
        import getpass
        user_home = os.path.expanduser('~')
        singularity_paths = [
            f'{user_home}/bin',           # User's bin directory
            '/usr/local/bin',             # Manual installs
            '/usr/bin',                   # System default
            '/bin',                       # Fallback system path
            '/opt/bin',                   # Optional packages
            '/opt/singularity/bin',       # Singularity default install
            '/opt/apptainer/bin',         # Apptainer default install
            '/usr/local/singularity/bin', # Alternative Singularity location
            '/usr/local/apptainer/bin',   # Alternative Apptainer location
            '/opt/modulefiles/bin',       # Module system locations
            '/cm/shared/apps/singularity', # Common HPC locations
            '/shared/apps/singularity',
            '/opt/apps/singularity',
            '/opt/hpc/singularity',
        ]

        # Add configured Singularity bin path if specified
        if hasattr(settings, 'singularity_bin_path') and settings.singularity_bin_path:
            singularity_paths.insert(0, settings.singularity_bin_path)
            logger.info("added_configured_singularity_path", path=settings.singularity_bin_path)

        extended_path = current_path
        for path in singularity_paths:
            if path not in current_path:
                extended_path = f"{path}:{extended_path}"
        env['PATH'] = extended_path

        logger.info("extended_singularity_path", path=extended_path)

        # Check for commands with extended PATH
        def check_command_with_path(cmd):
            """Check if command exists using extended PATH"""
            try:
                result = subprocess_module.run(
                    ['which', cmd],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    logger.info("found_command_with_extended_path", command=cmd, path=result.stdout.strip())
                    return True
            except (subprocess_module.TimeoutExpired, subprocess_module.CalledProcessError):
                pass
            return False

        # Check for Apptainer first (newer, more actively maintained)
        if check_command_with_path("apptainer"):
            singularity_cmd = "apptainer"
            logger.info("found_apptainer_command")
        elif check_command_with_path("singularity"):
            singularity_cmd = "singularity"
            logger.info("found_singularity_command")
        else:
            # Fallback: check absolute paths directly if PATH-based checks fail
            logger.info("path_based_checks_failed_trying_absolute_paths")
            if os.path.exists('/usr/bin/apptainer') and os.access('/usr/bin/apptainer', os.X_OK):
                singularity_cmd = "/usr/bin/apptainer"
                logger.info("found_apptainer_via_absolute_path", path="/usr/bin/apptainer")
            elif os.path.exists('/usr/bin/singularity') and os.access('/usr/bin/singularity', os.X_OK):
                singularity_cmd = "/usr/bin/singularity"
                logger.info("found_singularity_via_absolute_path", path="/usr/bin/singularity")
            elif os.path.exists('/usr/local/bin/apptainer') and os.access('/usr/local/bin/apptainer', os.X_OK):
                singularity_cmd = "/usr/local/bin/apptainer"
                logger.info("found_apptainer_via_absolute_path", path="/usr/local/bin/apptainer")
            else:
                logger.warning("no_singularity_commands_found")

        if singularity_cmd:
            # Quick test to see if Singularity works with extended PATH
            try:
                logger.info("testing_singularity_version", command=singularity_cmd)
                result = subprocess_module.run(
                    [singularity_cmd, "--version"],
                    capture_output=True,
                    timeout=5,
                    env=env
                )
                if result.returncode == 0:
                    singularity_available = True
                    logger.info("singularity_available", version=result.stdout.decode().strip() if result.stdout else "unknown")
                else:
                    logger.warning("singularity_version_check_failed", returncode=result.returncode, stderr=result.stderr.decode()[:100] if result.stderr else "no stderr")
            except (FileNotFoundError, subprocess_module.TimeoutExpired, subprocess_module.CalledProcessError) as e:
                logger.warning("singularity_test_failed", error=str(e))

        # Check for Docker
        docker_available = False
        try:
            # First try with explicit PATH that includes common Docker locations
            env = os.environ.copy()
            current_path = env.get('PATH', '')
            logger.info("current_path", path=current_path)

            # Add common Docker locations to PATH
            import getpass
            user_home = os.path.expanduser('~')
            docker_paths = [
                f'{user_home}/bin',       # User's bin directory (most common)
                '/usr/local/bin',         # Manual installs, Homebrew (Linux)
                '/usr/bin',               # System default (apt, dnf, pacman, etc.)
                '/bin',                   # Fallback system path
                '/opt/bin',               # Optional packages
                '/snap/bin',              # Snap packages
                '/opt/docker-desktop/bin', # Docker Desktop for Linux
                '/opt/docker/bin',        # Alternative Docker installs
            ]
            extended_path = current_path
            for path in docker_paths:
                if path not in current_path:
                    extended_path = f"{path}:{extended_path}"
            env['PATH'] = extended_path

            logger.info("extended_path", path=extended_path)
            logger.info("testing_docker_availability")

            # Try with extended PATH first
            result = subprocess_module.run(
                ["docker", "version"],
                capture_output=True,
                timeout=5,
                env=env
            )
            if result.returncode == 0:
                docker_available = True
                logger.info("docker_available", version=result.stdout.decode().strip()[:50] if result.stdout else "unknown")
            else:
                logger.warning("docker_version_check_failed", returncode=result.returncode, stderr=result.stderr.decode()[:100] if result.stderr else "no stderr")

                # Fallback: try absolute paths directly
                logger.info("docker_path_check_failed_trying_absolute_paths")
                docker_binary_paths = [
                    f"{user_home}/bin/docker",
                    "/usr/bin/docker",
                    "/usr/local/bin/docker",
                    "/opt/docker/bin/docker",
                    "/opt/docker-desktop/bin/docker",
                    "/snap/bin/docker"
                ]

                for docker_path in docker_binary_paths:
                    if os.path.exists(docker_path) and os.access(docker_path, os.X_OK):
                        logger.info("found_docker_via_absolute_path", path=docker_path)
                        try:
                            result = subprocess_module.run(
                                [docker_path, "version"],
                                capture_output=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                docker_available = True
                                logger.info("docker_available_via_absolute_path", path=docker_path, version=result.stdout.decode().strip()[:50] if result.stdout else "unknown")
                                break
                        except (subprocess_module.TimeoutExpired, subprocess_module.CalledProcessError, FileNotFoundError) as e:
                            logger.debug("docker_test_failed_at_path", path=docker_path, error=str(e))
                            continue

        except (FileNotFoundError, subprocess_module.TimeoutExpired, subprocess_module.CalledProcessError) as e:
            logger.warning("docker_test_failed", error=str(e))

        # FreeSurfer Runtime Selection Logic:
        # 1. Singularity is preferred for HPC environments and stability
        # 2. Docker is used as fallback for broader compatibility
        # 3. Mock data is used only when no container method works

        prefer_singularity = getattr(settings, 'prefer_singularity', True)  # Force Singularity due to Docker issues

        logger.info("freesurfer_runtime_selection_starting",
                   docker_available=docker_available,
                   singularity_available=singularity_available,
                   prefer_singularity=prefer_singularity)

        # Primary selection logic - FORCE SINGULARITY due to Docker user namespace issues
        if singularity_available:
            logger.info("using_singularity_as_primary_runtime_forced_due_to_docker_issues")
            return "singularity"

        if docker_available:
            # Docker as fallback (may have user namespace issues)
            logger.warning("using_docker_as_fallback_runtime_singularity_preferred_but_unavailable")
            return "docker"

        if singularity_available:
            # Docker not available, try Singularity as fallback
            if self._find_singularity_image():
                logger.info("using_singularity_as_docker_fallback")
                return "singularity"
            else:
                logger.warning("singularity_available_but_no_image_found")

        # No container runtimes available
        logger.warning("no_container_runtimes_available_for_freesurfer")

        # No working FreeSurfer runtime found
        logger.warning("no_freesurfer_runtime_available_will_use_mock_data")
        return "none"

    # ===== CONCURRENCY CONTROL METHODS =====

    def _check_container_concurrency_limit(self) -> None:
        """
        Check if launching another FreeSurfer container would exceed concurrency limits.

        Raises RuntimeError if the limit would be exceeded, preventing resource exhaustion.
        This enforces the max_concurrent_jobs setting at the container orchestration level.
        """
        try:
            # Get current running FreeSurfer containers
            result = subprocess_module.run(
                ["docker", "ps", "--filter", f"name={settings.freesurfer_container_prefix}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                running_containers = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                current_count = len(running_containers)

                logger.info("container_concurrency_check",
                          current_running=current_count,
                          max_allowed=settings.max_concurrent_jobs,
                          job_id=str(self.job_id))

                if current_count >= settings.max_concurrent_jobs:
                    running_names = ", ".join(running_containers) if running_containers else "none"
                    raise RuntimeError(
                        f"Container concurrency limit exceeded. "
                        f"Currently running: {current_count} FreeSurfer containers ({running_names}). "
                        f"Maximum allowed: {settings.max_concurrent_jobs}. "
                        f"Please wait for existing jobs to complete before starting new ones."
                    )

                logger.info("container_concurrency_check_passed",
                          current_running=current_count,
                          max_allowed=settings.max_concurrent_jobs,
                          job_id=str(self.job_id))
            else:
                # If docker ps fails, log warning but allow processing to continue
                logger.warning("container_concurrency_check_failed",
                             error=result.stderr.strip(),
                             message="Could not check running containers, proceeding with caution")

        except RuntimeError:
            # Re-raise RuntimeError (concurrency limit exceeded) to block processing
            raise
        except subprocess_module.TimeoutExpired:
            logger.warning("container_concurrency_check_timeout",
                         message="Docker ps command timed out, proceeding with caution")
        except Exception as e:
            logger.warning("container_concurrency_check_error",
                         error=str(e),
                         message="Error checking container concurrency, proceeding with caution")

    # ===== FREESURFER FALLBACK METHODS =====

    def _is_freesurfer_available(self) -> bool:
        """Check if FreeSurfer can be used as fallback."""
        try:
            # Must have Docker (for now - could add Singularity later)
            if not self._is_docker_available():
                logger.warning("freesurfer_unavailable_no_docker",
                              message="FreeSurfer requires Docker, but Docker is not available or not running. "
                                     "Please install Docker Desktop or ensure Docker daemon is running.")
                return False

            # Must have license
            license_path = self._get_freesurfer_license_path()
            if not license_path:
                logger.warning("freesurfer_unavailable_no_license",
                              message="FreeSurfer license not found. Processing will continue with alternative methods. "
                                     "To enable FreeSurfer, place license.txt in the app folder or set FREESURFER_LICENSE environment variable.")
                return False

            logger.debug("freesurfer_available_for_fallback")
            return True

        except Exception as e:
            logger.warning("freesurfer_availability_check_failed",
                          error=str(e),
                          message="Failed to check FreeSurfer availability due to unexpected error.")
            return False

    def _is_docker_performing_cleanup(self) -> bool:
        """
        Check if Docker daemon appears to be performing cleanup operations.

        This is a heuristic check that looks for signs of cleanup activity.
        """
        try:
            # Check for running containers that might be in cleanup
            result = subprocess_module.run(
                ["docker", "ps", "-a", "--filter", "status=exited", "--format", "{{.Names}}"],
                capture_output=True,
                timeout=5,
                env=self._get_extended_env()
            )

            if result.returncode == 0:
                exited_containers = result.stdout.decode().strip().split('\n')
                exited_containers = [c for c in exited_containers if c.strip()]

                # If there are recently exited FreeSurfer containers, cleanup might be happening
                freesurfer_exited = [
                    c for c in exited_containers if c.startswith(settings.freesurfer_container_prefix)
                ]
                if freesurfer_exited:
                    logger.info("detected_recently_exited_freesurfer_containers",
                              count=len(freesurfer_exited),
                              containers=freesurfer_exited)
                    return True

            # Check system prune operations (if any are running)
            # This is harder to detect directly, but we can check for docker system commands

        except Exception as e:
            logger.debug("error_checking_docker_cleanup_status", error=str(e))

        return False

    def _wait_for_docker_cleanup_if_needed(self) -> None:
        """
        Proactively wait for Docker cleanup if detected, before attempting Docker operations.

        This helps prevent the "No container runtimes available" error by ensuring
        Docker is fully ready before starting container operations.
        """
        if self._is_docker_performing_cleanup():
            logger.info("docker_cleanup_detected_waiting_before_processing")
            self._wait_for_docker_cleanup()
        else:
            logger.debug("no_docker_cleanup_detected_proceeding")

    def _wait_for_docker_cleanup(self, max_wait_seconds: Optional[int] = None) -> bool:
        """
        Wait for Docker daemon to complete any cleanup operations.

        Returns True if Docker becomes available within the timeout, False otherwise.
        """
        import time

        # Use configured timeout if not specified
        if max_wait_seconds is None:
            from backend.core.config import get_settings
            settings = get_settings()
            max_wait_seconds = settings.docker_cleanup_wait_timeout

        logger.info("checking_for_docker_cleanup_activity", max_wait=max_wait_seconds)

        # First check if we can detect cleanup activity
        if self._is_docker_performing_cleanup():
            logger.info("detected_docker_cleanup_activity_waiting")

        start_time = time.time()
        check_interval = 2.0  # Check every 2 seconds

        while time.time() - start_time < max_wait_seconds:
            try:
                # Quick check if Docker is responsive
                result = subprocess_module.run(
                    ["docker", "version"],
                    capture_output=True,
                    timeout=5,
                    env=self._get_extended_env()
                )

                if result.returncode == 0:
                    elapsed = time.time() - start_time
                    logger.info("docker_available_after_cleanup_wait",
                              wait_time=elapsed,
                              max_wait=max_wait_seconds)
                    return True

            except (subprocess_module.TimeoutExpired, FileNotFoundError, Exception):
                pass  # Continue waiting

            # Wait before next check
            time.sleep(check_interval)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning("docker_cleanup_wait_timeout",
                     elapsed=elapsed,
                     max_wait=max_wait_seconds)
        return False

    def _check_docker_available(self) -> bool:
        """
        Robustly check if Docker is available and functioning.

        Uses multiple checks with retry logic to handle transient Docker daemon issues.
        Includes automatic waiting for cleanup operations to complete.
        """
        import time

        # Docker commands to try in order of reliability
        docker_checks = [
            ["docker", "version"],  # Quick check, usually fastest
            ["docker", "info"],     # More comprehensive check
            ["docker", "ps"]        # Check if we can list containers
        ]

        max_retries = 3
        base_delay = 1.0  # seconds

        for check_cmd in docker_checks:
            cmd_name = check_cmd[1]  # 'version', 'info', or 'ps'

            for attempt in range(max_retries):
                try:
                    logger.debug("docker_check_attempt",
                               command=cmd_name,
                               attempt=attempt + 1,
                               max_retries=max_retries)

                    result = subprocess_module.run(
                        check_cmd,
                        capture_output=True,
                        timeout=10,
                        env=self._get_extended_env()
                    )

                    if result.returncode == 0:
                        logger.info("docker_available",
                                  command=cmd_name,
                                  attempt=attempt + 1)
                        return True
                    else:
                        stderr_msg = result.stderr.decode()[:200] if result.stderr else "Unknown error"
                        logger.warning("docker_command_failed",
                                     command=cmd_name,
                                     attempt=attempt + 1,
                                     returncode=result.returncode,
                                     stderr=stderr_msg)

                        # If this is not the last attempt, wait before retrying
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)  # Exponential backoff
                            logger.info("docker_retry_delay",
                                      command=cmd_name,
                                      delay=delay)
                            time.sleep(delay)

                except subprocess_module.TimeoutExpired:
                    logger.warning("docker_command_timeout",
                                 command=cmd_name,
                                 attempt=attempt + 1,
                                 timeout=10)

                    # Check if this might be due to cleanup activity
                    # Only do this on the first timeout to avoid excessive waiting
                    if attempt == 0 and cmd_name == "version":
                        logger.info("docker_timeout_detected_checking_for_cleanup")
                        if self._wait_for_docker_cleanup(max_wait_seconds=15):
                            # Docker became available after waiting for cleanup
                            logger.info("docker_available_after_cleanup_wait_retry")
                            return True  # Retry immediately

                    # If this is not the last attempt, wait before retrying
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)

                except FileNotFoundError:
                    logger.warning("docker_not_installed",
                                 message="Docker is not installed. Install Docker to enable FreeSurfer processing.")
                    return False
                except Exception as e:
                    logger.warning("docker_check_exception",
                                 command=cmd_name,
                                 attempt=attempt + 1,
                                 error=str(e))

                    # If this is not the last attempt, wait before retrying
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)

        # All checks failed
        logger.error("docker_unavailable_all_checks_failed",
                   message="All Docker availability checks failed. Docker daemon may be unresponsive or not installed.")
        return False

    def _get_freesurfer_license_path(self) -> Path:
        """Get FreeSurfer license path from multiple possible locations.

        Searches in the same locations as the license API for consistency.
        """
        # Use the same search logic as the license API
        base_dir = Path(__file__).parent.parent.parent  # desktop_alone_web directory
        search_paths = [
            base_dir / "license.txt",  # Primary location for users
            base_dir / "freesurfer_license.txt",  # Legacy support
            base_dir / "resources" / "licenses" / "license.txt",
            base_dir / "resources" / "licenses" / "freesurfer_license.txt",
            Path.home() / "neuroinsight" / "resources" / "licenses" / "license.txt",
            Path.home() / "neuroinsight" / "license.txt",
            Path("/usr/local/freesurfer/license.txt"),  # System FreeSurfer location
        ]

        # Also check environment variable
        import os
        license_env = os.getenv('FREESURFER_LICENSE')
        if license_env and Path(license_env).exists():
            logger.debug("freesurfer_license_found_via_env", path=license_env)
            return Path(license_env)

        # Check all search paths
        for license_path in search_paths:
            if license_path.exists():
                logger.debug("freesurfer_license_found", path=str(license_path))
                return license_path

        logger.debug("freesurfer_license_not_found")
        return None
        if legacy_app_license.exists():
            logger.debug("freesurfer_license_found_legacy_app", path=str(legacy_app_license))
            return legacy_app_license

        logger.debug("freesurfer_license_not_found")
        logger.warning("freesurfer_no_license_detected",
                      message="No FreeSurfer license found in any location. "
                             "Users should place license.txt in the app folder or set FREESURFER_LICENSE environment variable.")
        return None

    def _get_app_root_directory(self) -> Path:
        """Get the application root directory (works for both development and deployed apps)."""
        # Get the directory containing the MRI processor module
        processor_dir = Path(__file__).parent  # pipeline/processors/
        pipeline_dir = processor_dir.parent     # pipeline/
        app_root = pipeline_dir.parent          # desktop_alone_web/

        # For deployed apps, check if we're in a bundled environment
        if app_root.name == "desktop_alone_web":
            return app_root
        else:
            # Try to find the app root by going up directories
            current = Path.cwd()
            for _ in range(5):  # Don't go up more than 5 levels
                if (current / "resources" / "licenses").exists():
                    return current
                current = current.parent

        # Fallback to current working directory approach
        return Path.cwd()

    def _ensure_container_image(self, image_name: str, display_name: str, size_gb: int = 4) -> None:
        """Generic lazy container download with progress reporting."""
        try:
            # Check if image exists
            result = subprocess_module.run(
                ["docker", "images", "-q", image_name],
                capture_output=True, timeout=10
            )

            if not result.stdout.strip():
                logger.info(f"{image_name.replace('/', '_')}_image_missing_starting_download")

                # Show progress to user
                if self.progress_callback:
                    self.progress_callback(
                        self._get_current_progress(),
                        f"[DOWNLOAD] Downloading {display_name} ({size_gb}GB, one-time - 10-15 min)..."
                    )

                # Download with timeout - disable TTY requirements
                # Enhanced Docker image download with progress messages
                self._download_docker_image_with_progress(image_name, display_name)

                if result.returncode == 0:
                    logger.info(f"{image_name.replace('/', '_')}_download_successful")
                    if self.progress_callback:
                        self.progress_callback(
                            self._get_current_progress(),
                            f" {display_name} ready - continuing processing..."
                        )
                else:
                    error_msg = result.stderr.decode() if result.stderr else "Unknown error"
                    logger.error(f"{image_name.replace('/', '_')}_download_failed", error=error_msg)

                    # Check for common Docker environment issues
                    if "short-name resolution enforced" in error_msg:
                        error_msg += " (Docker requires TTY for interactive prompts. Try running from a terminal.)"
                    elif "insufficient UIDs or GIDs" in error_msg:
                        error_msg += " (Container UID/GID mapping issue in this environment.)"

                    raise RuntimeError(f"{display_name} download failed: {error_msg}")

        except subprocess_module.TimeoutExpired:
            logger.error(f"{image_name.replace('/', '_')}_download_timeout")
            raise RuntimeError(f"{display_name} download timed out after {FREESURFER_DOWNLOAD_TIMEOUT_MINUTES} minutes")

    def _run_freesurfer_fallback(self, nifti_path: Path, output_dir: Path) -> Path:
        """Execute FreeSurfer segmentation with automatic runtime selection and fallbacks."""
        logger.info("starting_freesurfer_fallback", input=str(nifti_path))

        # Get license path early
        license_path = self._get_freesurfer_license_path()
        if not license_path:
            raise RuntimeError("FreeSurfer license not found")

        # Use the new intelligent runtime selection
        freesurfer_runtime = self._check_container_runtime_availability()
        attempted_runtimes = []

        logger.info("freesurfer_runtime_selected", runtime=freesurfer_runtime)

        # COMMENTED OUT: Nipype requires manual FreeSurfer installation
        # Keeping containers as primary method for easier deployment
        # try:
        #     logger.info("attempting_freesurfer_nipype_first")
        #     attempted_runtimes.append("nipype")
        #     return self._run_freesurfer_nipype(nifti_path, output_dir, license_path)
        # except Exception as nipype_error:
        #     logger.warning("freesurfer_nipype_failed", error=str(nipype_error), error_type=type(nipype_error).__name__)

        # Try selected runtime with intelligent fallback logic
        if freesurfer_runtime == "docker":
            logger.info("attempting_freesurfer_docker_primary")
            attempted_runtimes.append("docker")
            try:
                return self._run_freesurfer_docker(nifti_path, output_dir, license_path)
            except Exception as docker_error:
                logger.warning("freesurfer_docker_failed", error=str(docker_error), error_type=type(docker_error).__name__)

                # Try Singularity fallback
                if self._is_singularity_available() and self._find_singularity_image():
                    logger.info("docker_failed_trying_singularity_fallback")
                    attempted_runtimes.append("singularity")
                    try:
                        return self._run_freesurfer_singularity(nifti_path, output_dir)
                    except Exception as sing_error:
                        logger.warning("singularity_fallback_failed", error=str(sing_error), error_type=type(sing_error).__name__)

                # Native FreeSurfer support removed - only container methods available

        elif freesurfer_runtime == "singularity":
            logger.info("attempting_freesurfer_singularity_primary")
            attempted_runtimes.append("singularity")
            try:
                return self._run_freesurfer_singularity(nifti_path, output_dir)
            except Exception as sing_error:
                logger.warning("freesurfer_singularity_failed", error=str(sing_error), error_type=type(sing_error).__name__)

                # Try Docker fallback
                if self._is_docker_available():
                    logger.info("singularity_failed_trying_docker_fallback")
                    attempted_runtimes.append("docker")
                    try:
                        return self._run_freesurfer_docker(nifti_path, output_dir, license_path)
                    except Exception as docker_error:
                        logger.warning("docker_fallback_failed", error=str(docker_error), error_type=type(docker_error).__name__)

                # Native FreeSurfer support removed - only container methods available

        # Native FreeSurfer support removed - only container methods supported

        # Secondary attempt with Singularity only
        elif freesurfer_runtime == "singularity":
            logger.info("attempting_freesurfer_singularity_as_primary")
            attempted_runtimes.append("singularity")
            try:
                return self._run_freesurfer_singularity(nifti_path, output_dir)
            except Exception as sing_error:
                logger.warning("freesurfer_singularity_failed", error=str(sing_error))

        # If we get here, both runtimes failed
        logger.warning("all_freesurfer_runtimes_failed",
                      attempted_runtimes=attempted_runtimes,
                      note="FreeSurfer fallback failed, will use mock data")

        # This will be handled by the caller - we raise an exception to indicate FreeSurfer failed
        raise RuntimeError(f"FreeSurfer processing failed with all available runtimes: {attempted_runtimes}")

    # _run_freesurfer_native method removed - native FreeSurfer support disabled
    def _find_freesurfer_sif(self) -> Path:
        """Find local FreeSurfer .sif container file."""
        # Get the application directory
        app_dir = Path(__file__).parent.parent.parent  # Go up from processors/mri_processor.py

        # Check multiple possible locations for the .sif file
        search_paths = [
            # HPC FreeSurfer containers (discovered on this system)
            Path("/opt/ood/images/freesurfer/freesurfer_7.4.1.sif"),
            Path("/opt/ood_apps/images/freesurfer/freesurfer_7.4.1.sif"),
            # Common HPC container locations
            Path("/shared/containers/freesurfer/freesurfer.sif"),
            Path("/opt/containers/freesurfer/freesurfer.sif"),
            Path("/usr/local/containers/freesurfer/freesurfer.sif"),
            # Same directory as the application
            Path("./freesurfer.sif"),
            Path("./freesurfer-7.3.2.sif"),
            Path("./freesurfer-7.4.1.sif"),
            # In conda environment
            Path(os.getenv('CONDA_PREFIX', '')) / "share" / "freesurfer.sif" if os.getenv('CONDA_PREFIX') else None,
            # In package directory
            app_dir / "freesurfer.sif",
            app_dir / "freesurfer-7.3.2.sif",
            app_dir / "freesurfer-7.4.1.sif",
            # In distribution package
            app_dir.parent / "freesurfer.sif",
            app_dir.parent / "freesurfer-7.4.1.sif",
        ]

        for path in search_paths:
            if path and path.exists():
                logger.info("freesurfer_sif_found", path=str(path))
                return path

        # If no SIF file found, try to download and convert Docker image
        logger.info("no_local_sif_found_attempting_download")
        downloaded_sif = self._download_freesurfer_apptainer()
        if downloaded_sif and downloaded_sif.exists():
            logger.info("freesurfer_sif_downloaded", path=str(downloaded_sif))
            return downloaded_sif

        logger.warning("no_freesurfer_sif_available")
        return None

    def _ensure_singularity_container(self) -> Path:
        """Ensure FreeSurfer Singularity container is available, downloading if necessary."""
        app_dir = Path(__file__).parent.parent.parent
        target_sif = app_dir / "freesurfer-7.4.1.sif"
        download_script = app_dir / "download_freesurfer_apptainer.sh"

        # Check if container already exists
        if target_sif.exists():
            logger.info("freesurfer_singularity_container_already_exists", path=str(target_sif))
            return target_sif

        # Check if download script exists
        if not download_script.exists():
            logger.warning("singularity_download_script_not_found",
                         script_path=str(download_script),
                         message="Cannot automatically download FreeSurfer Singularity container")
            return None

        logger.info("starting_freesurfer_singularity_download",
                   target=str(target_sif),
                   script=str(download_script))

        # Show progress to user
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"[DOWNLOAD] Downloading FreeSurfer Singularity container (~4GB, one-time - 10-15 min)..."
            )

        try:
            # Run the download script
            result = subprocess_module.run(
                ["bash", str(download_script)],
                cwd=app_dir,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout for download
            )

            if result.returncode == 0 and target_sif.exists():
                logger.info("freesurfer_singularity_download_successful", sif_path=str(target_sif))

                if self.progress_callback:
                    self.progress_callback(
                        self._get_current_progress(),
                        f" FreeSurfer Singularity container ready - continuing processing..."
                    )

                return target_sif
            else:
                logger.error("freesurfer_singularity_download_failed",
                           returncode=result.returncode,
                           stdout=result.stdout.strip(),
                           stderr=result.stderr.strip())
                return None

        except subprocess_module.TimeoutExpired:
            logger.error("freesurfer_singularity_download_timeout", timeout_minutes=30)
            return None
        except Exception as e:
            logger.error("freesurfer_singularity_download_error", error=str(e))
            return None

    def _download_freesurfer_apptainer(self) -> Path:
        """Download FreeSurfer Docker image and convert to Apptainer format."""
        # This method is now deprecated - use _ensure_singularity_container() instead
        return self._ensure_singularity_container()

    def _run_freesurfer_nipype(self, nifti_path: Path, output_dir: Path, license_path: Path) -> Path:
        """Execute FreeSurfer segmentation using nipype within conda environment."""
        subject_id = f"freesurfer_nipype_{self.job_id}"
        freesurfer_dir = output_dir / "freesurfer_nipype"
        freesurfer_dir.mkdir(exist_ok=True)

        # Update progress
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"Processing with FreeSurfer (Nipype) ({subject_id})..."
            )

        try:
            # Check for local .sif file first
            sif_path = self._find_freesurfer_sif()
            if sif_path:
                logger.info("using_local_freesurfer_container", sif_path=str(sif_path))
                return self._run_freesurfer_singularity_local(nifti_path, freesurfer_dir, license_path, sif_path)

            # COMMENTED OUT: No longer falling back to native Nipype
            # This ensures we only use containers for FreeSurfer processing
            # logger.info("no_local_container_found_trying_nipype")
            # return self._run_freesurfer_nipype_system(nifti_path, freesurfer_dir, license_path)

            # If no local containers found, let the main logic handle container fallbacks
            raise Exception("No local FreeSurfer containers found - will fallback to main container logic")

        except Exception as e:
            logger.error("freesurfer_nipype_failed",
                        subject_id=subject_id,
                        error=str(e),
                        error_type=type(e).__name__)
            # Fail with clear error message instead of mock data
            error_msg = (
                "FreeSurfer processing failed: nipype execution error. "
                "FreeSurfer could not process the input file. "
                "Please ensure the NIfTI file is valid and compatible with FreeSurfer."
            )
            logger.error("freesurfer_nipype_failed", error=error_msg)
            raise RuntimeError(error_msg)

    def _run_freesurfer_nipype_system(self, nifti_path: Path, freesurfer_dir: Path, license_path: Path) -> Path:
        """Run FreeSurfer using nipype with system installation."""
        subject_id = f"freesurfer_nipype_{self.job_id}"

        try:
            # Import nipype FreeSurfer interface
            from nipype.interfaces.freesurfer import ReconAll

            # Set FreeSurfer environment
            import os

            # Check for local FreeSurfer installation in project directory
            local_freesurfer = self.app_dir / "freesurfer"  # Directory name after extraction
            if local_freesurfer.exists() and (local_freesurfer / "bin" / "recon-all").exists():
                logger.info("using_local_freesurfer_installation", path=str(local_freesurfer))
                os.environ['FREESURFER_HOME'] = str(local_freesurfer)
                os.environ['PATH'] = f"{local_freesurfer}/bin:{os.environ.get('PATH', '')}"
            else:
                logger.info("using_system_freesurfer_installation")

            # Ensure license is accessible - copy to FREESURFER_HOME and use absolute path
            fs_license_dest = local_freesurfer / 'license.txt'
            if not fs_license_dest.exists():
                import shutil
                shutil.copy2(license_path, fs_license_dest)
            os.environ['FS_LICENSE'] = str(fs_license_dest)

            # Create subjects directory if it doesn't exist
            freesurfer_dir.mkdir(parents=True, exist_ok=True)
            os.environ['SUBJECTS_DIR'] = str(freesurfer_dir)

            # Create ReconAll interface
            recon = ReconAll()
            recon.inputs.subject_id = subject_id
            recon.inputs.subjects_dir = str(freesurfer_dir)
            recon.inputs.T1_files = str(nifti_path)

            recon.inputs.directive = 'autorecon1'  # Initial processing (skull stripping, basic segmentation)

            # Set environment explicitly for nipype to ensure license is found
            import shutil
            env = os.environ.copy()
            fs_license_path = None

            if local_freesurfer.exists():
                env['FREESURFER_HOME'] = str(local_freesurfer)
                env['PATH'] = f"{local_freesurfer}/bin:{env.get('PATH', '')}"

                # Copy license to FREESURFER_HOME directory and use absolute path
                fs_license_path = local_freesurfer / 'license.txt'
                if not fs_license_path.exists():
                    shutil.copy2(license_path, fs_license_path)
                    logger.info("copied_license_to_freesurfer_home", path=str(fs_license_path))

                # Also copy to subjects directory (where FreeSurfer runs)
                subj_license_path = freesurfer_dir / 'license.txt'
                if not subj_license_path.exists():
                    shutil.copy2(license_path, subj_license_path)

            # Use absolute path for FS_LICENSE
            env['FS_LICENSE'] = str(fs_license_path) if fs_license_path else str(license_path)
            env['SUBJECTS_DIR'] = str(freesurfer_dir)
            recon.inputs.environ = env

            logger.info("executing_freesurfer_nipype_system",
                       subject_id=subject_id,
                       input_file=str(nifti_path),
                       output_dir=str(freesurfer_dir))

            # Execute with nipype
            logger.info("starting_nipype_recon_run", subject_id=subject_id)
            result = recon.run()
            logger.info("nipype_recon_run_returned", subject_id=subject_id, result_type=type(result).__name__)

            # Log detailed result information
            if hasattr(result, 'outputs'):
                logger.info("nipype_result_outputs", subject_id=subject_id, outputs=str(result.outputs))
            if hasattr(result, 'runtime'):
                logger.info("nipype_result_runtime", subject_id=subject_id, runtime=str(result.runtime))

            logger.info("freesurfer_nipype_system_completed",
                       subject_id=subject_id,
                       result=str(result))

            # Verify output exists and try to extract hippocampus data
            subject_output_dir = freesurfer_dir / subject_id
            logger.info("checking_subject_output_dir",
                       subject_id=subject_id,
                       output_dir=str(subject_output_dir),
                       exists=subject_output_dir.exists())

            if subject_output_dir.exists():
                # Try to extract hippocampus data from FreeSurfer output
                hippo_data = self._extract_freesurfer_hippocampus_data(freesurfer_dir, subject_id)
                if hippo_data:
                    logger.info("freesurfer_partial_success",
                               subject_id=subject_id,
                               extracted_volumes=hippo_data,
                               message="FreeSurfer completed with usable segmentation data")
                    return freesurfer_dir
                else:
                    logger.warning("freesurfer_no_hippocampus_data",
                                 subject_id=subject_id,
                                 message="FreeSurfer completed but no hippocampus data found")
                    # Continue to mock fallback
            else:
                logger.warning("freesurfer_no_output_directory",
                             subject_id=subject_id,
                             expected_dir=str(subject_output_dir))

            # FreeSurfer didn't produce usable results - fail with clear error
            error_msg = (
                "FreeSurfer processing failed: No usable output produced. "
                "FreeSurfer completed but did not generate expected segmentation files. "
                "This may indicate issues with the input file or FreeSurfer installation."
            )
            logger.error("freesurfer_no_usable_output", error=error_msg, subject_id=subject_id)
            raise RuntimeError(error_msg)

        except Exception as e:
            logger.warning("freesurfer_nipype_system_failed",
                         subject_id=subject_id,
                         error=str(e),
                         error_type=type(e).__name__,
                         message="FreeSurfer nipype execution failed, checking for partial results")

            # Try to extract hippocampus data from any partial FreeSurfer output
            hippo_data = self._extract_freesurfer_hippocampus_data(freesurfer_dir, subject_id)
            if hippo_data:
                logger.info("freesurfer_partial_success_with_error",
                           subject_id=subject_id,
                           extracted_volumes=hippo_data,
                           error=str(e),
                           message="FreeSurfer failed but produced usable hippocampus data")
                return freesurfer_dir
            else:
                # FreeSurfer failed completely - fail with clear error
                error_msg = (
                    f"FreeSurfer processing failed: {str(e)}. "
                    "FreeSurfer encountered an error and could not complete segmentation. "
                    "Please check the input file and try again."
                )
                logger.error("freesurfer_failed_completely", error=error_msg, subject_id=subject_id)
                raise RuntimeError(error_msg)

        except ImportError:
            # Nipype not available - fail with clear error
            error_msg = (
                "FreeSurfer processing failed: nipype library not available. "
                "The system requires nipype for FreeSurfer execution. "
                "Please install nipype: pip install nipype"
            )
            logger.error("nipype_not_available", error=error_msg)
            raise RuntimeError(error_msg)

    def _run_freesurfer_singularity_local(self, nifti_path: Path, freesurfer_dir: Path, license_path: Path, sif_path: Path) -> Path:
        """Run FreeSurfer using local Singularity container."""
        subject_id = f"freesurfer_singularity_{self.job_id}"

        # Ensure the FreeSurfer directory exists (apptainer requires it for mounting)
        freesurfer_dir.mkdir(parents=True, exist_ok=True)

        # Update progress
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"Processing with FreeSurfer (Singularity) ({subject_id})..."
            )

        import os

        # IMPORTANT: Clean up any existing subject directory to prevent "re-run existing subject" error
        subject_output_dir = freesurfer_dir / subject_id
        if subject_output_dir.exists():
            logger.warning("freesurfer_subject_dir_exists",
                          path=str(subject_output_dir),
                          message="Removing existing subject directory to allow recon-all -i to run")
            import shutil
            # Make best-effort permission fixes before deletion (root-owned outputs)
            try:
                subprocess_module.run(
                    ["chmod", "-R", "777", str(subject_output_dir)],
                    capture_output=True,
                    timeout=30
                )
            except Exception as chmod_error:
                logger.warning("failed_to_chmod_subject_dir", path=str(subject_output_dir), error=str(chmod_error))

            shutil.rmtree(subject_output_dir)

        # Convert all paths to absolute paths (required for container mounts)
        abs_freesurfer_dir = freesurfer_dir.resolve()
        abs_input_dir = nifti_path.parent.resolve()
        abs_license_path = license_path.resolve()
        abs_sif_path = sif_path.resolve()
        
        singularity_cmd = [
            "apptainer", "exec",  # or "singularity"
            # Removed --cleanenv to preserve FreeSurfer environment
            "--bind", f"{abs_freesurfer_dir}:/subjects",
            "--bind", f"{abs_input_dir}:/input:ro",
            "--bind", f"{abs_license_path}:/usr/local/freesurfer/license.txt:ro",
            "--env", f"FS_LICENSE=/usr/local/freesurfer/license.txt",
            "--env", f"SUBJECTS_DIR=/subjects",
            *self._get_freesurfer_thread_env("--env"),
            str(abs_sif_path),  # Local .sif file
            "/bin/bash", "-c",
            " recon-all -i /input/{nifti_path.name} -s {subject_id}",
            "-autorecon1",
                "-autorecon2-volonly",
        ]

        logger.info("executing_freesurfer_singularity_combined",
                   command=" ".join(singularity_cmd),
                   subject_id=subject_id,
                   sif_path=str(sif_path),
                   input_file=str(nifti_path))

        try:
            logger.info("freesurfer_singularity_starting_combined_autorecon",
                       command=" ".join(singularity_cmd),
                       nifti_path=str(nifti_path),
                       sif_path=str(sif_path))

            result = subprocess_module.run(
                singularity_cmd,
                capture_output=True,
                timeout=FREESURFER_PROCESSING_TIMEOUT_MINUTES*60,  # Use the configured timeout
                text=True,
                env=self._get_extended_env()
            )

            if result.returncode != 0:
                logger.error("freesurfer_combined_autorecon_failed",
                           returncode=result.returncode,
                           stderr=result.stderr[:1000],
                           stdout=result.stdout[:1000])
                raise RuntimeError(f"FreeSurfer combined autorecon failed: {result.stderr[:200]}")

            logger.info("freesurfer_combined_autorecon_completed")

            # Now run mri_segstats to generate aseg.stats from aseg.auto.mgz
            subject_mri_dir = freesurfer_dir / subject_id / "mri"
            subject_stats_dir = freesurfer_dir / subject_id / "stats"
            subject_stats_dir.mkdir(exist_ok=True, parents=True)

            aseg_auto_mgz = subject_mri_dir / "aseg.auto.mgz"
            aseg_stats = subject_stats_dir / "aseg.stats"
            brain_mgz = subject_mri_dir / "brain.mgz"

            if aseg_auto_mgz.exists():
                # Run mri_segstats to generate aseg.stats
                # Use absolute paths for container mounts
                abs_freesurfer_dir = freesurfer_dir.resolve()
                abs_license_path = license_path.resolve()
                abs_sif_path = sif_path.resolve()
                
                segstats_cmd = [
                    "apptainer", "exec",
                    "--bind", f"{abs_freesurfer_dir}:/subjects",
                    "--bind", f"{abs_license_path}:/usr/local/freesurfer/license.txt:ro",
                    "--env", f"FS_LICENSE=/usr/local/freesurfer/license.txt",
                    "--env", f"SUBJECTS_DIR=/subjects",
            *self._get_freesurfer_thread_env("--env"),
                    str(abs_sif_path),
                    "/bin/bash", "-c",
                    f" mri_segstats --seg /subjects/{subject_id}/mri/aseg.auto.mgz --excludeid 0 --sum /subjects/{subject_id}/stats/aseg.stats --i /subjects/{subject_id}/mri/brain.mgz"
                ]

                logger.info("running_mri_segstats_after_combined_autorecon", command=" ".join(segstats_cmd))
                segstats_result = subprocess_module.run(
                    segstats_cmd,
                    capture_output=True,
                    timeout=300,  # 5 minutes for stats generation
                    text=True,
                    env=self._get_extended_env()
                )

                if segstats_result.returncode != 0:
                    logger.warning("mri_segstats_failed_after_combined_autorecon",
                                 returncode=segstats_result.returncode,
                                 stderr=segstats_result.stderr[:500])
                    # Don't raise error - continue with processing, fallback will handle missing stats
                else:
                    logger.info("mri_segstats_completed_after_combined_autorecon")
            else:
                logger.warning("aseg.auto.mgz_not_found_after_combined_autorecon", path=str(aseg_auto_mgz))

            # Use combined autorecon result for final check
            logger.info("freesurfer_singularity_command_result",
                       returncode=result.returncode,
                       stdout_length=len(result.stdout),
                       stderr_length=len(result.stderr))
            if result.returncode != 0:
                logger.error("freesurfer_combined_autorecon_failed",
                           returncode=result.returncode,
                           stderr=result.stderr[:1000],
                           stdout=result.stdout[:1000],
                           command=" ".join(singularity_cmd))

            if result.returncode == 0:
                logger.info("freesurfer_singularity_completed",
                           subject_id=subject_id,
                           stdout_lines=len(result.stdout.split('\n')))

                # Verify output exists
                subject_output_dir = freesurfer_dir / subject_id
                if subject_output_dir.exists():
                    return freesurfer_dir
                else:
                    raise RuntimeError(f"FreeSurfer completed but output directory {subject_output_dir} not found")
            else:
                error_msg = result.stderr or result.stdout
                logger.error("freesurfer_singularity_failed",
                           returncode=result.returncode,
                           error=error_msg[:500])
                raise RuntimeError(f"FreeSurfer Singularity failed: {error_msg[:200]}")

        except subprocess_module.TimeoutExpired:
            logger.error("freesurfer_singularity_timeout",
                        subject_id=subject_id,
                        timeout_minutes=FREESURFER_PROCESSING_TIMEOUT_MINUTES)
            raise RuntimeError(f"FreeSurfer processing timed out after {FREESURFER_PROCESSING_TIMEOUT_MINUTES} minutes")
        except FileNotFoundError as fnf_error:
            logger.error("apptainer_command_not_found",
                        error=str(fnf_error),
                        command=singularity_cmd[0])
            logger.warning("apptainer_not_found", message="Trying singularity command")
            # Try with singularity instead of apptainer
            singularity_cmd[0] = "singularity"
            try:
                result = subprocess_module.run(
                    singularity_cmd,
                    capture_output=True,
                    timeout=FREESURFER_PROCESSING_TIMEOUT_MINUTES*60,
                    text=True,
                    env=self._get_extended_env()
                )
                if result.returncode == 0:
                    subject_output_dir = freesurfer_dir / subject_id
                    if subject_output_dir.exists():
                        return freesurfer_dir
            except:
                pass

            raise RuntimeError("Neither apptainer nor singularity found")

    def _run_freesurfer_docker(self, nifti_path: Path, output_dir: Path, license_path: Path) -> Path:
        print("DEBUG: ENTERING _run_freesurfer_docker method")

        # Docker availability is already checked by the caller; avoid false negatives here.
        if not self._check_docker_available():
            logger.warning(
                "docker_check_failed_in_run_freesurfer",
                job_id=str(self.job_id),
                message="Docker check failed inside runner; attempting to proceed with docker run."
            )

        subject_id = f"freesurfer_docker_{self.job_id}"
        freesurfer_dir = output_dir / "freesurfer_docker"
        freesurfer_dir.mkdir(exist_ok=True)
        abs_freesurfer_dir = freesurfer_dir.resolve()

        # Avoid permission issues from previous runs by using a unique subject id if needed
        subject_output_dir = freesurfer_dir / subject_id
        if subject_output_dir.exists():
            import time
            unique_suffix = int(time.time())
            subject_id = f"{subject_id}_{unique_suffix}"
            subject_output_dir = freesurfer_dir / subject_id
            logger.warning(
                "freesurfer_subject_dir_exists_using_unique_subject",
                previous_path=str(freesurfer_dir / f"freesurfer_docker_{self.job_id}"),
                new_subject_id=subject_id
            )

        # Ensure FreeSurfer container is available (lazy download)
        self._ensure_container_image(
            FREESURFER_CONTAINER_IMAGE,
            "FreeSurfer",
            FREESURFER_CONTAINER_SIZE_GB
        )

        # Update progress
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"Processing with FreeSurfer (Docker) ({subject_id})..."
            )

        # Execute with timeout
        try:
            # Get host paths for Docker-in-Docker mounting
            # When worker runs inside Docker and spawns FreeSurfer Docker container,
            # we need to mount HOST paths, not container paths
            host_upload_dir = os.getenv('HOST_UPLOAD_DIR')
            host_output_dir = os.getenv('HOST_OUTPUT_DIR')
            
            # Auto-detect host paths by inspecting our own container
            if not host_upload_dir or not host_output_dir:
                try:
                    import json
                    # Inspect our own container to find volume mount sources
                    inspect_result = subprocess_module.run(
                        ["docker", "inspect", os.uname().nodename],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if inspect_result.returncode == 0:
                        container_info = json.loads(inspect_result.stdout)[0]
                        for mount in container_info.get('Mounts', []):
                            dest = mount.get('Destination')
                            source = mount.get('Source')
                            if dest == '/data' and not host_upload_dir:
                                host_upload_dir = f"{source}/uploads"
                                host_output_dir = f"{source}/outputs"
                                logger.info("auto_detected_host_paths",
                                          upload_dir=host_upload_dir,
                                          output_dir=host_output_dir)
                                break
                except Exception as e:
                    logger.warning("failed_to_auto_detect_host_paths", error=str(e))
            
            # If host paths are set (Docker-in-Docker mode), use them
            # Don't check exists() - we can't verify host paths from inside container!
            if host_upload_dir and host_upload_dir.strip():
                abs_input_dir = host_upload_dir
                logger.info("using_host_upload_path", path=abs_input_dir)
            else:
                # Fallback - use container paths
                abs_input_dir = str(nifti_path.parent.resolve())
                logger.info("using_container_upload_path", path=abs_input_dir)
            
            if host_output_dir and host_output_dir.strip():
                # For Docker-in-Docker, include the job_id subdirectory in host path
                abs_freesurfer_dir = f"{host_output_dir}/{self.job_id}/freesurfer/freesurfer_docker"
                logger.info("using_host_output_path", path=abs_freesurfer_dir)
            else:
                # Fallback - use container paths
                abs_freesurfer_dir = freesurfer_dir.resolve()
                logger.info("using_container_output_path", path=str(abs_freesurfer_dir))
            
            # Handle license path for Docker-in-Docker
            # Check if license is mounted from host (look for HOST_LICENSE_PATH or detect from container inspect)
            if host_upload_dir:  # Docker-in-Docker mode detected
                # Try to detect host license path from Docker inspect
                try:
                    import json
                    inspect_result = subprocess_module.run(
                        ["docker", "inspect", os.uname().nodename],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if inspect_result.returncode == 0:
                        container_info = json.loads(inspect_result.stdout)[0]
                        for mount in container_info.get('Mounts', []):
                            if mount.get('Destination') == '/app/license.txt':
                                abs_license_path = mount.get('Source')
                                logger.info("detected_host_license_path", path=abs_license_path)
                                break
                        else:
                            # License mount not found, use container path
                            abs_license_path = str(license_path.resolve())
                            logger.warning("license_mount_not_detected_using_container_path", path=abs_license_path)
                    else:
                        abs_license_path = str(license_path.resolve())
                except Exception as e:
                    logger.warning("failed_to_detect_license_host_path", error=str(e))
                    abs_license_path = str(license_path.resolve())
            else:
                # Native mode - use container path
                abs_license_path = str(license_path.resolve())
            
            # Use a unique container name so we can track and kill it if needed
            container_name = f"{settings.freesurfer_container_prefix}{self.job_id}"

            # ENFORCE CONTAINER CONCURRENCY LIMIT
            self._check_container_concurrency_limit()

            # Get current user ID and group ID for universal compatibility
            import getpass
            import grp

            current_user = getpass.getuser()
            current_uid = os.getuid()
            current_gid = os.getgid()

            logger.info("freesurfer_container_running_as_root",
                       note="FreeSurfer container runs as root for compatibility, ownership fixed by post-processing")

            print(f"DEBUG: ===== LAUNCHING FREESURFER CONTAINER =====")
            print(f"DEBUG: Container name: {container_name}")
            print(f"DEBUG: Input file: {nifti_path} (exists: {nifti_path.exists()})")
            print(f"DEBUG: Input file size: {os.path.getsize(nifti_path) if os.path.exists(nifti_path) else 'N/A'}")
            print(f"DEBUG: FreeSurfer dir: {abs_freesurfer_dir}")
            print(f"DEBUG: Subject ID: {subject_id}")
            print(f"DEBUG: License path: {abs_license_path} (exists: {os.path.exists(abs_license_path) if isinstance(abs_license_path, str) else abs_license_path.exists()})")
            print(f"DEBUG: Input dir: {abs_input_dir}")
            print(f"DEBUG: Output dir: {abs_freesurfer_dir}")

            # Provide a minimal hostname script to avoid missing binary/glibc mismatches
            import tempfile
            hostname_script_path = Path(tempfile.gettempdir()) / "ni-hostname"
            try:
                hostname_script_path.write_text("#!/bin/sh\n\necho \"${HOSTNAME:-localhost}\"\n")
                hostname_script_path.chmod(0o755)
            except Exception as script_error:
                logger.warning("failed_to_prepare_hostname_script", path=str(hostname_script_path), error=str(script_error))
            hostname_mount = ["-v", f"{hostname_script_path}:/usr/bin/hostname:ro"]

            # Use traditional FreeSurfer recon-all command format
            docker_cmd = [
                "docker", "run", "--user", "root",  # Run as root to avoid nonroot user issues
                "--name", container_name,  # Named container for tracking
                # Removed memory limits - let FreeSurfer use what it needs (system has 30GB available)
                "-v", f"{abs_freesurfer_dir}:/subjects",
                "-v", f"{abs_input_dir}:/input:ro",
                "-v", f"{abs_license_path}:/usr/local/freesurfer/license.txt:ro",
                *hostname_mount,
                "-e", "FS_LICENSE=/usr/local/freesurfer/license.txt",
                "-e", "SUBJECTS_DIR=/subjects",
                "-e", "PATH=/usr/bin:/usr/local/bin:$PATH",
                "-e", "ANTSPATH=/usr/local/freesurfer/bin",
                "-e", "HOSTNAME=localhost",  # Set hostname environment variable
                *self._get_freesurfer_thread_env("-e"),
                FREESURFER_CONTAINER_IMAGE,
                "/bin/bash", "-c",
                f"source /usr/local/freesurfer/FreeSurferEnv.sh && recon-all -i /input/{nifti_path.name} -s {subject_id} -autorecon1 -autorecon2-volonly",
            ]

            print(f"DEBUG: Full Docker command: {' '.join(docker_cmd)}")
            print(f"DEBUG: Input file exists: {nifti_path.exists()}")
            print(f"DEBUG: License file exists: {os.path.exists(abs_license_path) if isinstance(abs_license_path, str) else abs_license_path.exists()}")

            # Store container name in database for cancellation support
            self._store_container_id(container_name)

            logger.info("executing_freesurfer_docker_combined_autorecon",
                       command=" ".join(docker_cmd),
                       subject_id=subject_id,
                       timeout_minutes=FREESURFER_PROCESSING_TIMEOUT_MINUTES)

            # Start progress monitoring
            status_log_path = subject_output_dir / "scripts" / "recon-all-status.log"
            # Convert to absolute path so monitor thread can find it reliably
            abs_status_log_path = status_log_path.resolve()
            progress_monitor = self._start_freesurfer_progress_monitor(
                abs_status_log_path,
                base_progress=self._get_current_progress(),
                end_progress=90
            )

            logger.info("freesurfer_docker_starting_combined_autorecon",
                       command=" ".join(docker_cmd))

            print(f"DEBUG: About to run Docker command for job {self.job_id}")
            print(f"DEBUG: Full command: {' '.join(docker_cmd)}")

            logger.info(
                "freesurfer_container_lifecycle_start",
                container=container_name,
                job_id=str(self.job_id),
                subject_id=subject_id,
            )

            # Clean up any leftover containers from previous failed runs
            try:
                self._cleanup_job_containers()
                print(f"DEBUG: Cleaned up any leftover containers")
            except Exception as cleanup_error:
                print(f"DEBUG: Cleanup warning: {cleanup_error}")

            # Start resource sampling while the container runs
            sampler_stop_event, sampler_thread = self._start_resource_sampling(
                container_name,
                subject_output_dir,
                interval_seconds=30,
            )
            self._resource_sampler_stop_event = sampler_stop_event
            self._resource_sampler_thread = sampler_thread

            # Capture output to debug Docker issues
            print(f"DEBUG: Executing Docker command now...")
            try:
                result = subprocess_module.run(
                    docker_cmd,
                    capture_output=True,  # Capture output for debugging
                    timeout=FREESURFER_PROCESSING_TIMEOUT_MINUTES*60,
                    env=self._get_extended_env()
                )
                print(f"DEBUG: Docker command completed with return code: {result.returncode}")
                logger.info(
                    "freesurfer_container_lifecycle_exit",
                    container=container_name,
                    job_id=str(self.job_id),
                    returncode=result.returncode,
                )
            except Exception as docker_exec_error:
                sampler_stop_event.set()
                sampler_thread.join(timeout=2)
                self._resource_sampler_stop_event = None
                self._resource_sampler_thread = None
                print(f"DEBUG: Docker command execution failed: {docker_exec_error}")
                # Attempt to capture container artifacts before raising
                self._capture_container_failure_artifacts(container_name, subject_output_dir)
                raise docker_exec_error
            finally:
                sampler_stop_event.set()
                sampler_thread.join(timeout=2)
                self._resource_sampler_stop_event = None
                self._resource_sampler_thread = None

            print(f"DEBUG: Docker command completed with exit code: {result.returncode}")
            print(f"DEBUG: Command executed successfully (output not captured to avoid memory issues)")

            if result.returncode != 0:
                stderr_output = result.stderr.decode() if result.stderr else ""
                stdout_output = result.stdout.decode() if result.stdout else ""

                # Extract more detailed error information
                error_details = []
                if "license" in stderr_output.lower():
                    error_details.append("FreeSurfer license issue - check license.txt file")
                if "no such file" in stderr_output.lower():
                    error_details.append("Input file not found in container")
                if "permission denied" in stderr_output.lower():
                    error_details.append("Docker permission issue - check user permissions")
                if "no space left" in stderr_output.lower():
                    error_details.append("Insufficient disk space for processing")

                detailed_error = "; ".join(error_details) if error_details else "Check Docker logs for details"

                error_msg = f"FreeSurfer Docker failed (exit code: {result.returncode}). {detailed_error}"
                if stderr_output:
                    error_msg += f" STDERR: {stderr_output[:300]}..."

                self._write_docker_failure_output(
                    subject_output_dir,
                    container_name,
                    stdout_output,
                    stderr_output,
                )

                # Capture container logs/state before cleanup
                self._capture_container_failure_artifacts(container_name, subject_output_dir)

                # DEBUG: Print stderr to console
                print(f"DEBUG: Docker stderr: {stderr_output}")
                print(f"DEBUG: Docker stdout: {stdout_output}")
                print(f"DEBUG: Return code: {result.returncode}")

                logger.error("freesurfer_docker_combined_autorecon_failed",
                           returncode=result.returncode,
                           stderr=stderr_output[:500],
                           stdout=stdout_output[:500],
                           error_details=error_details)

                # Clean up container even on failure
                try:
                    self._cleanup_job_containers()
                except Exception as cleanup_error:
                    logger.warning("failed_to_cleanup_container_on_error", error=str(cleanup_error))

                # Cleanup container after capturing artifacts
                self._cleanup_named_container(container_name)
                raise RuntimeError(error_msg)

            # Cleanup container on success
            self._cleanup_named_container(container_name)

            logger.info("freesurfer_docker_combined_autorecon_completed")

            # Now run mri_segstats to generate aseg.stats from aseg.auto.mgz
            subject_mri_dir = freesurfer_dir / subject_id / "mri"
            subject_stats_dir = freesurfer_dir / subject_id / "stats"
            subject_stats_dir.mkdir(exist_ok=True, parents=True)

            aseg_auto_mgz = subject_mri_dir / "aseg.auto.mgz"
            aseg_stats = subject_stats_dir / "aseg.stats"
            brain_mgz = subject_mri_dir / "brain.mgz"

            if aseg_auto_mgz.exists():
                # Run mri_segstats to generate aseg.stats
                # Reuse abs_freesurfer_dir and abs_license_path from earlier
                # (already calculated with Docker-in-Docker host path support)
                
                segstats_cmd = [
                    "docker", "run", "--rm",  # Removed user mapping - FreeSurfer needs to run as root
                    "-v", f"{abs_freesurfer_dir}:/subjects",
                    "-v", f"{abs_license_path}:/usr/local/freesurfer/license.txt:ro",
                    *hostname_mount,
                    "-e", "FS_LICENSE=/usr/local/freesurfer/license.txt",
                    "-e", "SUBJECTS_DIR=/subjects",
                    FREESURFER_CONTAINER_IMAGE,
                "/bin/bash", "-c",
                f" source /usr/local/freesurfer/FreeSurferEnv.sh && mri_segstats --seg /subjects/{subject_id}/mri/aseg.auto.mgz --excludeid 0 --sum /subjects/{subject_id}/stats/aseg.stats --i /subjects/{subject_id}/mri/brain.mgz"
                ]

                logger.info("running_docker_mri_segstats_after_combined_autorecon", command=" ".join(segstats_cmd))
                segstats_result = subprocess_module.run(
                    segstats_cmd,
                    capture_output=True,
                    timeout=300,  # 5 minutes for stats generation
                    env=self._get_extended_env()
                )

                if segstats_result.returncode != 0:
                    error_msg = segstats_result.stderr.decode()[:500] if segstats_result.stderr else "Unknown error"
                    logger.warning("docker_mri_segstats_failed_after_combined_autorecon",
                                 returncode=segstats_result.returncode,
                                 error=error_msg)
                    # Don't raise error - continue with processing, fallback will handle missing stats
                else:
                    logger.info("docker_mri_segstats_completed_after_combined_autorecon")
            else:
                logger.warning("aseg.auto.mgz_not_found_after_combined_autorecon_in_docker", path=str(aseg_auto_mgz))

            if result.returncode == 0:
                logger.info("freesurfer_docker_processing_completed", subject_id=subject_id)

                # Fix permissions for post-processing access (FreeSurfer runs as root)
                try:
                    import getpass
                    current_user = getpass.getuser()
                    logger.info("fixing_freesurfer_output_permissions",
                              freesurfer_dir=str(freesurfer_dir),
                              user=current_user)

                    # Ensure chown uses absolute paths
                    abs_freesurfer_dir = freesurfer_dir.resolve()

                    # Use sudo chown to fix ownership recursively
                    chown_result = subprocess_module.run(
                        ['sudo', 'chown', '-R', f'{current_user}:{current_user}', str(abs_freesurfer_dir)],
                        capture_output=True,
                        timeout=60,
                        env=self._get_extended_env()
                    )

                    if chown_result.returncode == 0:
                        logger.info("freesurfer_permissions_fixed_successfully",
                                  freesurfer_dir=str(freesurfer_dir))
                    else:
                        logger.warning("freesurfer_chown_failed",
                                     returncode=chown_result.returncode,
                                     error=chown_result.stderr.decode()[:200])

                except Exception as perm_error:
                    logger.warning("freesurfer_permission_fix_failed",
                                 error=str(perm_error),
                                 freesurfer_dir=str(freesurfer_dir))

                return freesurfer_dir

            else:
                error_msg = result.stderr.decode()[:500] if result.stderr else "Unknown error"
                logger.error("freesurfer_docker_autorecon2_failed",
                           returncode=result.returncode,
                           error=error_msg,
                           subject_id=subject_id)
                raise RuntimeError(f"FreeSurfer Docker autorecon2 failed: {error_msg}")

        except subprocess_module.TimeoutExpired:
            logger.error("freesurfer_docker_processing_timeout",
                        subject_id=subject_id,
                        timeout_minutes=FREESURFER_PROCESSING_TIMEOUT_MINUTES)
            raise RuntimeError(f"FreeSurfer Docker processing timed out after {FREESURFER_PROCESSING_TIMEOUT_MINUTES} minutes for {subject_id}")

    # _is_freesurfer_native_available method removed - native FreeSurfer support disabled

    def _check_freesurfer_runtime_availability(self) -> str:
        """Check which container runtime is available for FreeSurfer."""
        # Check Docker availability
        docker_available = self._is_docker_available()

        # Check Singularity availability and FreeSurfer image
        singularity_available = self._is_singularity_available() and self._find_freesurfer_singularity_image() is not None

        if docker_available and singularity_available:
            return "both"
        elif docker_available:
            return "docker"
        elif singularity_available:
            return "singularity"
        else:
            return "none"

    def _extract_freesurfer_hippocampus_data(self, freesurfer_dir: Path, subject_id: str) -> Dict[str, float]:
        """Extract hippocampus volumes from FreeSurfer aseg.stats."""
        stats_file = freesurfer_dir / subject_id / "stats" / "aseg.stats"

        if not stats_file.exists():
            logger.warning("freesurfer_stats_file_missing",
                          path=str(stats_file),
                          subject_id=subject_id)
            return {}

        volumes = {}
        try:
            with open(stats_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            label_name = parts[4]  # Structure name
                            volume_mm3 = float(parts[3])  # Volume in mm³

                            if "Left-Hippocampus" in label_name:
                                volumes['left_hippocampus'] = volume_mm3
                                logger.info("freesurfer_left_hippocampus_extracted",
                                           volume=volume_mm3, subject_id=subject_id)
                            elif "Right-Hippocampus" in label_name:
                                volumes['right_hippocampus'] = volume_mm3
                                logger.info("freesurfer_right_hippocampus_extracted",
                                           volume=volume_mm3, subject_id=subject_id)

        except Exception as e:
            logger.error("freesurfer_stats_parsing_failed",
                        error=str(e),
                        subject_id=subject_id,
                        stats_file=str(stats_file))
            return {}

        # Validate we got both hemispheres
        if len(volumes) < 2:
            logger.warning("freesurfer_incomplete_hippocampus_data",
                          extracted_volumes=volumes,
                          subject_id=subject_id)

        return volumes

    def _convert_freesurfer_to_fastsurfer_format(self, freesurfer_dir: Path, target_dir: Path) -> Path:
        """Convert FreeSurfer output for downstream processing."""
        subject_id = f"freesurfer_fallback_{self.job_id}"

        # Create output directory structure
        fs_dir = target_dir / str(self.job_id)
        fs_dir.mkdir(exist_ok=True)

        # Create stats directory
        fs_stats_dir = fs_dir / "stats"
        fs_stats_dir.mkdir(exist_ok=True)

        # Copy FreeSurfer stats (aseg.stats contains hippocampus data)
        freesurfer_stats = freesurfer_dir / subject_id / "stats" / "aseg.stats"
        if freesurfer_stats.exists():
            import shutil
            shutil.copy2(freesurfer_stats, fs_stats_dir / "aseg.stats")
            logger.info("freesurfer_stats_copied",
                       from_path=str(freesurfer_stats),
                       to_path=str(fs_stats_dir / "aseg.stats"))

        # Create mock subfield files for testing (FreeSurfer doesn't provide detailed subfields)
        self._create_mock_fastsurfer_subfields_from_hippocampus(fs_dir)

        return target_dir

    def _create_mock_fastsurfer_subfields_from_hippocampus(self, fs_dir: Path) -> None:
        """Create mock subfield files based on FreeSurfer whole hippocampus volumes."""
        # Read FreeSurfer volumes
        aseg_stats = fs_dir / "stats" / "aseg.stats"
        volumes = self._extract_freesurfer_hippocampus_data_from_file(aseg_stats)

        if not volumes:
            logger.warning("no_hippocampus_volumes_for_mock_subfields")
            return

        # Create mock subfield files (approximate distribution based on literature)
        # CA1: ~30%, CA3: ~10%, Subiculum: ~25%, DG: ~20%, etc.
        left_total = volumes.get('left_hippocampus', 0)
        right_total = volumes.get('right_hippocampus', 0)

        if left_total > 0:
            self._write_mock_subfield_stats(fs_dir, "lh", left_total)
        if right_total > 0:
            self._write_mock_subfield_stats(fs_dir, "rh", right_total)

        logger.info("mock_fastsurfer_subfields_created",
                   left_total=left_total,
                   right_total=right_total)

    def _extract_freesurfer_hippocampus_data_from_file(self, stats_file: Path) -> Dict[str, float]:
        """Extract hippocampus volumes directly from aseg.stats file."""
        if not stats_file.exists():
            return {}

        volumes = {}
        try:
            with open(stats_file, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            label_name = parts[4]
                            volume_mm3 = float(parts[3])

                            if "Left-Hippocampus" in label_name:
                                volumes['left_hippocampus'] = volume_mm3
                            elif "Right-Hippocampus" in label_name:
                                volumes['right_hippocampus'] = volume_mm3
        except Exception as e:
            logger.error("freesurfer_file_parsing_failed", error=str(e), file=str(stats_file))
            return {}

        return volumes

    def _write_mock_subfield_stats(self, fs_dir: Path, hemisphere: str, total_volume: float) -> None:
        """Write mock subfield statistics file."""
        # Approximate subfield volume distribution (based on literature)
        subfield_ratios = {
            'CA1': 0.30,      # Cornu Ammonis 1
            'CA3': 0.10,      # Cornu Ammonis 3
            'Subiculum': 0.25, # Subiculum
            'DG': 0.20,       # Dentate Gyrus
            'CA4': 0.08,      # Cornu Ammonis 4
            'SRLM': 0.04,     # Stratum radiatum lacunosum moleculare
            'Cyst': 0.03      # Cyst/Other
        }

        stats_content = f"""# Mock subfield stats for FreeSurfer fallback
# Total {hemisphere} hippocampus volume: {total_volume:.2f} mm³
# Generated from FreeSurfer whole hippocampus segmentation

"""

        for subfield, ratio in subfield_ratios.items():
            volume = total_volume * ratio
            stats_content += f"{hemisphere}-{subfield} {volume:.2f} mm³\n"

            # Write to standard output filename
        filename = f"{hemisphere}.hippoSfVolumes-T1.v21.txt"
        stats_file = fs_dir / "stats" / filename

        with open(stats_file, 'w') as f:
            f.write(stats_content)

        logger.info("mock_subfield_stats_written",
                   file=str(stats_file),
                   hemisphere=hemisphere,
                   total_volume=total_volume)

    def _run_freesurfer_singularity(self, nifti_path: Path, output_dir: Path) -> Path:
        logger.info("starting_freesurfer_singularity_fallback", input=str(nifti_path))

        subject_id = f"freesurfer_fallback_{self.job_id}"
        freesurfer_dir = output_dir / "freesurfer_fallback"
        freesurfer_dir.mkdir(exist_ok=True)

        # Check if FreeSurfer Singularity image is available
        singularity_image = self._find_freesurfer_singularity_image()
        if not singularity_image:
            raise RuntimeError("FreeSurfer Singularity image not found")

        # Get license path
        license_path = self._get_freesurfer_license_path()
        if not license_path:
            raise RuntimeError("FreeSurfer license not found")

        # Update progress
        if self.progress_callback:
            self.progress_callback(
                self._get_current_progress(),
                f"Processing with FreeSurfer (Singularity) ({subject_id})..."
            )

        # IMPORTANT: Clean up any existing subject directory to prevent "re-run existing subject" error
        subject_output_dir = freesurfer_dir / subject_id
        if subject_output_dir.exists():
            logger.warning("freesurfer_subject_dir_exists",
                          path=str(subject_output_dir),
                          message="Removing existing subject directory to allow recon-all -i to run")
            import shutil
            shutil.rmtree(subject_output_dir)

        # Execute with timeout
        try:
            singularity_cmd = [
                "apptainer", "exec",
                "--cleanenv",  # Clean environment
                "-B", f"{freesurfer_dir}:/subjects",
                "-B", f"{nifti_path.parent}:/input:ro",
                "-B", f"{license_path}:/usr/local/freesurfer/license.txt:ro",
                "--env", f"FS_LICENSE=/usr/local/freesurfer/license.txt",
                "--env", f"SUBJECTS_DIR=/subjects",
            *self._get_freesurfer_thread_env("--env"),
                str(singularity_image),
                "/bin/bash", "-c",
                f" recon-all -i /input/{nifti_path.name} -s {subject_id}",
                "-autorecon1",
                "-autorecon2-volonly",
            ]

            logger.info("executing_freesurfer_singularity_combined_autorecon",
                       command=" ".join(singularity_cmd),
                       subject_id=subject_id,
                       singularity_image=str(singularity_image),
                       timeout_minutes=FREESURFER_PROCESSING_TIMEOUT_MINUTES)

            # Start progress monitoring
            status_log_path = subject_output_dir / "scripts" / "recon-all-status.log"
            logger.info("starting_progress_monitor", log_path=str(status_log_path), log_exists=status_log_path.exists(), subject_dir=str(subject_output_dir))
            progress_monitor = self._start_freesurfer_progress_monitor(
                status_log_path,
                base_progress=self._get_current_progress(),
                end_progress=90
            )

            logger.info("freesurfer_singularity_starting_combined_autorecon",
                       command=" ".join(singularity_cmd))

            result = subprocess_module.run(
                singularity_cmd,
                capture_output=True,
                timeout=FREESURFER_PROCESSING_TIMEOUT_MINUTES*60,
                env=self._get_extended_env()
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode()[:500] if result.stderr else "Unknown error"
                logger.error("freesurfer_singularity_combined_autorecon_failed",
                           returncode=result.returncode,
                           error=error_msg)
                raise RuntimeError(f"FreeSurfer Singularity combined autorecon failed: {error_msg}")

            logger.info("freesurfer_singularity_combined_autorecon_completed")

            # Now run mri_segstats to generate aseg.stats from aseg.auto.mgz
            subject_mri_dir = freesurfer_dir / subject_id / "mri"
            subject_stats_dir = freesurfer_dir / subject_id / "stats"
            subject_stats_dir.mkdir(exist_ok=True, parents=True)

            aseg_auto_mgz = subject_mri_dir / "aseg.auto.mgz"
            aseg_stats = subject_stats_dir / "aseg.stats"
            brain_mgz = subject_mri_dir / "brain.mgz"

            if aseg_auto_mgz.exists():
                # Run mri_segstats to generate aseg.stats
                segstats_cmd = [
                    "apptainer", "exec",
                    "--cleanenv",
                    "-B", f"{freesurfer_dir}:/subjects",
                    "-B", f"{license_path}:/usr/local/freesurfer/license.txt:ro",
                    "--env", f"FS_LICENSE=/usr/local/freesurfer/license.txt",
                    "--env", f"SUBJECTS_DIR=/subjects",
            *self._get_freesurfer_thread_env("--env"),
                    str(singularity_image),
                    "/bin/bash", "-c",
                    f" mri_segstats --seg /subjects/{subject_id}/mri/aseg.auto.mgz --excludeid 0 --sum /subjects/{subject_id}/stats/aseg.stats --i /subjects/{subject_id}/mri/brain.mgz"
                ]

                logger.info("running_singularity_mri_segstats_after_combined_autorecon", command=" ".join(segstats_cmd))
                segstats_result = subprocess_module.run(
                    segstats_cmd,
                    capture_output=True,
                    timeout=300,  # 5 minutes for stats generation
                    env=self._get_extended_env()
                )

                if segstats_result.returncode != 0:
                    error_msg = segstats_result.stderr.decode()[:500] if segstats_result.stderr else "Unknown error"
                    logger.warning("singularity_mri_segstats_failed_after_combined_autorecon",
                                 returncode=segstats_result.returncode,
                                 error=error_msg)
                    # Don't raise error - continue with processing, fallback will handle missing stats
                else:
                    logger.info("singularity_mri_segstats_completed_after_combined_autorecon")
            else:
                logger.warning("aseg.auto.mgz_not_found_after_combined_autorecon_in_singularity", path=str(aseg_auto_mgz))

            if result.returncode == 0:
                logger.info("freesurfer_singularity_processing_completed", subject_id=subject_id)
                return freesurfer_dir

            else:
                error_msg = result.stderr.decode()[:500] if result.stderr else "Unknown error"
                logger.error("freesurfer_singularity_autorecon2_failed",
                           returncode=result.returncode,
                           error=error_msg,
                           subject_id=subject_id)
                raise RuntimeError(f"FreeSurfer Singularity autorecon2 failed: {error_msg}")

        except subprocess_module.TimeoutExpired:
            logger.error("freesurfer_singularity_processing_timeout",
                        subject_id=subject_id,
                        timeout_minutes=FREESURFER_PROCESSING_TIMEOUT_MINUTES)
            raise RuntimeError(f"FreeSurfer Singularity processing timed out after {FREESURFER_PROCESSING_TIMEOUT_MINUTES} minutes for {subject_id}")

    def _run_freesurfer_primary(self, nifti_path: Path) -> Path:
        """
        Run FreeSurfer as the primary segmentation method (FreeSurfer-only approach).

        This uses FreeSurfer-only processing for complete brain segmentation.
        """
        logger.info("running_freesurfer_primary_segmentation", input=str(nifti_path))

        freesurfer_dir = self.output_dir / "freesurfer"
        freesurfer_dir.mkdir(exist_ok=True)

        # Production mode only - no smoke test or mock data fallbacks

        # Check FreeSurfer availability and license before processing
        logger.info("checking_freesurfer_requirements")

        # Check for FreeSurfer license first
        license_path = self._get_freesurfer_license_path()
        if not license_path:
            error_msg = ("FreeSurfer license not found. Please place your FreeSurfer license.txt file in the same folder as the NeuroInsight application, or set the FREESURFER_LICENSE environment variable to point to your license file. "
                        "You can obtain a FreeSurfer license from: https://surfer.nmr.mgh.harvard.edu/registration.html")
            logger.error("freesurfer_license_not_found", error=error_msg)
            raise RuntimeError(f"FreeSurfer license required: {error_msg}")

        # Priority order: Docker (main) → Apptainer (fallback) → Mock data (final fallback)

        # Check if Docker is available (primary choice for most users)
        # First wait for any ongoing cleanup operations to complete
        self._wait_for_docker_cleanup_if_needed()

        # Use more robust checking to avoid transient daemon issues
        # This includes automatic waiting for cleanup operations
        docker_available = self._check_docker_available()
        if docker_available:
            logger.info("freesurfer_docker_available_using_as_primary")
            try:
                # Use Docker container as primary method
                return self._run_freesurfer_docker(nifti_path, freesurfer_dir, license_path)
            except RuntimeError as docker_error:
                # Check if this is a Docker availability error (not a processing error)
                if "Docker is not available" in str(docker_error):
                    logger.warning("freesurfer_docker_unavailable_falling_back",
                                 error=str(docker_error))
                    docker_available = False  # Force fallback to Apptainer
                else:
                    # This is a processing error, re-raise it
                    logger.error("freesurfer_docker_processing_error", error=str(docker_error))
                    raise
            except Exception as docker_error:
                # Treat any other Docker exception as a processing error, not a runtime absence
                logger.error("freesurfer_docker_processing_error", error=str(docker_error))
                raise

        # If Docker failed or was unavailable, try fallback options
        if not docker_available:
            logger.info("docker_unavailable_checking_fallbacks")

        # Check if Apptainer/Singularity containers are available (fallback for HPC/specialized systems)
        sif_path = self._find_freesurfer_sif()
        if sif_path:
            logger.info("freesurfer_apptainer_available_using_as_fallback", sif_path=str(sif_path))
            try:
                # Use Apptainer/Singularity container as fallback
                subject_id = f"freesurfer_apptainer_{self.job_id}"
                return self._run_freesurfer_singularity_local(nifti_path, freesurfer_dir, license_path, sif_path)
            except Exception as apptainer_error:
                logger.error("freesurfer_apptainer_failed_falling_back",
                           error=str(apptainer_error),
                           error_type=type(apptainer_error).__name__,
                           sif_path=str(sif_path),
                           nifti_path=str(nifti_path),
                           freesurfer_dir=str(freesurfer_dir))
                import traceback
                logger.error("freesurfer_apptainer_traceback",
                           traceback=traceback.format_exc())

        # No container runtimes available - fail with clear error and troubleshooting steps
        error_msg = (
            "FreeSurfer processing failed: No container runtimes available. "
            "NeuroInsight requires Docker (recommended) or Apptainer/Singularity for FreeSurfer processing.\n\n"
            "Troubleshooting steps:\n"
            "1. Ensure Docker is installed and running: 'sudo systemctl status docker'\n"
            "2. If Docker is stopped, start it: 'sudo systemctl start docker'\n"
            "3. Test Docker: 'docker run --rm hello-world'\n"
            "4. If Docker is unavailable, install Apptainer: 'sudo apt install apptainer'\n"
            "5. For WSL users, ensure Docker Desktop is running with WSL integration enabled\n\n"
            "Note: This error may occur due to temporary Docker daemon issues. "
            "Try restarting the job after ensuring Docker is fully operational."
        )
        logger.error("freesurfer_no_containers_available",
                   error=error_msg,
                   docker_available=docker_available,
                   apptainer_available=bool(sif_path))
        raise RuntimeError(error_msg)

        logger.info("freesurfer_requirements_met", license_path=str(license_path))

        # Run FreeSurfer segmentation directly
        logger.info("starting_freesurfer_primary_processing")

        try:
            # Use the existing FreeSurfer fallback method as primary
            result_dir = self._run_freesurfer_fallback(nifti_path, freesurfer_dir.parent)

            # Convert to consistent output format
            self._convert_freesurfer_to_fastsurfer_format(result_dir, freesurfer_dir)

            logger.info("freesurfer_primary_processing_successful")
            return freesurfer_dir

        except Exception as freesurfer_error:
            logger.error("freesurfer_primary_processing_failed",
                        error=str(freesurfer_error),
                        error_type=type(freesurfer_error).__name__)

            # Production: Fail with clear error message - no mock data fallback
            raise RuntimeError(f"FreeSurfer processing failed: {str(freesurfer_error)}")


    def _find_freesurfer_singularity_image(self) -> Path:
        """Find the FreeSurfer Singularity image."""
        # Check configured path first
        if hasattr(settings, 'freesurfer_singularity_image_path'):
            img_path = Path(settings.freesurfer_singularity_image_path)
            if img_path.exists():
                logger.info("found_configured_freesurfer_singularity_image", path=str(img_path))
                return img_path

        # Check current working directory containers first (for development)
        cwd_container = Path.cwd() / "containers" / "freesurfer.sif"
        if cwd_container.exists():
            logger.info("found_cwd_freesurfer_singularity_image", path=str(cwd_container))
            return cwd_container

        # Check app-bundled containers directory (for deployed apps)
        try:
            app_root = self._get_app_root_directory()
            app_container = app_root / "containers" / "freesurfer.sif"
            if app_container.exists():
                logger.info("found_app_bundled_freesurfer_singularity_image", path=str(app_container))
                return app_container
        except:
            pass  # Ignore app root detection failures

        # Check common locations for FreeSurfer Singularity images
        common_locations = [
            # User-specific locations
            Path.home() / "Documents/containers/freesurfer_latest.sif",
            Path.home() / "containers/freesurfer_latest.sif",
            Path.home() / ".singularity/cache/freesurfer_latest.sif",

            # Shared/HPC locations
            Path("/shared/containers/freesurfer_latest.sif"),
            Path("/opt/containers/freesurfer_latest.sif"),
            Path("/opt/hpc/containers/freesurfer_latest.sif"),
            Path("/cm/shared/containers/freesurfer_latest.sif"),
            Path("/scratch/containers/freesurfer_latest.sif"),
            Path("/project/containers/freesurfer_latest.sif"),

            # System-wide locations
            Path("/usr/local/singularity/images/freesurfer_latest.sif"),
            Path("/opt/singularity/images/freesurfer_latest.sif"),
        ]

        for img_path in common_locations:
            if img_path.exists():
                logger.info("found_freesurfer_singularity_image", path=str(img_path))
                return img_path

        # No existing images found - try automatic download
        logger.info("no_freesurfer_singularity_images_found_attempting_download")
        downloaded_image = self._ensure_singularity_container()
        if downloaded_image and downloaded_image.exists():
            logger.info("freesurfer_singularity_download_successful", path=str(downloaded_image))
            return downloaded_image

        logger.warning("freesurfer_singularity_image_not_found_and_download_failed")
        return None

    def _find_singularity_image(self) -> Path:
        """
        Find the FreeSurfer Singularity image.

        Returns:
            Path to the Singularity image if found, None otherwise
        """
        # Check configured path first
        if hasattr(settings, 'singularity_image_path'):
            img_path = Path(settings.singularity_image_path)
            if img_path.exists():
                logger.info("found_configured_singularity_image", path=str(img_path))
                return img_path

        # Check common locations for Singularity images
        common_locations = [
            # User-specific locations
            Path.home() / "Documents/containers/fastsurfer_latest.sif",
            Path.home() / "containers/fastsurfer_latest.sif",
            Path.home() / ".singularity/cache/fastsurfer_latest.sif",

            # Shared/HPC locations
            Path("/shared/containers/fastsurfer_latest.sif"),
            Path("/opt/containers/fastsurfer_latest.sif"),
            Path("/opt/hpc/containers/fastsurfer_latest.sif"),
            Path("/cm/shared/containers/fastsurfer_latest.sif"),
            Path("/scratch/containers/fastsurfer_latest.sif"),
            Path("/project/containers/fastsurfer_latest.sif"),

            # System-wide locations
            Path("/usr/local/share/singularity/images/fastsurfer_latest.sif"),
            Path("/var/lib/singularity/images/fastsurfer_latest.sif"),

            # Alternative naming patterns
            Path("/shared/containers/fastsurfer.sif"),
            Path("/opt/containers/fastsurfer.sif"),
        ]

        for location in common_locations:
            if location.exists():
                logger.info("found_singularity_image", path=str(location))
                return location

        logger.info("singularity_image_not_found")
        return None


    def _run_fastsurfer(self, nifti_path: Path) -> Path:
        """
        Run FreeSurfer segmentation using Docker.

        Executes FreeSurfer container for whole brain segmentation.
        In smoke test mode, immediately returns mock data for faster CI testing.

        Args:
            nifti_path: Path to input NIfTI file

        Returns:
            Path to FreeSurfer output directory

        Raises:
            DockerNotAvailableError: If Docker is not installed or not running
        """
        logger.info("running_fastsurfer_docker", input=str(nifti_path))

        freesurfer_dir = self.output_dir / "fastsurfer"
        freesurfer_dir.mkdir(exist_ok=True)

        # Smoke test mode: Skip Docker and create mock output immediately
        # Production mode only - no smoke test or mock data fallbacks

        # Smart Container Runtime Selection with Automatic Fallback
        # Strategy: Try preferred runtime first, fallback to alternatives if available

        container_runtime = self._check_container_runtime_availability()
        attempted_runtimes = []

        # Primary attempt with selected runtime
        if container_runtime == "docker":
            logger.info("attempting_docker_as_primary_runtime")
            attempted_runtimes.append("docker")
            try:
                return self._run_fastsurfer_docker(nifti_path, freesurfer_dir)
            except Exception as docker_error:
                logger.warning("docker_execution_failed", error=str(docker_error), error_type=type(docker_error).__name__)
                # Docker failed - try Singularity fallback if available
                singularity_available = self._is_singularity_available()
                logger.info("checking_singularity_for_fallback", available=singularity_available)
                if singularity_available:
                    logger.info("docker_failed_trying_singularity_fallback")
                    attempted_runtimes.append("singularity")
                    try:
                        return self._run_fastsurfer_singularity(nifti_path, freesurfer_dir)
                    except Exception as sing_error:
                        logger.warning("singularity_fallback_failed", error=str(sing_error), error_type=type(sing_error).__name__)
                else:
                    logger.warning("singularity_not_available_for_fallback")

        elif container_runtime == "singularity":
            logger.info("attempting_singularity_as_primary_runtime")
            attempted_runtimes.append("singularity")
            try:
                return self._run_fastsurfer_singularity(nifti_path, freesurfer_dir)
            except Exception as sing_error:
                logger.warning("singularity_execution_failed", error=str(sing_error))
                # Singularity failed - try Docker fallback if available
                if self._is_docker_available():
                    logger.info("singularity_failed_trying_docker_fallback")
                    attempted_runtimes.append("docker")
                    try:
                        return self._run_fastsurfer_docker(nifti_path, freesurfer_dir)
                    except Exception as docker_error:
                        logger.warning("docker_fallback_failed", error=str(docker_error))

        # ===== FREESURFER FALLBACK =====
        # If container execution failed, fall back to mock data
        if self._is_freesurfer_available():
            logger.info("fastsurfer_failed_trying_freesurfer_fallback")
            try:
                freesurfer_result_dir = self._run_freesurfer_fallback(nifti_path, freesurfer_dir.parent)

                # Use FreeSurfer output directly
                compatible_dir = self._convert_freesurfer_to_fastsurfer_format(
                    freesurfer_result_dir, freesurfer_dir
                )

                logger.info("freesurfer_fallback_successful")
                return compatible_dir

            except Exception as freesurfer_error:
                logger.error("freesurfer_fallback_failed",
                           fastsurfer_error=str(freesurfer_error),
                           freesurfer_error=str(freesurfer_error))

        # All segmentation methods failed - fail with clear error
        error_msg = (
            f"All segmentation methods failed: {attempted_runtimes}. "
            "Neither FastSurfer nor FreeSurfer could process the input file. "
            "Please ensure the NIfTI file is valid and compatible with brain segmentation tools."
        )
        logger.error("all_segmentation_methods_failed", error=error_msg, attempted_runtimes=attempted_runtimes)
        raise RuntimeError(error_msg)

    def _run_fastsurfer_docker(self, nifti_path: Path, freesurfer_dir: Path) -> Path:
        """
        Run FreeSurfer using Docker.

        Args:
            nifti_path: Path to input NIfTI file
            freesurfer_dir: Output directory

        Returns:
            Path to FreeSurfer output directory
        """
        try:
            result = subprocess_module.run(
                ["docker", "images", "-q", "deepmi/fastsurfer:latest"],
                capture_output=True,
                timeout=10
            )
            if not result.stdout.strip():
                # Image not found - need to download
                logger.info("fastsurfer_image_not_found", message="Will download FastSurfer image")
                if self.progress_callback:
                    self.progress_callback(
                        15,
                        "Downloading FreeSurfer container (4GB, first time only - takes 10-15 min)..."
                    )
                
                # Pull the image
                logger.info("pulling_fastsurfer_image")
                # Use the same extended PATH environment for consistency
                env = os.environ.copy()
                current_path = env.get('PATH', '')
                # Add common Docker locations to PATH
                import getpass
                user_home = os.path.expanduser('~')
                docker_paths = [
                    f'{user_home}/bin',  # User's bin directory
                    '/usr/local/bin',     # Common alternative location
                    '/usr/bin',           # System default
                    '/bin',               # Fallback
                    '/opt/bin',           # Optional packages
                    '/snap/bin',          # Snap packages
                ]
                extended_path = current_path
                for path in docker_paths:
                    if path not in current_path:
                        extended_path = f"{path}:{extended_path}"
                env['PATH'] = extended_path

                # Use enhanced Docker download with progress messages
                try:
                    self._download_docker_image_with_progress(
                        "deepmi/fastsurfer:latest",
                        "FastSurfer",
                        env
                    )
                except subprocess_module.CalledProcessError as e:
                    logger.error("fastsurfer_pull_failed", error=str(e))
                    raise RuntimeError(
                        f"Failed to download FreeSurfer container: {str(e)}\n\n"
                        "Please check your internet connection and try again."
                    )
                
                logger.info("fastsurfer_image_downloaded", message="FastSurfer model ready")
        except subprocess_module.TimeoutExpired:
            raise RuntimeError(
                "Downloading FreeSurfer container timed out. "
                "Please check your internet connection and try again."
            )
        
        try:
            # Use CPU processing
            device = "cpu"
            runtime_arg = ""

            # Determine optimal thread count for CPU processing
            import os
            cpu_count = os.cpu_count() or 4
            num_threads = max(1, cpu_count - 2)  # Leave 2 cores free
            
            # Get host paths for Docker-in-Docker mounting
            # When worker runs inside Docker and spawns FastSurfer Docker container,
            # we need to mount HOST paths, not container paths
            host_upload_dir = os.getenv('HOST_UPLOAD_DIR')
            host_output_dir = os.getenv('HOST_OUTPUT_DIR')
            
            # If not set, try to auto-detect from Docker inspect
            if not host_upload_dir or not host_output_dir:
                try:
                    import json
                    
                    # Get our own container info
                    # Use the same extended PATH environment for consistency
                    env = os.environ.copy()
                    current_path = env.get('PATH', '')
                    # Add common Docker locations to PATH
                    import getpass
                    user_home = os.path.expanduser('~')
                    docker_paths = [
                        f'{user_home}/bin',  # User's bin directory
                        '/usr/local/bin',     # Common alternative location
                        '/usr/bin',           # System default
                        '/bin',               # Fallback
                        '/opt/bin',           # Optional packages
                        '/snap/bin',          # Snap packages
                    ]
                    extended_path = current_path
                    for path in docker_paths:
                        if path not in current_path:
                            extended_path = f"{path}:{extended_path}"
                    env['PATH'] = extended_path

                    result = subprocess_module.run(
                        ['docker', 'inspect', os.uname().nodename],
                        capture_output=True,
                        text=True,
                        check=True,
                        env=env
                    )
                    container_info = json.loads(result.stdout)[0]
                    
                    # Extract mount sources from our container
                    for mount in container_info.get('Mounts', []):
                        dest = mount.get('Destination', '')
                        if dest == '/data/uploads' and not host_upload_dir:
                            host_upload_dir = mount.get('Source')
                        elif dest == '/data/outputs' and not host_output_dir:
                            host_output_dir = mount.get('Source')
                    
                    logger.info(
                        "auto_detected_host_paths",
                        upload_dir=host_upload_dir,
                        output_dir=host_output_dir
                    )
                except Exception as e:
                    logger.warning(
                        "host_path_detection_failed",
                        error=str(e),
                        note="Falling back to configured desktop paths"
                    )
                    host_upload_dir = host_upload_dir or ''
                    host_output_dir = host_output_dir or ''
            else:
                logger.info(
                    "using_configured_host_paths",
                    upload_dir=host_upload_dir,
                    output_dir=host_output_dir
                )

            # If host paths are still unset or point to placeholder mount locations,
            # fall back to the actual desktop storage directories.
            if not host_upload_dir or not Path(host_upload_dir).exists() or host_upload_dir == "/data/uploads":
                host_upload_dir = str(Path(settings.upload_dir).resolve())

            if not host_output_dir or not Path(host_output_dir).exists() or host_output_dir == "/data/outputs":
                host_output_dir = str(Path(settings.output_dir).resolve())

            logger.info(
                "resolved_host_paths",
                upload_dir=host_upload_dir,
                output_dir=host_output_dir
            )
            
            # Calculate relative paths from host perspective
            # nifti_path is like /data/uploads/file.nii (inside worker container)
            # We need to translate to host path
            input_host_path = host_upload_dir
            output_host_path = f"{host_output_dir}/{self.job_id}/fastsurfer"
            
            # Build Docker command
            cmd = ["docker", "run", "--rm"]
            
            allow_root = False
            force_root = os.getenv("FASTSURFER_FORCE_ROOT") == "1"
            # Add GPU support if available
            if runtime_arg:
                cmd.extend(runtime_arg.split())
            
            # On Windows or when force_root is set, FastSurfer image defaults to user "nonroot"
            # which cannot read NTFS-mounted paths. Override to root and allow root exec.
            force_root_reason = None
            if platform.system() == "Windows" or force_root:
                cmd.extend(["--user", "root"])
                allow_root = True
                force_root_reason = (
                    "windows_platform" if platform.system() == "Windows" else "forced_by_env"
                )
            
            # Add volume mounts with HOST paths
            cmd.extend([
                "-v", f"{input_host_path}:/input:ro",
                "-v", f"{output_host_path}:/output",
                "deepmi/fastsurfer:latest",
                "--t1", f"/input/{nifti_path.name}",
                "--sid", str(self.job_id),
                "--sd", "/output",
                "--seg_only",  # Only segmentation, skip surface reconstruction
                "--device", device,
                "--batch", "1",
                "--threads", str(num_threads),
                "--viewagg_device", "cpu",
            ])

            if allow_root:
                logger.info(
                    "forcing_root_user_for_fastsurfer",
                    reason=force_root_reason,
                    platform=platform.system(),
                )
                cmd.append("--allow_root")
            
            if device == "cpu":
                logger.info(
                    "cpu_threading_enabled",
                    threads=num_threads,
                    total_cores=cpu_count,
                    note=f"Using {num_threads} threads for CPU processing"
                )
            
            logger.info(
                "executing_fastsurfer",
                command=" ".join(cmd),
                note="Running FastSurfer with Docker"
            )
            
            # Use the same extended PATH environment for consistency
            env = os.environ.copy()
            current_path = env.get('PATH', '')
            # Add common Docker locations to PATH
            import getpass
            user_home = os.path.expanduser('~')
            docker_paths = [
                f'{user_home}/bin',       # User's bin directory (most common)
                '/usr/local/bin',         # Manual installs, Homebrew (Linux)
                '/usr/bin',               # System default (apt, dnf, pacman, etc.)
                '/bin',                   # Fallback system path
                '/opt/bin',               # Optional packages
                '/snap/bin',              # Snap packages
                '/opt/docker-desktop/bin', # Docker Desktop for Linux
                '/opt/docker/bin',        # Alternative Docker installs
            ]
            extended_path = current_path
            for path in docker_paths:
                if path not in current_path:
                    extended_path = f"{path}:{extended_path}"
            env['PATH'] = extended_path

            # Use 7-hour timeout for all jobs
            fastsurfer_timeout = 25200  # 7 hours
            result = subprocess_module.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=fastsurfer_timeout,
                env=env
            )
            
            logger.info(
                "fastsurfer_completed",
                output_dir=str(freesurfer_dir),
                note="Brain segmentation complete"
            )
            
        except subprocess_module.TimeoutExpired:
            # FastSurfer timed out - fail with clear error
            error_msg = (
                "FastSurfer processing timed out. "
                "The segmentation process took too long to complete. "
                "This may indicate issues with the input file or system resources."
            )
            logger.error("fastsurfer_timeout", error=error_msg)
            raise RuntimeError(error_msg)
        
        except subprocess_module.CalledProcessError as e:
            # Docker command failed - comprehensive error checking for Singularity fallback
            stderr_lower = (e.stderr or "").lower() if hasattr(e, 'stderr') else ""
            stdout_lower = (e.stdout or "").lower() if hasattr(e, 'stdout') else ""

            # Check for various Docker failure modes that should trigger Singularity fallback
            docker_failure_indicators = [
                "cannot connect to the docker daemon",
                "docker daemon is not running",
                "permission denied",
                "no such file or directory",
                "docker: command not found",
                "cannot apply additional memory protection",
                "error while loading shared libraries",
                "connection refused",
                "timeout",
            ]

            should_try_singularity = any(indicator in stderr_lower or indicator in stdout_lower
                                       for indicator in docker_failure_indicators)

            if should_try_singularity:
                logger.warning(
                    "docker_failed_trying_singularity",
                    error=str(e),
                    stderr=e.stderr if hasattr(e, 'stderr') else "No stderr",
                    returncode=e.returncode,
                )
                try:
                    return self._run_fastsurfer_singularity(nifti_path, freesurfer_dir)
                except Exception as sing_error:
                    # Both Docker and Singularity failed - fail with clear error
                    error_msg = (
                        f"FastSurfer processing failed: Docker error: {str(e)}, "
                        f"Singularity error: {str(sing_error)}. "
                        "Both container runtimes failed to execute FastSurfer."
                    )
                    logger.error("both_container_runtimes_failed", error=error_msg)
                    raise RuntimeError(error_msg)

            # Docker command succeeded but returned error - log and try Singularity anyway
            logger.error(
                "fastsurfer_execution_failed_trying_singularity",
                error=str(e),
                stderr=e.stderr if hasattr(e, 'stderr') and e.stderr else "No stderr",
                stdout=e.stdout if hasattr(e, 'stdout') and e.stdout else "No stdout",
                returncode=e.returncode,
            )

            # Try Singularity as fallback for any Docker failure
            logger.info("trying_singularity_fallback_after_docker_failure")
            try:
                return self._run_fastsurfer_singularity(nifti_path, freesurfer_dir)
            except Exception as sing_error:
                # Singularity fallback failed - fail with clear error
                error_msg = (
                    f"FastSurfer processing failed: Singularity fallback error: {str(sing_error)}. "
                    "Both Docker and Singularity failed to execute FastSurfer."
                )
                logger.error("singularity_fallback_failed", error=error_msg)
                raise RuntimeError(error_msg)
        
        except Exception as e:
            logger.error(
                "fastsurfer_unexpected_error",
                error=str(e),
                error_type=type(e).__name__
            )
            # Unexpected error - fail with clear error message
            error_msg = f"FastSurfer processing failed with unexpected error: {str(e)}"
            logger.error("fastsurfer_unexpected_error", error=error_msg, error_type=type(e).__name__)
            raise RuntimeError(error_msg)
        
        return freesurfer_dir
    
    def _run_fastsurfer_docker(self, nifti_path: Path, freesurfer_dir: Path) -> Path:
        """
        Run FreeSurfer using Docker.

        Args:
            nifti_path: Path to input NIfTI file
            freesurfer_dir: Output directory

        Returns:
            Path to FreeSurfer output directory

        Raises:
            RuntimeError: If Docker execution fails
        """
        logger.info("running_fastsurfer_docker", input=str(nifti_path))

        # Check if FastSurfer image is downloaded
        try:
            result = subprocess_module.run(
                ["docker", "images", "-q", "deepmi/fastsurfer:latest"],
                capture_output=True,
                timeout=10
            )
            if not result.stdout.strip():
                # Image not found - need to download
                logger.info("fastsurfer_image_not_found", message="Will download FastSurfer image")
                if self.progress_callback:
                    self.progress_callback(
                        15,
                        "Downloading FreeSurfer container (4GB, first time only - takes 10-15 min)..."
                    )

                # Pull the image
                logger.info("pulling_fastsurfer_image")
                env = os.environ.copy()
                current_path = env.get('PATH', '')
                extended_path = f"/usr/local/bin:/usr/bin:/bin:{current_path}"
                env['PATH'] = extended_path

                try:
                    # Use enhanced Docker download with progress messages
                    self._download_docker_image_with_progress(
                        "deepmi/fastsurfer:latest",
                        "FastSurfer",
                        env
                    )
                    logger.info("fastsurfer_image_downloaded_successfully")
                except subprocess_module.CalledProcessError as e:
                    logger.error("fastsurfer_image_download_failed", error=str(e))
                    raise RuntimeError(f"Failed to download FreeSurfer container: {str(e)}")
                except subprocess_module.TimeoutExpired:
                    logger.error("fastsurfer_image_download_timeout")
                    raise RuntimeError("FreeSurfer container download timed out")
            else:
                logger.info("fastsurfer_image_already_present")
        except subprocess_module.TimeoutExpired:
            logger.error("docker_image_check_timeout")
            raise RuntimeError("Docker image check timed out")
        except subprocess_module.CalledProcessError as e:
            logger.error("docker_image_check_failed", error=str(e))
            raise RuntimeError(f"Docker image check failed: {e}")

        # Use CPU processing
        device = "cpu"

        # Threading
        cpu_count = os.cpu_count() or 4
        num_threads = max(1, cpu_count - 2)

        # Build Docker command
        # Use absolute paths for Docker volume mounts
        abs_input_dir = nifti_path.parent.resolve()
        abs_freesurfer_dir = freesurfer_dir.resolve()
        
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{abs_input_dir}:/input:ro",
            "-v", f"{abs_freesurfer_dir}:/output",
        ]

        cmd.extend([
            "deepmi/fastsurfer:latest",
            "--t1", f"/input/{nifti_path.name}",
            "--sid", str(self.job_id),
            "--sd", "/output",
            "--seg_only",
            "--device", device,
            "--batch", "1",
            "--threads", str(num_threads),
            "--viewagg_device", "cpu",
        ])

        logger.info("cpu_threading_enabled",
                   threads=num_threads,
                   total_cores=cpu_count,
                   note=f"Using {num_threads} threads for CPU processing")

        logger.info("executing_fastsurfer_docker",
                   command=" ".join(cmd),
                   note="Running FastSurfer with Docker")

        # Execute Docker
        env = os.environ.copy()
        current_path = env.get('PATH', '')
        extended_path = f"/usr/local/bin:/usr/bin:/bin:{current_path}"
        env['PATH'] = extended_path

        try:
            result = subprocess_module.run(
                cmd,
                capture_output=True,
                timeout=self.docker_timeout,
                env=env
            )

            if result.returncode == 0:
                logger.info("fastsurfer_docker_completed", output_dir=str(freesurfer_dir))
                return freesurfer_dir
            else:
                logger.error("fastsurfer_docker_failed",
                           returncode=result.returncode,
                           stderr=result.stderr.decode()[:500] if result.stderr else "No stderr",
                           stdout=result.stdout.decode()[:500] if result.stdout else "No stdout")
                raise RuntimeError(f"FastSurfer Docker failed: {result.stderr.decode()}")
        except subprocess_module.TimeoutExpired:
            logger.error("fastsurfer_docker_timeout", timeout=self.docker_timeout)
            raise RuntimeError(f"FastSurfer Docker execution timed out after {self.docker_timeout} seconds")

    def _run_fastsurfer_singularity(self, nifti_path: Path, freesurfer_dir: Path) -> Path:
        """
        Run FreeSurfer using Singularity/Apptainer (fallback when Docker not available).
        
        Args:
            nifti_path: Path to input NIfTI file
            freesurfer_dir: Output directory
            
        Returns:
            Path to FreeSurfer output directory
        """
        import shutil
        import os
        import signal
        
        logger.info("running_fastsurfer_singularity", input=str(nifti_path))
        
        # Check for Singularity/Apptainer with extended PATH
        singularity_cmd = None
        env = os.environ.copy()
        current_path = env.get('PATH', '')

        # Add common Singularity/Apptainer locations to PATH
        user_home = os.path.expanduser('~')
        singularity_paths = [
            f'{user_home}/bin',
            '/usr/local/bin',
            '/usr/bin',
            '/bin',
            '/opt/bin',
            '/opt/singularity/bin',
            '/opt/apptainer/bin',
            '/usr/local/singularity/bin',
            '/usr/local/apptainer/bin',
            '/opt/modulefiles/bin',
            '/cm/shared/apps/singularity',
            '/shared/apps/singularity',
            '/opt/apps/singularity',
            '/opt/hpc/singularity',
        ]

        # Add configured Singularity bin path if specified
        if hasattr(settings, 'singularity_bin_path') and settings.singularity_bin_path:
            singularity_paths.insert(0, settings.singularity_bin_path)
            logger.info("added_configured_singularity_path", path=settings.singularity_bin_path)

        extended_path = current_path
        for path in singularity_paths:
            if path not in current_path:
                extended_path = f"{path}:{extended_path}"
        env['PATH'] = extended_path

        # Check for commands with extended PATH
        def check_command_with_path(cmd):
            try:
                result = subprocess_module.run(
                    ['which', cmd],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return True
            except (subprocess_module.TimeoutExpired, subprocess_module.CalledProcessError):
                pass
            return False

        if check_command_with_path("apptainer"):
            singularity_cmd = "apptainer"
        elif check_command_with_path("singularity"):
            singularity_cmd = "singularity"
        else:
            raise FileNotFoundError("Neither singularity nor apptainer found in PATH")
        
        # Find Singularity image
        singularity_img = Path(settings.singularity_image_path) if hasattr(settings, 'singularity_image_path') else None
        if not singularity_img or not singularity_img.exists():
            # Try common locations including HPC paths
            possible_paths = [
                # Relative to output directory
                Path(settings.output_dir).parent / "singularity-images" / "fastsurfer.sif",
                Path("./singularity-images/fastsurfer.sif"),

                # HPC/Shared locations
                Path("/shared/containers/fastsurfer_latest.sif"),
                Path("/opt/containers/fastsurfer_latest.sif"),
                Path("/opt/hpc/containers/fastsurfer_latest.sif"),
                Path("/cm/shared/containers/fastsurfer_latest.sif"),
                Path("/scratch/containers/fastsurfer_latest.sif"),
                Path("/project/containers/fastsurfer_latest.sif"),

                # Alternative naming
                Path("/shared/containers/fastsurfer.sif"),
                Path("/opt/containers/fastsurfer.sif"),
            ]
            for path in possible_paths:
                if path.exists():
                    singularity_img = path
                    break
        
        if not singularity_img or not singularity_img.exists():
            raise FileNotFoundError(f"FastSurfer Singularity image not found")
        
        logger.info("found_singularity_image", path=str(singularity_img))
        
        # Use CPU processing
        device = "cpu"

        # Threading
        cpu_count = os.cpu_count() or 4
        num_threads = max(1, cpu_count - 2)

        # Build Singularity command
        cmd = [singularity_cmd, "exec"]
        
        # Add bind mounts and environment
        cmd.extend([
            "--bind", f"{nifti_path.parent}:/input:ro",
            "--bind", f"{freesurfer_dir}:/output",
            "--env", "TQDM_DISABLE=1",
            "--cleanenv",
            str(singularity_img),
            "/fastsurfer/run_fastsurfer.sh",
            "--t1", f"/input/{nifti_path.name}",
            "--sid", str(self.job_id),
            "--sd", "/output",
            "--seg_only",
            "--device", device,
            "--batch", "1",
            "--threads", str(num_threads),
            "--viewagg_device", "cpu",
        ])
        
        logger.info(
            "cpu_threading_enabled",
            threads=num_threads,
            total_cores=cpu_count,
            note=f"Using {num_threads} threads for CPU parallel processing"
        )
        
        logger.info(
            "executing_fastsurfer_singularity",
            command=" ".join(cmd),
            note="Running FastSurfer with Singularity"
        )
        
        # Execute Singularity with proper process group management
        # Using Popen instead of run() to track PID and manage process group
        process = None
        try:
            # Create a new process group so we can kill all child processes
            # Use extended environment with Singularity PATH
            process = subprocess_module.Popen(
                cmd,
                stdout=subprocess_module.PIPE,
                stderr=subprocess_module.PIPE,
                text=True,
                env=env,  # Use environment with extended PATH for Singularity
                preexec_fn=os.setsid,  # Create new process group
            )
            
            # Store the process PID for cleanup tracking
            self._store_process_pid(process.pid)
            logger.info("process_started", pid=process.pid, pgid=os.getpgid(process.pid))
            
            # Wait for process with timeout
            try:
                stdout, stderr = process.communicate(timeout=25200)
                returncode = process.returncode
            except subprocess_module.TimeoutExpired:
                logger.warning("process_timeout_killing_group", pid=process.pid)
                # Kill entire process group
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=10)
                except:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                raise
            finally:
                self._clear_process_pid()
            
            if returncode != 0:
                logger.error(
                    "fastsurfer_singularity_failed",
                    returncode=returncode,
                    stderr=stderr[:500] if stderr else "No stderr",
                    stdout=stdout[:500] if stdout else "No stdout"
                )
                raise RuntimeError(f"FastSurfer Singularity failed: {stderr}")
            
            logger.info("fastsurfer_singularity_completed", output_dir=str(freesurfer_dir))
            return freesurfer_dir
            
        except Exception as e:
            # Ensure cleanup of process group on any error
            if process and process.poll() is None:
                logger.warning("cleaning_up_process_group_on_error", pid=process.pid)
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except:
                    pass
            self._clear_process_pid()
            raise
    

    def _create_mock_segmentation_files(self, mri_dir: Path) -> None:
        """
        Create mock segmentation files needed for visualization.

        Args:
            mri_dir: MRI directory to create files in
        """
        import numpy as np
        import nibabel as nib

        logger.info("creating_mock_segmentation_files")

        # Create a simple 3D brain-like volume (64x64x32) for mock data
        shape = (64, 64, 32)
        data = np.zeros(shape, dtype=np.int16)

        # Add mock hippocampus regions
        # Left hippocampus (label 17) - roughly in the temporal lobe area
        data[20:30, 15:25, 10:20] = 17
        # Right hippocampus (label 53)
        data[35:45, 15:25, 10:20] = 53

        # Add some other brain structures for realism
        data[25:35, 25:35, 15:25] = 2  # Left cerebral white matter
        data[30:40, 25:35, 15:25] = 41  # Right cerebral white matter

        # Create affine matrix (simple scaling)
        affine = np.diag([1.0, 1.0, 1.0, 1.0])

        # Create mock T1 anatomical image (orig.mgz)
        t1_data = np.random.normal(1000, 100, size=shape).astype(np.float32)
        # Make hippocampus areas slightly different intensity
        t1_data[20:30, 15:25, 10:20] = np.random.normal(1100, 50, size=(10, 10, 10))
        t1_data[35:45, 15:25, 10:20] = np.random.normal(1100, 50, size=(10, 10, 10))

        # Save orig.mgz (T1 anatomical)
        orig_img = nib.Nifti1Image(t1_data, affine)
        orig_path = mri_dir / "orig.mgz"
        nib.save(orig_img, orig_path)

        # Save aparc.DKTatlas+aseg.deep.mgz (segmentation)
        seg_img = nib.Nifti1Image(data, affine)
        aseg_path = mri_dir / "aparc.DKTatlas+aseg.deep.mgz"
        nib.save(seg_img, aseg_path)

        # Create mock hippocampal subfield files (optional)
        # Left hippocampus subfields
        lh_subfields = np.zeros(shape, dtype=np.int16)
        lh_subfields[20:25, 15:25, 10:20] = 203  # CA1
        lh_subfields[25:30, 15:25, 10:20] = 204  # CA3

        # Right hippocampus subfields
        rh_subfields = np.zeros(shape, dtype=np.int16)
        rh_subfields[35:40, 15:25, 10:20] = 1203  # CA1_right
        rh_subfields[40:45, 15:25, 10:20] = 1204  # CA3_right

        # Save subfield files
        lh_img = nib.Nifti1Image(lh_subfields, affine)
        lh_path = mri_dir / "lh.hippoSfLabels-T1.v21.mgz"
        nib.save(lh_img, lh_path)

        rh_img = nib.Nifti1Image(rh_subfields, affine)
        rh_path = mri_dir / "rh.hippoSfLabels-T1.v21.mgz"
        nib.save(rh_img, rh_path)

        logger.info("mock_segmentation_files_created",
                   orig=str(orig_path),
                   aseg=str(aseg_path),
                   lh_subfields=str(lh_path),
                   rh_subfields=str(rh_path))
    
    def _generate_aseg_stats_from_mgz(self, subject_dir: Path, aseg_mgz_file: Path, output_stats_file: Path) -> None:
        """
        Generate aseg.stats from aseg.mgz using FreeSurfer's mri_segstats.

        Args:
            subject_dir: FreeSurfer subject directory
            aseg_mgz_file: Path to aseg.mgz file
            output_stats_file: Where to save the stats file
        """
        logger.info("generating_aseg_stats_from_mgz",
                   subject_dir=str(subject_dir),
                   aseg_mgz=str(aseg_mgz_file),
                   output=str(output_stats_file))

        # Use the same container and environment as the main FreeSurfer run
        sif_path = self._find_freesurfer_sif()
        if not sif_path:
            raise RuntimeError("FreeSurfer SIF not found for stats generation")

        license_path = self._get_freesurfer_license_path()
        if not license_path:
            raise RuntimeError("FreeSurfer license not found")

        # mri_segstats command to generate statistics
        segstats_cmd = [
            "apptainer", "exec",
            "--bind", f"{subject_dir}:/subjects",
            "--bind", f"{license_path}:/usr/local/freesurfer/license.txt:ro",
            "--env", f"FS_LICENSE=/usr/local/freesurfer/license.txt",
            "--env", f"SUBJECTS_DIR=/subjects",
            *self._get_freesurfer_thread_env("--env"),
            str(sif_path),
            "/bin/bash", "-c",
            f" mri_segstats --seg /subjects/mri/aseg.mgz --sum /subjects/stats/aseg.stats --pv /subjects/mri/norm.mgz --empty --brain-vol --subject {subject_dir.name}"
        ]

        logger.info("running_mri_segstats", command=" ".join(segstats_cmd))

        result = subprocess_module.run(
            segstats_cmd,
            capture_output=True,
            timeout=300,  # 5 minutes timeout for stats generation
            text=True,
            env=self._get_extended_env()
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout
            logger.error("mri_segstats_failed",
                        returncode=result.returncode,
                        error=error_msg[:500])
            raise RuntimeError(f"mri_segstats failed: {error_msg[:200]}")

        logger.info("mri_segstats_completed")

    def _extract_hippocampal_data(self, freesurfer_dir: Path) -> Dict:
        """
        Extract hippocampal volumes from FreeSurfer output.

        Handles both FreeSurfer and FastSurfer output formats.
        Tries FreeSurfer aseg.stats first, then FastSurfer aseg+DKT.stats.

        Args:
            freesurfer_dir: FreeSurfer/FastSurfer output directory

        Returns:
            Dictionary of hippocampal volumes by region and hemisphere
        """
        logger.info("extracting_hippocampal_data")

        # Check FreeSurfer structure first (new primary)
        freesurfer_stats_dir = None

        # Look for FreeSurfer subject directories
        for subdir in ["freesurfer_singularity", "freesurfer_docker", "freesurfer_fallback"]:
            # Check both direct path and nested Docker path
            candidate_dirs = [
                freesurfer_dir / f"{subdir}_{self.job_id}" / "stats",  # Direct path
                freesurfer_dir / subdir / f"{subdir}_{self.job_id}" / "stats"  # Nested Docker path
            ]

            for candidate_dir in candidate_dirs:
                if candidate_dir.exists():
                    freesurfer_stats_dir = candidate_dir
                    logger.info("found_freesurfer_stats_directory", stats_dir=str(freesurfer_stats_dir), subdir=subdir)
                    break

            if freesurfer_stats_dir:
                break

        # Fall back to FastSurfer structure
        if not freesurfer_stats_dir:
            fastsurfer_stats_dir = freesurfer_dir / str(self.job_id) / "stats"
            if fastsurfer_stats_dir.exists():
                freesurfer_stats_dir = fastsurfer_stats_dir
                logger.info("found_fastsurfer_stats_directory", stats_dir=str(freesurfer_stats_dir))

        # No mock data fallback - fail if no real stats directory found

        if not freesurfer_stats_dir:
            logger.warning("no_stats_directory_found")
            return {}

        # Try FreeSurfer aseg.stats first
        logger.info("checking_for_freesurfer_aseg_data")
        aseg_file = freesurfer_stats_dir / "aseg.stats"

        hippocampal_data = {}

        # Check if the current stats directory has valid files
        stats_files_exist = aseg_file.exists() or (freesurfer_stats_dir / "aseg+DKT.stats").exists()

        # If no stats files exist, fail with clear error message
        if not stats_files_exist:
            error_msg = (
                "No segmentation statistics files found. "
                f"Expected aseg.stats or aseg+DKT.stats in {freesurfer_stats_dir}. "
                "FreeSurfer/FastSurfer processing may have failed or produced incomplete results."
            )
            logger.error("no_segmentation_stats_files", error=error_msg, stats_dir=str(freesurfer_stats_dir))
            raise RuntimeError(error_msg)

        if stats_files_exist and aseg_file.exists():
            logger.info("using_freesurfer_aseg_data", file=str(aseg_file))
            volumes = segmentation.parse_aseg_stats(aseg_file)
            if volumes:
                hippocampal_data = {
                    "Hippocampus": {
                        "left": volumes.get("left", 0.0),
                        "right": volumes.get("right", 0.0),
                    }
                }
                logger.info(
                    "freesurfer_hippocampal_data_found",
                    left=volumes.get("left"),
                    right=volumes.get("right")
                )
        else:
            # Try to generate aseg.stats from aseg.mgz if FreeSurfer created segmentation but not stats
            aseg_mgz_file = freesurfer_stats_dir.parent / "mri" / "aseg.mgz"
            if aseg_mgz_file.exists():
                logger.info("aseg.stats_missing_generating_from_mgz", mgz_file=str(aseg_mgz_file))
                try:
                    # Generate stats using mri_segstats (run inside FreeSurfer environment)
                    self._generate_aseg_stats_from_mgz(freesurfer_stats_dir.parent, aseg_mgz_file, aseg_file)
                    if aseg_file.exists():
                        logger.info("aseg_stats_generated_successfully")
                        volumes = segmentation.parse_aseg_stats(aseg_file)
                        if volumes:
                            hippocampal_data = {
                                "Hippocampus": {
                                    "left": volumes.get("left", 0.0),
                                    "right": volumes.get("right", 0.0),
                                }
                            }
                            logger.info(
                                "freesurfer_hippocampal_data_found",
                                left=volumes.get("left"),
                                right=volumes.get("right")
                            )
                    else:
                        logger.warning("failed_to_generate_aseg_stats")
                except Exception as e:
                    logger.error("error_generating_aseg_stats", error=str(e))
            else:
                logger.warning("no_aseg_files_found")

        # If no FreeSurfer data found, try FastSurfer fallback
        if not hippocampal_data:
            # Fall back to FastSurfer aseg+DKT.stats
            # Fall back to FastSurfer aseg+DKT.stats
            logger.info("freesurfer_stats_not_found_trying_fastsurfer")
            fastsurfer_aseg_file = freesurfer_stats_dir / "aseg+DKT.stats"

            if fastsurfer_aseg_file.exists():
                logger.info("using_fastsurfer_aseg_data", file=str(fastsurfer_aseg_file))
                volumes = segmentation.parse_aseg_stats(fastsurfer_aseg_file)
                if volumes:
                    hippocampal_data = {
                        "Hippocampus": {
                            "left": volumes.get("left", 0.0),
                            "right": volumes.get("right", 0.0),
                        }
                    }
                    logger.info(
                        "fastsurfer_hippocampal_data_found",
                        left=volumes.get("left"),
                        right=volumes.get("right")
                    )
                    logger.info(
                        "freesurfer_hippocampal_data_found",
                        left=volumes.get("left_hippocampus"),
                        right=volumes.get("right_hippocampus")
                    )
                else:
                    logger.warning("no_hippocampal_volumes_found_in_freesurfer")
            else:
                logger.error("no_stats_files_found", stats_dir=str(freesurfer_stats_dir), tried_files=["aseg+DKT.stats", "aseg.stats"])
        
        logger.info(
            "hippocampal_data_extracted",
            regions=list(hippocampal_data.keys()),
        )
        
        return hippocampal_data
    
    def _calculate_asymmetry(self, hippocampal_data: Dict) -> List[Dict]:
        """
        Calculate asymmetry indices for each hippocampal region.
        
        Args:
            hippocampal_data: Dictionary of volumes by region
        
        Returns:
            List of metric dictionaries
        """
        logger.info("calculating_asymmetry_indices")
        
        metrics = []
        
        for region, volumes in hippocampal_data.items():
            left = volumes["left"]
            right = volumes["right"]
            
            # Calculate asymmetry index
            ai = asymmetry.calculate_asymmetry_index(left, right)
            
            metrics.append({
                "region": region,
                "left_volume": left,
                "right_volume": right,
                "asymmetry_index": ai,
            })
        
        logger.info("asymmetry_calculated", metrics_count=len(metrics))
        
        return metrics
    
    def _generate_visualizations(self, nifti_path: Path, freesurfer_dir: Path) -> Dict[str, any]:
        """
        Generate segmentation visualizations for web viewer.
        
        Args:
            nifti_path: Path to original T1 NIfTI
            freesurfer_dir: FastSurfer output directory
        
        Returns:
            Dictionary with visualization file paths
        """
        logger.info("generating_visualizations")
        
        viz_dir = self.output_dir / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        
        viz_paths = {
            "whole_hippocampus": None,
            "subfields": None,
            "overlays": {}
        }
        
        try:
            # Extract segmentation files from FreeSurfer output
            aseg_nii, subfields_nii = visualization.extract_hippocampus_segmentation(
                freesurfer_dir,
                str(self.job_id)
            )
            
            # Convert anatomical T1 image for viewer base layer
            # FreeSurfer uses T1.mgz (conformed space) to ensure alignment with segmentation
            # Look for FreeSurfer subject directories first
            freesurfer_subject_dir = None
            for subdir in ["freesurfer_singularity", "freesurfer_docker", "freesurfer_fallback"]:
                candidate_dir = freesurfer_dir / f"{subdir}_{self.job_id}"
                if candidate_dir.exists():
                    freesurfer_subject_dir = candidate_dir
                    break

            t1_nifti = None
            if freesurfer_subject_dir:
                # Use FreeSurfer's T1.mgz for proper alignment
                t1_mgz = freesurfer_subject_dir / "mri" / "T1.mgz"
                if t1_mgz.exists():
                    t1_nifti = visualization.convert_t1_to_nifti(
                        t1_mgz,
                        viz_dir / "whole_hippocampus"
                    )
                    logger.info("t1_anatomical_converted", path=str(t1_nifti))
                else:
                    logger.warning("t1_mgz_not_found_in_freesurfer",
                                 expected=str(t1_mgz),
                                 note="Will use original input - may have alignment issues")

            # Fallback to original input if no FreeSurfer subject directory found
            if not t1_nifti:
                logger.warning("freesurfer_subject_dir_not_found",
                             note="Will use original input - may have alignment issues")
                t1_nifti = nifti_path
                
                # Generate overlay images for ALL 3 orientations
                # Use orig.mgz converted T1 to ensure proper spatial alignment with segmentation
                # FreeSurfer labels: 17 = Left-Hippocampus, 53 = Right-Hippocampus
                all_overlays = visualization.generate_all_orientation_overlays(
                    t1_nifti,  # Use orig.mgz converted (in same space as segmentation)
                    aseg_nii,
                    viz_dir / "overlays",
                    prefix="hippocampus",
                    specific_labels=[17, 53]  # Highlight hippocampus only
                )
                viz_paths["overlays"] = all_overlays
            
            # Prepare subfields for viewer
            if subfields_nii and subfields_nii.exists():
                subfields = visualization.prepare_nifti_for_viewer(
                    subfields_nii,
                    viz_dir / "subfields",
                    visualization.HIPPOCAMPAL_SUBFIELD_LABELS
                )
                viz_paths["subfields"] = subfields
                
                # Generate subfield overlay images
                # Use orig.mgz converted T1 to ensure proper spatial alignment
                subfield_overlays = visualization.generate_segmentation_overlays(
                    t1_nifti,  # Use orig.mgz converted (in same space as segmentation)
                    subfields_nii,
                    viz_dir / "overlays",
                    prefix="subfields"
                )
                viz_paths["overlays"]["subfields"] = subfield_overlays
            
            logger.info("visualizations_generated", paths=viz_paths)
        
        except Exception as e:
            logger.error("visualization_generation_failed", error=str(e), exc_info=True)
        
        return viz_paths
    
    def _store_process_pid(self, pid: int) -> None:
        """
        Store the process PID for tracking and cleanup.
        
        Writes PID to a file so we can kill zombie processes later.
        
        Args:
            pid: Process ID to store
        """
        self.process_pid = pid
        pid_file = self.output_dir / ".process_pid"
        with open(pid_file, "w") as f:
            f.write(str(pid))
        logger.info("process_pid_stored", pid=pid, file=str(pid_file))
    
    def _clear_process_pid(self) -> None:
        """Clear stored process PID after completion."""
        self.process_pid = None
        pid_file = self.output_dir / ".process_pid"
        if pid_file.exists():
            pid_file.unlink()
            logger.info("process_pid_cleared")
    
    def _save_results(self, metrics: List[Dict]) -> None:
        """
        Save processing results to files.
        
        Args:
            metrics: List of metric dictionaries
        """
        logger.info("saving_results")
        
        # Save as JSON
        json_path = self.output_dir / "metrics.json"
        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        # Save as CSV
        csv_path = self.output_dir / "metrics.csv"
        df = pd.DataFrame(metrics)
        df.to_csv(csv_path, index=False)
        
        logger.info(
            "results_saved",
            json=str(json_path),
            csv=str(csv_path),
        )

    def _get_app_root_directory(self) -> Path:
        """Get the application root directory.

        Returns the parent directory of the pipeline folder.
        """
        import inspect
        from pathlib import Path
        current_file = Path(inspect.getfile(self.__class__))
        app_root = current_file.parent.parent.parent  # Go up from pipeline/processors/mri_processor.py
        return app_root
    
    def _calculate_asymmetry(self, hippocampal_data: Dict) -> List[Dict]:
        """
        Calculate asymmetry indices for each hippocampal region.
        
        Args:
            hippocampal_data: Dictionary of volumes by region
        
        Returns:
            List of metric dictionaries
        """
        logger.info("calculating_asymmetry_indices")
        
        metrics = []
        
        for region, volumes in hippocampal_data.items():
            left = volumes["left"]
            right = volumes["right"]
            
            # Calculate asymmetry index
            ai = asymmetry.calculate_asymmetry_index(left, right)
            
            metrics.append({
                "region": region,
                "left_volume": left,
                "right_volume": right,
                "asymmetry_index": ai,
            })
        
        logger.info("asymmetry_calculated", metrics_count=len(metrics))
        
        return metrics
    
    def _generate_visualizations(self, nifti_path: Path, freesurfer_dir: Path) -> Dict[str, any]:
        """
        Generate segmentation visualizations for web viewer.
        
        Args:
            nifti_path: Path to original T1 NIfTI
            freesurfer_dir: FastSurfer output directory
        
        Returns:
            Dictionary with visualization file paths
        """
        logger.info("generating_visualizations")
        
        viz_dir = self.output_dir / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)
        
        viz_paths = {
            "whole_hippocampus": None,
            "subfields": None,
            "overlays": {}
        }
        
        try:
            # Extract segmentation files from FreeSurfer output
            aseg_nii, subfields_nii = visualization.extract_hippocampus_segmentation(
                freesurfer_dir,
                str(self.job_id)
            )
            
            # Convert anatomical T1 image for viewer base layer
            # FreeSurfer uses T1.mgz (conformed space) to ensure alignment with segmentation
            # Look for FreeSurfer subject directories first
            freesurfer_subject_dir = None
            for subdir in ["freesurfer_singularity", "freesurfer_docker", "freesurfer_fallback"]:
                candidate_dir = freesurfer_dir / f"{subdir}_{self.job_id}"
                if candidate_dir.exists():
                    freesurfer_subject_dir = candidate_dir
                    break

            t1_nifti = None
            if freesurfer_subject_dir:
                # Use FreeSurfer's T1.mgz for proper alignment
                t1_mgz = freesurfer_subject_dir / "mri" / "T1.mgz"
                if t1_mgz.exists():
                    t1_nifti = visualization.convert_t1_to_nifti(
                        t1_mgz,
                        viz_dir / "whole_hippocampus"
                    )
                    logger.info("t1_anatomical_converted", path=str(t1_nifti))
                else:
                    logger.warning("t1_mgz_not_found_in_freesurfer",
                                 expected=str(t1_mgz),
                                 note="Will use original input - may have alignment issues")

            # Fallback to original input if no FreeSurfer subject directory found
            if not t1_nifti:
                logger.warning("freesurfer_subject_dir_not_found",
                             note="Will use original input - may have alignment issues")
                t1_nifti = nifti_path
            
            # REQUIRE segmentation extraction for hippocampus analysis
            # Without proper segmentation, we cannot provide meaningful hippocampus visualization
            if not aseg_nii or not aseg_nii.exists():
                error_msg = (
                    "Segmentation extraction failed - cannot generate hippocampus visualizations. "
                    "FreeSurfer MGZ to NIfTI conversion failed, likely due to permission issues. "
                    "The system requires proper segmentation data to highlight hippocampus regions."
                )
                logger.error("segmentation_extraction_failed",
                           error=error_msg,
                           aseg_nii=str(aseg_nii) if aseg_nii else "None")
                raise ValueError(f"Hippocampus segmentation required but failed: {error_msg}")

            # Segmentation extraction successful - proceed with full visualization
            logger.info("segmentation_extraction_successful", aseg_path=str(aseg_nii))

            # Prepare whole hippocampus for viewer
            # Show whole brain but only highlight hippocampus in legend
            whole_hippo = visualization.prepare_nifti_for_viewer(
                aseg_nii,
                viz_dir / "whole_hippocampus",
                visualization.ASEG_HIPPOCAMPUS_LABELS,
                highlight_labels=[17, 53]  # Only show hippocampus in legend
            )
            viz_paths["whole_hippocampus"] = whole_hippo

            # Generate overlay images for ALL 3 orientations
            # Use orig.mgz converted T1 to ensure proper spatial alignment with segmentation
            # FreeSurfer labels: 17 = Left-Hippocampus, 53 = Right-Hippocampus
            all_overlays = visualization.generate_all_orientation_overlays(
                t1_nifti,  # Use orig.mgz converted (in same space as segmentation)
                aseg_nii,
                viz_dir / "overlays",
                prefix="hippocampus",
                specific_labels=[17, 53]  # Highlight hippocampus only
            )
            viz_paths["overlays"] = all_overlays

            # Prepare subfields for viewer (optional - doesn't fail if missing)
            if subfields_nii and subfields_nii.exists():
                subfields = visualization.prepare_nifti_for_viewer(
                    subfields_nii,
                    viz_dir / "subfields",
                    visualization.HIPPOCAMPAL_SUBFIELD_LABELS
                )
                viz_paths["subfields"] = subfields

                # Generate subfield overlay images
                # Use orig.mgz converted T1 to ensure proper spatial alignment
                subfield_overlays = visualization.generate_segmentation_overlays(
                    t1_nifti,  # Use orig.mgz converted (in same space as segmentation)
                    subfields_nii,
                    viz_dir / "overlays",
                    prefix="subfields"
                )
                viz_paths["overlays"]["subfields"] = subfield_overlays
            
            logger.info("visualizations_generated", paths=viz_paths)
        
        except Exception as e:
            logger.error("visualization_generation_failed", error=str(e), exc_info=True)
        
        return viz_paths
    
    def _store_process_pid(self, pid: int) -> None:
        """
        Store the process PID for tracking and cleanup.
        
        Writes PID to a file so we can kill zombie processes later.
        
        Args:
            pid: Process ID to store
        """
        self.process_pid = pid
        pid_file = self.output_dir / ".process_pid"
        with open(pid_file, "w") as f:
            f.write(str(pid))
        logger.info("process_pid_stored", pid=pid, file=str(pid_file))
    
    def _clear_process_pid(self) -> None:
        """Clear stored process PID after completion."""
        self.process_pid = None
        pid_file = self.output_dir / ".process_pid"
        if pid_file.exists():
            pid_file.unlink()
            logger.info("process_pid_cleared")
    
    def _save_results(self, metrics: List[Dict]) -> None:
        """
        Save processing results to files.
        
        Args:
            metrics: List of metric dictionaries
        """
        logger.info("saving_results")
        
        # Save as JSON
        json_path = self.output_dir / "metrics.json"
        with open(json_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        # Save as CSV
        csv_path = self.output_dir / "metrics.csv"
        df = pd.DataFrame(metrics)
        df.to_csv(csv_path, index=False)
        
        logger.info(
            "results_saved",
            json=str(json_path),
            csv=str(csv_path),
        )

    def _get_app_root_directory(self) -> Path:
        """Get the application root directory.

        Returns the parent directory of the pipeline folder.
        """
        import inspect
        from pathlib import Path
        current_file = Path(inspect.getfile(self.__class__))
        app_root = current_file.parent.parent.parent  # Go up from pipeline/processors/mri_processor.py
        return app_root

    def _start_freesurfer_progress_monitor(
        self,
        status_log_path: Path,
        base_progress: int = 20,
        end_progress: int = 100
    ) -> None:
        """Start monitoring FreeSurfer progress by parsing recon-all-status.log.

        This runs in a separate thread and updates progress based on FreeSurfer's
        completion of different processing stages.
        
        Includes robust error handling, thread health checks, and watchdog mechanism.

        Args:
            status_log_path: Path to the recon-all-status.log file
            base_progress: Base progress percentage (default 20 for FreeSurfer start)
        """
        import threading
        import time

        # Thread health monitoring
        class MonitorHealth:
            def __init__(self):
                self.last_heartbeat = time.time()
                self.poll_count = 0
                self.error_count = 0
                self.is_alive = True
                
            def heartbeat(self):
                """Update heartbeat timestamp"""
                self.last_heartbeat = time.time()
                self.poll_count += 1
                
            def record_error(self):
                """Record an error occurrence"""
                self.error_count += 1
                
            def is_healthy(self, timeout=120):
                """Check if monitor is healthy (heartbeat within timeout)"""
                return (time.time() - self.last_heartbeat) < timeout
        
        health = MonitorHealth()

        def monitor_progress():
            """Monitor the status log file and update progress with fixed percentages per phase."""
            last_line_count = 0
            current_phase = None
            ca_reg_snapshot_taken = False
            consecutive_errors = 0
            max_consecutive_errors = 5

            # Fixed percentage allocation based on phase complexity/duration.
            # Weights are mapped into the remaining range [base_progress, 100]
            # so percentages never exceed 100 even when base_progress > 0.
            # Weights below are derived from the last completed job's phase durations
            # (minutes rounded). This keeps percentages aligned with actual runtimes.
            phase_weights = {
                "motioncor": 1,                  # ~0.3 min
                "talairach": 4,                  # ~3.9 min
                "talairach failure detection": 0,
                "nu intensity correction": 4,    # ~4.0 min
                "intensity normalization": 2,    # ~1.6 min
                "skull stripping": 16,           # ~15.8 min
                "em registration": 12,           # ~11.8 min
                "ca normalize": 1,               # ~1.0 min
                "ca reg": 127,                   # ~127 min
                "subcort seg": 32,               # ~32 min
                "cc seg": 1,                     # ~0.8 min
                "merge aseg": 0,
                "intensity normalization2": 2,   # ~2.4 min
                "mask bfs": 0,
                "wm segmentation": 3,            # ~2.5 min
                "fill": 2,                       # ~2+ min (end marker not logged)
                "cortical parcellation": 0,      # Not usually reached in volonly
            }

            total_weight = sum(phase_weights.values()) or 1
            remaining_range = max(0, end_progress - base_progress)
            cumulative = 0
            phase_info = {}
            for phase, weight in phase_weights.items():
                cumulative += weight
                completion = base_progress + int((remaining_range * cumulative) / total_weight)
                phase_info[phase] = {
                    "completion_percent": min(completion, end_progress),
                    "estimated_duration": 0
                }

            # Create reverse mapping for progress lookup
            phase_progress_map = {phase: info["completion_percent"] for phase, info in phase_info.items()}
            
            logger.info("freesurfer_progress_monitor_thread_started", 
                       log_path=str(status_log_path), 
                       base_progress=base_progress,
                       job_id=str(self.job_id))

            # Wait for status log to be created (max 5 minutes)
            wait_count = 0
            while not status_log_path.exists() and wait_count < 10:
                logger.debug("waiting_for_status_log", path=str(status_log_path), wait_count=wait_count)
                time.sleep(30)
                wait_count += 1
            
            if not status_log_path.exists():
                logger.warning("status_log_never_created", path=str(status_log_path))
                return

            logger.info("status_log_found", path=str(status_log_path))

            poll_interval = 5  # Poll every 5 seconds (more responsive than 10s or 30s)
            
            while True:
                poll_start_time = time.time()
                
                try:
                    # Update heartbeat at start of each poll cycle
                    health.heartbeat()
                    
                    # CRITICAL: Check if output directory still exists
                    output_dir = status_log_path.parent.parent  # Go up from scripts/recon-all-status.log to job root
                    if not output_dir.exists():
                        logger.error("freesurfer_monitor_output_directory_deleted",
                                   job_id=str(self.job_id),
                                   output_dir=str(output_dir),
                                   message="Output directory was deleted while job was running")
                        # Fail the job immediately
                        try:
                            self._update_progress(0, "Failed: Output directory deleted")
                            # Mark job as failed in database
                            from workers.tasks.processing_web import fail_job_sync
                            fail_job_sync(str(self.job_id), "Output directory was deleted while job was running")
                        except Exception as fail_err:
                            logger.error("failed_to_mark_job_as_failed", 
                                       job_id=str(self.job_id), 
                                       error=str(fail_err))
                        health.is_alive = False
                        return
                    
                    # CRITICAL: Check if container is still running
                    from backend.core.config import get_settings
                    settings = get_settings()
                    container_name = f"{settings.freesurfer_container_prefix}{self.job_id}"
                    
                    try:
                        check_result = subprocess_module.run(
                            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
                            capture_output=True,
                            timeout=5,
                            text=True
                        )
                        
                        if check_result.returncode == 0:
                            container_status = check_result.stdout.strip()
                            
                            # If container exited, check exit code
                            if container_status in ["exited", "dead"]:
                                exit_code_result = subprocess_module.run(
                                    ["docker", "inspect", "--format", "{{.State.ExitCode}}", container_name],
                                    capture_output=True,
                                    timeout=5,
                                    text=True
                                )
                                
                                exit_code = int(exit_code_result.stdout.strip()) if exit_code_result.returncode == 0 else -1
                                
                                if exit_code != 0:
                                    logger.error("freesurfer_monitor_container_failed",
                                               job_id=str(self.job_id),
                                               container_name=container_name,
                                               exit_code=exit_code,
                                               status=container_status)
                                    
                                    # Get container logs for error details
                                    logs_result = subprocess_module.run(
                                        ["docker", "logs", "--tail", "50", container_name],
                                        capture_output=True,
                                        timeout=10,
                                        text=True
                                    )
                                    error_logs = logs_result.stdout[-500:] if logs_result.returncode == 0 else "Could not retrieve logs"
                                    
                                    # Fail the job immediately
                                    try:
                                        error_msg = f"FreeSurfer container exited with code {exit_code}. Recent logs: {error_logs}"
                                        self._update_progress(0, f"Failed: Container error (code {exit_code})")
                                        from workers.tasks.processing_web import fail_job_sync
                                        fail_job_sync(str(self.job_id), error_msg)
                                    except Exception as fail_err:
                                        logger.error("failed_to_mark_job_as_failed", 
                                                   job_id=str(self.job_id), 
                                                   error=str(fail_err))
                                    
                                    health.is_alive = False
                                    return
                                else:
                                    # Container exited successfully (exit code 0)
                                    logger.info("freesurfer_monitor_container_completed",
                                              job_id=str(self.job_id),
                                              container_name=container_name)
                                    health.is_alive = False
                                    return
                    except Exception as container_check_err:
                        # Container might not exist yet or Docker is unavailable
                        # Don't fail the job, just log it
                        logger.debug("freesurfer_monitor_container_check_failed",
                                   job_id=str(self.job_id),
                                   error=str(container_check_err))
                    
                    # Log each poll attempt for debugging
                    logger.debug("freesurfer_monitor_poll_attempt", 
                               poll_count=health.poll_count,
                               last_line_count=last_line_count,
                               current_phase=current_phase,
                               job_id=str(self.job_id),
                               log_exists=status_log_path.exists())
                    
                    if status_log_path.exists():
                        try:
                            with open(status_log_path, 'r', encoding='utf-8', errors='replace') as f:
                                lines = f.readlines()
                        except IOError as io_err:
                            logger.warning("freesurfer_monitor_file_read_error",
                                         error=str(io_err),
                                         path=str(status_log_path),
                                         job_id=str(self.job_id))
                            health.record_error()
                            consecutive_errors += 1
                            time.sleep(poll_interval)
                            continue

                        if len(lines) > last_line_count:
                            # New lines detected - reset error counter
                            consecutive_errors = 0
                            new_lines = lines[last_line_count:]
                            last_line_count = len(lines)
                            
                            logger.info("freesurfer_log_new_lines", 
                                       count=len(new_lines), 
                                       total_lines=len(lines),
                                       poll_count=health.poll_count,
                                       job_id=str(self.job_id))

                            for line in new_lines:
                                original_line = line.strip()
                                line_lower = original_line.lower()
                                
                                # Check for FreeSurfer status markers: #@# PhaseName
                                # NOTE: #@# markers indicate PHASE START, not completion
                                if line_lower.startswith("#@#"):
                                    logger.info("freesurfer_log_line_found", line=original_line, job_id=str(self.job_id))
                                    
                                    # Try to match with known phases
                                    matched = False
                                    for phase in phase_info.keys():
                                        if phase in line_lower:
                                            if current_phase != phase:  # Only update if it's a new phase
                                                # Set completion progress for previous phase if it exists
                                                if current_phase and current_phase in phase_info:
                                                    completion_progress = phase_info[current_phase]["completion_percent"]
                                                    prev_phase_display_name = current_phase.replace('_', ' ').title()
                                                    self._update_progress(completion_progress, f"Completed...({prev_phase_display_name})")
                                                    logger.info(
                                                        "freesurfer_phase_completed",
                                                        phase=current_phase,
                                                        progress=completion_progress,
                                                        job_id=str(self.job_id)
                                                    )

                                                # Start new phase - jump to start percentage
                                                current_phase = phase

                                                # Capture a one-time memory snapshot and increase sampling rate when CA Reg starts
                                                if phase == "ca reg" and not ca_reg_snapshot_taken:
                                                    try:
                                                        subject_output_dir = status_log_path.parent.parent
                                                        self._capture_memory_snapshot(subject_output_dir, "ca-reg-start")
                                                        container_name = f"{settings.freesurfer_container_prefix}{self.job_id}"
                                                        self._restart_resource_sampling(
                                                            container_name,
                                                            subject_output_dir,
                                                            interval_seconds=1,
                                                        )
                                                        ca_reg_snapshot_taken = True
                                                    except Exception as snapshot_exc:
                                                        logger.warning(
                                                            "ca_reg_memory_snapshot_failed",
                                                            error=str(snapshot_exc),
                                                            job_id=str(self.job_id),
                                                        )
                                                phase_start_time = time.time()

                                                # Calculate start progress (previous phase completion + small increment)
                                                if current_phase == "motioncor":
                                                    start_progress = min(base_progress + 1, end_progress)
                                                else:
                                                    # Find previous phase completion percentage
                                                    prev_completion = base_progress
                                                    phase_keys = list(phase_info.keys())
                                                    current_idx = phase_keys.index(phase)
                                                    if current_idx > 0:
                                                        prev_phase = phase_keys[current_idx - 1]
                                                        prev_completion = phase_info[prev_phase]["completion_percent"]

                                                    start_progress = min(prev_completion + 1, end_progress)

                                                phase_display_name = phase.replace('_', ' ').title()
                                                self._update_progress(start_progress, f"Processing...({phase_display_name})")
                                                logger.info("freesurfer_phase_started",
                                                           phase=phase,
                                                           progress=start_progress,
                                                           target_progress=phase_info[phase]["completion_percent"],
                                                           job_id=str(self.job_id))
                                            matched = True
                                            break
                                    
                                    if not matched:
                                        logger.debug("freesurfer_phase_not_matched", line=original_line)

                    # Fixed percentage system: Progress only updates when phases start and complete
                    # No incremental time-based updates within phases for simplicity
                        else:
                            # No new lines in this poll
                            logger.debug("freesurfer_monitor_no_new_lines",
                                       last_line_count=last_line_count,
                                       poll_count=health.poll_count,
                                       job_id=str(self.job_id))
                    else:
                        # Status log no longer exists, processing might be complete
                        logger.info("status_log_disappeared", path=str(status_log_path), job_id=str(self.job_id))
                        # Set final progress to 100% if we were in a phase
                        if current_phase and current_phase in phase_info:
                            final_progress = phase_info[current_phase]["completion_percent"]
                            self._update_progress(final_progress, f"FreeSurfer: {current_phase.replace('_', ' ').title()} completed")
                        health.is_alive = False
                        break

                    # Check for too many consecutive errors (possible thread issue)
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("freesurfer_monitor_too_many_errors",
                                   consecutive_errors=consecutive_errors,
                                   max_errors=max_consecutive_errors,
                                   job_id=str(self.job_id))
                        # Don't exit - keep trying, but log the issue
                        consecutive_errors = 0  # Reset to continue monitoring

                    # Calculate poll duration and adjust sleep time
                    poll_duration = time.time() - poll_start_time
                    sleep_time = max(0.1, poll_interval - poll_duration)
                    
                    logger.debug("freesurfer_monitor_poll_complete",
                               poll_duration_ms=int(poll_duration * 1000),
                               sleep_time_ms=int(sleep_time * 1000),
                               job_id=str(self.job_id))
                    
                    time.sleep(sleep_time)

                except KeyboardInterrupt:
                    logger.info("freesurfer_monitor_interrupted", job_id=str(self.job_id))
                    health.is_alive = False
                    break
                except Exception as e:
                    health.record_error()
                    consecutive_errors += 1
                    
                    logger.error("freesurfer_progress_monitor_error", 
                                error=str(e), 
                                error_type=type(e).__name__,
                                error_count=health.error_count,
                                consecutive_errors=consecutive_errors,
                                job_id=str(self.job_id))
                    
                    # Log full traceback for debugging
                    import traceback
                    logger.error("freesurfer_monitor_traceback", 
                               traceback=traceback.format_exc(),
                               job_id=str(self.job_id))
                    
                    # Adaptive error handling: shorter wait for transient errors
                    if consecutive_errors < 3:
                        time.sleep(poll_interval)  # Normal interval
                    else:
                        time.sleep(poll_interval * 3)  # Longer wait after multiple errors
                    
                    continue
            
            logger.info("freesurfer_progress_monitor_thread_ended", 
                       job_id=str(self.job_id),
                       poll_count=health.poll_count,
                       error_count=health.error_count)

        def watchdog():
            """Watchdog thread to monitor and restart the progress monitor if it dies."""
            restart_count = 0
            max_restarts = 3
            watchdog_check_interval = 60  # Check every 60 seconds
            
            logger.info("freesurfer_watchdog_started", job_id=str(self.job_id))
            
            while restart_count < max_restarts:
                time.sleep(watchdog_check_interval)
                
                # Check if monitor thread is still alive
                if not monitor_thread.is_alive():
                    logger.warning("freesurfer_monitor_thread_died",
                                 job_id=str(self.job_id),
                                 restart_count=restart_count,
                                 poll_count=health.poll_count,
                                 error_count=health.error_count)
                    
                    # Don't restart if it exited cleanly
                    if health.is_alive:
                        restart_count += 1
                        logger.warning("freesurfer_monitor_restarting",
                                     job_id=str(self.job_id),
                                     restart_attempt=restart_count)
                        
                        # Restart the monitor thread
                        new_monitor = threading.Thread(
                            target=monitor_progress,
                            daemon=True,
                            name=f"FreeSurferProgressMonitor-Restart{restart_count}"
                        )
                        new_monitor.start()
                        globals()['monitor_thread'] = new_monitor
                        
                        logger.info("freesurfer_monitor_restarted",
                                  job_id=str(self.job_id),
                                  thread_name=new_monitor.name)
                    else:
                        logger.info("freesurfer_monitor_exited_cleanly", job_id=str(self.job_id))
                        break
                
                # Check for unhealthy thread (heartbeat timeout)
                elif not health.is_healthy(timeout=120):
                    logger.error("freesurfer_monitor_unhealthy",
                               job_id=str(self.job_id),
                               last_heartbeat_seconds_ago=int(time.time() - health.last_heartbeat),
                               poll_count=health.poll_count,
                               error_count=health.error_count)
                    
                    # Thread is stuck - this is bad, log but don't restart
                    # (restarting a stuck thread could cause issues)
                else:
                    # Monitor is healthy
                    logger.debug("freesurfer_watchdog_check_ok",
                               job_id=str(self.job_id),
                               monitor_alive=True,
                               poll_count=health.poll_count,
                               last_heartbeat_seconds_ago=int(time.time() - health.last_heartbeat))
            
            if restart_count >= max_restarts:
                logger.error("freesurfer_monitor_max_restarts_exceeded",
                           job_id=str(self.job_id),
                           max_restarts=max_restarts)
            
            logger.info("freesurfer_watchdog_ended", job_id=str(self.job_id))

        # Start monitoring in a background thread
        monitor_thread = threading.Thread(target=monitor_progress, daemon=True, name="FreeSurferProgressMonitor")
        monitor_thread.start()
        
        # Start watchdog thread to monitor the monitor thread
        watchdog_thread = threading.Thread(target=watchdog, daemon=True, name="FreeSurferWatchdog")
        watchdog_thread.start()
        
        logger.info("freesurfer_progress_monitor_started", 
                   log_path=str(status_log_path), 
                   monitor_thread=monitor_thread.name,
                   watchdog_thread=watchdog_thread.name,
                   poll_interval_seconds=5,
                   job_id=str(self.job_id))

    def _get_current_freesurfer_command(self) -> Optional[str]:
        """Get the current FreeSurfer command being executed in the container.

        Returns:
            Command name (e.g., 'EM Registration', 'Normalization') or None if not found
        """
        try:
            # Get container ID from instance or database
            container_id = getattr(self, 'container_id', None)
            if not container_id:
                # Try to get from database
                job = self.db_session.query(Job).filter(Job.id == self.job_id).first()
                container_id = job.docker_container_id if job else None

            if not container_id:
                return None

            # Run docker exec to check running processes
            result = subprocess_module.run([
                'docker', 'exec', container_id,
                'ps', 'aux'
            ], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    # Look for FreeSurfer commands (exclude recon-all itself)
                    if 'mri_' in line and 'recon-all' not in line:
                        # Extract the command name (first word after mri_)
                        parts = line.split()
                        for part in parts:
                            if part.startswith('mri_'):
                                command = part.split('/')[-1]  # Remove path if present
                                # Map to more readable names
                                command_map = {
                                    'mri_em_register': 'EM Registration',
                                    'mri_normalize': 'Normalization',
                                    'mri_watershed': 'Watershed Algorithm',
                                    'mri_ca_normalize': 'CA Normalization',
                                    'mri_ca_register': 'CA Registration',
                                    'mri_segstats': 'Segmentation Stats',
                                    'mri_fill': 'Filling',
                                    'mri_cc': 'Corpus Callosum',
                                    'mri_pretess': 'Pre-Tessellation',
                                    'mri_tessellate': 'Tessellation',
                                    'mri_smooth': 'Smoothing',
                                    'mri_inflate': 'Inflation',
                                    'mri_sphere': 'Spherical Mapping',
                                    'mri_fix': 'Topology Fix',
                                    'mri_surf2surf': 'Surface Mapping',
                                    'mri_label': 'Labeling'
                                }
                                return command_map.get(command, command.replace('mri_', '').replace('_', ' ').title())

            return None

        except Exception as e:
            logger.debug("failed_to_get_freesurfer_command", error=str(e), job_id=str(self.job_id))
            return None

    def _api_bridge_process(self, input_path: str) -> Dict:
        """
        Process MRI using the FreeSurfer API Bridge.

        This method delegates the actual FreeSurfer processing to the API bridge service,
        which manages Docker containers and provides clean HTTP APIs.

        Args:
            input_path: Path to input MRI file

        Returns:
            Dictionary containing processing results
        """
        logger.info("api_bridge_processing_started", job_id=str(self.job_id), input_path=input_path)

        # Get API bridge configuration
        api_bridge_url = os.getenv("API_BRIDGE_URL", "http://localhost:8080")

        # Prepare input file path (ensure it's accessible to API bridge)
        input_path_obj = Path(input_path)
        if not input_path_obj.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Create output directory for this job
        output_dir = Path(settings.output_dir) / str(self.job_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare API request
        process_url = f"{api_bridge_url}/freesurfer/process"
        request_data = {
            "job_id": str(self.job_id),
            "input_file": str(input_path_obj),
            "output_dir": str(output_dir),
            "subject_id": f"subject_{self.job_id}"
        }

        try:
            # Submit processing job to API bridge
            if self.progress_callback:
                self.progress_callback(10, "Submitting job to FreeSurfer API Bridge")

            logger.info("submitting_to_api_bridge", url=process_url, job_id=str(self.job_id))
            response = requests.post(process_url, json=request_data, timeout=30)

            if response.status_code != 200:
                raise Exception(f"API bridge request failed: {response.status_code} - {response.text}")

            response_data = response.json()
            logger.info("api_bridge_job_submitted", response=response_data)

            # Monitor job progress
            status_url = f"{api_bridge_url}/freesurfer/status/{self.job_id}"
            results_url = f"{api_bridge_url}/freesurfer/results/{self.job_id}"

            # Poll for completion (with timeout)
            max_wait_time = 3600  # 1 hour maximum
            poll_interval = 10  # Check every 10 seconds
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                try:
                    # Check status
                    status_response = requests.get(status_url, timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()

                        # Update progress callback
                        if self.progress_callback and status_data.get("progress"):
                            progress = int(status_data["progress"])
                            message = status_data.get("message", "Processing...")
                            self.progress_callback(progress, message)

                        # Check if completed
                        if status_data.get("status") == "completed":
                            logger.info("api_bridge_job_completed", job_id=str(self.job_id))

                            # Get final results
                            results_response = requests.get(results_url, timeout=10)
                            if results_response.status_code == 200:
                                results_data = results_response.json()
                                logger.info("api_bridge_results_retrieved", job_id=str(self.job_id))

                                # Return standardized results format
                                return {
                                    "status": "completed",
                                    "output_dir": str(output_dir),
                                    "processing_method": "api_bridge",
                                    "api_bridge_results": results_data.get("results", {}),
                                    "job_id": str(self.job_id)
                                }
                            else:
                                raise Exception(f"Failed to get results: {results_response.status_code}")

                        elif status_data.get("status") == "failed":
                            error_msg = status_data.get("error", "Unknown error from API bridge")
                            raise Exception(f"FreeSurfer processing failed: {error_msg}")

                    elif status_response.status_code == 404:
                        # Job not found, might still be starting
                        logger.debug("job_not_found_waiting", job_id=str(self.job_id))

                except requests.RequestException as e:
                    logger.warning(f"Status check failed: {e}")

                # Wait before next poll
                time.sleep(poll_interval)
                elapsed_time += poll_interval

                # Update progress periodically
                if self.progress_callback and elapsed_time % 60 == 0:  # Every minute
                    minutes_elapsed = elapsed_time // 60
                    self.progress_callback(
                        min(90, 20 + minutes_elapsed),  # Progress from 20% to 90%
                        f"Processing with FreeSurfer... ({minutes_elapsed}min elapsed)"
                    )

            # Timeout reached
            raise Exception(f"FreeSurfer processing timed out after {max_wait_time} seconds")

        except Exception as e:
            logger.error("api_bridge_processing_failed", job_id=str(self.job_id), error=str(e))
            raise Exception(f"API bridge processing failed: {str(e)}")



            elapsed_time = 0

            while elapsed_time < max_wait_time:
                try:
                    # Check status
                    status_response = requests.get(status_url, timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()

                        # Update progress callback
                        if self.progress_callback and status_data.get("progress"):
                            progress = int(status_data["progress"])
                            message = status_data.get("message", "Processing...")
                            self.progress_callback(progress, message)

                        # Check if completed
                        if status_data.get("status") == "completed":
                            logger.info("api_bridge_job_completed", job_id=str(self.job_id))

                            # Get final results
                            results_response = requests.get(results_url, timeout=10)
                            if results_response.status_code == 200:
                                results_data = results_response.json()
                                logger.info("api_bridge_results_retrieved", job_id=str(self.job_id))

                                # Return standardized results format
                                return {
                                    "status": "completed",
                                    "output_dir": str(output_dir),
                                    "processing_method": "api_bridge",
                                    "api_bridge_results": results_data.get("results", {}),
                                    "job_id": str(self.job_id)
                                }
                            else:
                                raise Exception(f"Failed to get results: {results_response.status_code}")

                        elif status_data.get("status") == "failed":
                            error_msg = status_data.get("error", "Unknown error from API bridge")
                            raise Exception(f"FreeSurfer processing failed: {error_msg}")

                    elif status_response.status_code == 404:
                        # Job not found, might still be starting
                        logger.debug("job_not_found_waiting", job_id=str(self.job_id))

                except requests.RequestException as e:
                    logger.warning(f"Status check failed: {e}")

                # Wait before next poll
                time.sleep(poll_interval)
                elapsed_time += poll_interval

                # Update progress periodically
                if self.progress_callback and elapsed_time % 60 == 0:  # Every minute
                    minutes_elapsed = elapsed_time // 60
                    self.progress_callback(
                        min(90, 20 + minutes_elapsed),  # Progress from 20% to 90%
                        f"Processing with FreeSurfer... ({minutes_elapsed}min elapsed)"
                    )

            # Timeout reached
            raise Exception(f"FreeSurfer processing timed out after {max_wait_time} seconds")

        except Exception as e:
            logger.error("api_bridge_processing_failed", job_id=str(self.job_id), error=str(e))
            raise Exception(f"API bridge processing failed: {str(e)}")



            elapsed_time = 0

            while elapsed_time < max_wait_time:
                try:
                    # Check status
                    status_response = requests.get(status_url, timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()

                        # Update progress callback
                        if self.progress_callback and status_data.get("progress"):
                            progress = int(status_data["progress"])
                            message = status_data.get("message", "Processing...")
                            self.progress_callback(progress, message)

                        # Check if completed
                        if status_data.get("status") == "completed":
                            logger.info("api_bridge_job_completed", job_id=str(self.job_id))

                            # Get final results
                            results_response = requests.get(results_url, timeout=10)
                            if results_response.status_code == 200:
                                results_data = results_response.json()
                                logger.info("api_bridge_results_retrieved", job_id=str(self.job_id))

                                # Return standardized results format
                                return {
                                    "status": "completed",
                                    "output_dir": str(output_dir),
                                    "processing_method": "api_bridge",
                                    "api_bridge_results": results_data.get("results", {}),
                                    "job_id": str(self.job_id)
                                }
                            else:
                                raise Exception(f"Failed to get results: {results_response.status_code}")

                        elif status_data.get("status") == "failed":
                            error_msg = status_data.get("error", "Unknown error from API bridge")
                            raise Exception(f"FreeSurfer processing failed: {error_msg}")

                    elif status_response.status_code == 404:
                        # Job not found, might still be starting
                        logger.debug("job_not_found_waiting", job_id=str(self.job_id))

                except requests.RequestException as e:
                    logger.warning(f"Status check failed: {e}")

                # Wait before next poll
                time.sleep(poll_interval)
                elapsed_time += poll_interval

                # Update progress periodically
                if self.progress_callback and elapsed_time % 60 == 0:  # Every minute
                    minutes_elapsed = elapsed_time // 60
                    self.progress_callback(
                        min(90, 20 + minutes_elapsed),  # Progress from 20% to 90%
                        f"Processing with FreeSurfer... ({minutes_elapsed}min elapsed)"
                    )

            # Timeout reached
            raise Exception(f"FreeSurfer processing timed out after {max_wait_time} seconds")

        except Exception as e:
            logger.error("api_bridge_processing_failed", job_id=str(self.job_id), error=str(e))
            raise Exception(f"API bridge processing failed: {str(e)}")


