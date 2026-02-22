#!/usr/bin/env python3
"""
NeuroInsight Stop Script - Python-based for reliability
Aggressively stops all NeuroInsight processes and services
"""

import os
import sys
import subprocess
import signal
import time
import psutil
from pathlib import Path

# Ensure prod stop uses production settings (dev has its own stop_dev.py)
os.environ.setdefault("ENVIRONMENT", "production")

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def log_info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{NC} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{NC} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")

def kill_process_by_pid_file(pid_file, process_name):
    """Kill process using PID file"""
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())

            if psutil.pid_exists(pid):
                log_info(f"Stopping {process_name} (PID: {pid})...")

                # Try graceful shutdown first
                try:
                    os.kill(pid, signal.SIGTERM)
                    # Wait up to 10 seconds for graceful shutdown
                    for _ in range(10):
                        if not psutil.pid_exists(pid):
                            break
                        time.sleep(1)

                    if psutil.pid_exists(pid):
                        log_warning(f"{process_name} didn't stop gracefully, forcing...")
                        os.kill(pid, signal.SIGKILL)
                    else:
                        log_success(f"{process_name} stopped gracefully")
                except OSError:
                    log_warning(f"Process {pid} already dead")
            else:
                log_warning(f"{process_name} PID file exists but process not running")

        except (ValueError, IOError) as e:
            log_warning(f"Error reading {process_name} PID file: {e}")

        # Clean up PID file
        os.remove(pid_file)
    else:
        log_info(f"No {process_name} PID file found")

def kill_processes_by_pattern(pattern, process_name):
    """Kill all processes matching a pattern"""
    try:
        # Use pgrep to find processes
        result = subprocess.run(['pgrep', '-f', pattern],
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            pids = [int(pid.strip()) for pid in result.stdout.strip().split('\n') if pid.strip()]
            killed = 0
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                    killed += 1
                except (ProcessLookupError, OSError):
                    pass  # Already dead
            if killed > 0:
                log_info(f"Killed {killed} {process_name} processes")
    except Exception as e:
        log_warning(f"Error killing {process_name}: {e}")

def stop_docker_services():
    """Stop Docker containers individually"""
    try:
        log_info("Stopping Docker containers...")

        containers = ['neuroinsight-minio', 'neuroinsight-redis', 'neuroinsight-postgres']
        stopped_containers = []

        for container in containers:
            try:
                # Check if container exists and is running
                result = subprocess.run(['docker', 'ps', '-q', '-f', f'name={container}'],
                                      capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    log_info(f"Stopping {container}...")
                    stop_result = subprocess.run(['docker', 'stop', container],
                                               capture_output=True, text=True)
                    if stop_result.returncode == 0:
                        log_success(f"Stopped {container}")
                        stopped_containers.append(container)
                    else:
                        log_warning(f"Failed to stop {container}: {stop_result.stderr}")
                else:
                    log_info(f"Container {container} not running")
            except Exception as e:
                log_error(f"Error stopping {container}: {e}")

        # Remove containers
        for container in containers:
            try:
                result = subprocess.run(['docker', 'ps', '-a', '-q', '-f', f'name={container}'],
                                      capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    log_info(f"Removing {container}...")
                    rm_result = subprocess.run(['docker', 'rm', container],
                                             capture_output=True, text=True)
                    if rm_result.returncode == 0:
                        log_success(f"Removed {container}")
                    else:
                        log_warning(f"Failed to remove {container}: {rm_result.stderr}")
            except Exception as e:
                log_error(f"Error removing {container}: {e}")

        if stopped_containers:
            log_success(f"Successfully stopped containers: {', '.join(stopped_containers)}")
        else:
            log_info("No containers were running")

        # Force kill any remaining containers (fallback)
        try:
            result = subprocess.run(['docker', 'ps', '-q', '--filter', 'name=neuroinsight'],
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                container_ids = result.stdout.strip().split('\n')
                for container_id in container_ids:
                    subprocess.run(['docker', 'kill', container_id], capture_output=True)
                log_success("Force-killed remaining NeuroInsight containers")
        except Exception as e:
            log_warning(f"Error force-killing containers: {e}")

    except Exception as e:
        log_error(f"Docker stop error: {e}")

def run_maintenance():
    """Run maintenance before shutdown"""
    try:
        log_info("Running maintenance to detect interrupted jobs...")
        sys.path.insert(0, '.')
        from backend.services.task_management_service import TaskManagementService

        result = TaskManagementService.run_maintenance()
        container_mismatches = len(result.get('container_mismatches', []))
        cleaned_jobs = result.get('cleaned_jobs', 0)
        log_success(f"Maintenance completed: {container_mismatches} mismatches, {cleaned_jobs} jobs cleaned")
    except Exception as e:
        log_warning(f"Maintenance check failed: {e}")

def clear_stuck_jobs():
    """Clear stuck jobs if requested"""
    try:
        log_info("Clearing stuck jobs...")
        sys.path.insert(0, '.')
        from backend.core.database import get_db
        from backend.models.job import Job, JobStatus
        from datetime import datetime, timedelta

        db = next(get_db())
        now = datetime.utcnow()

        # Clear running jobs stuck for >5 hours
        stuck_running = db.query(Job).filter(
            Job.status == JobStatus.RUNNING,
            Job.started_at < (now - timedelta(hours=5))
        ).all()

        cleared = 0
        for job in stuck_running:
            job.status = JobStatus.FAILED
            job.error_message = "Cleared stuck job during shutdown"
            job.completed_at = now
            cleared += 1

        if cleared > 0:
            db.commit()
            log_success(f"Cleared {cleared} stuck running jobs")

        db.close()

    except Exception as e:
        log_error(f"Failed to clear stuck jobs: {e}")

def main():
    print("=" * 50)
    print("   NeuroInsight Stop (Python-based)")
    print("=" * 50)
    print()

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Run maintenance first
    run_maintenance()

    # Check for --clear-stuck flag
    if len(sys.argv) > 1 and sys.argv[1] == "--clear-stuck":
        clear_stuck_jobs()

    # Aggressive process cleanup
    log_info("Aggressively stopping all NeuroInsight processes...")

    # Kill by PID files first
    kill_process_by_pid_file("neuroinsight.pid", "backend")
    kill_process_by_pid_file("celery.pid", "Celery worker")
    kill_process_by_pid_file("job_monitor.pid", "job monitor")
    kill_process_by_pid_file("job_queue_processor.pid", "job queue processor")
    kill_process_by_pid_file("monitor.pid", "system monitor")

    # Kill any remaining processes by pattern
    kill_processes_by_pattern("python3.*backend/main.py", "backend")
    kill_processes_by_pattern("python3.*celery.*processing_web", "Celery")
    kill_processes_by_pattern("python3.*job_monitor", "job monitor")
    kill_processes_by_pattern("python3.*job_queue_processor", "job queue processor")
    kill_processes_by_pattern("python3.*monitor.sh", "system monitor")

    # Stop Docker services
    stop_docker_services()

    # Final cleanup
    for pid_file in ["neuroinsight.pid", "celery.pid", "job_monitor.pid", "job_queue_processor.pid", "monitor.pid"]:
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except OSError:
                pass

    log_success("NeuroInsight services stopped completely")

    print()
    print("=" * 50)
    print("To restart: ./neuroinsight start")
    print("To check status: ./neuroinsight status")
    print("=" * 50)

if __name__ == "__main__":
    main()


