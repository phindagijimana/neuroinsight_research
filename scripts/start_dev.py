#!/usr/bin/env python3
"""
NeuroInsight Dev Start Script (isolated from production).
Starts backend, Celery, and job monitor on port 8001 with dev-only resources.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

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


def check_port_available(port):
    """Check if a port is available."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        result = sock.connect_ex(('localhost', port))
        return result != 0  # True if available


def require_port_available(port):
    """Require a specific port to be available."""
    if not check_port_available(port):
        log_error(f"Port {port} is already in use. Stop the service using it first.")
        return False
    return True


def ensure_dev_database():
    """Ensure the dev database exists."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            user='neuroinsight',
            password='JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg',
            database='postgres',
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'neuroinsight_dev'")
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute("CREATE DATABASE neuroinsight_dev")
            log_success("Created dev database neuroinsight_dev")
        else:
            log_info("Dev database neuroinsight_dev already exists")
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        log_error(f"Failed to ensure dev database: {exc}")
        return False


def build_dev_env():
    """Build environment variables for dev services."""
    base_dir = Path.home() / ".local" / "share" / "neuroinsight_dev"
    upload_dir = str(base_dir / "uploads")
    output_dir = str(base_dir / "outputs")

    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path.cwd())
    env['ENVIRONMENT'] = 'development'
    env['API_PORT'] = '8001'
    env['PORT'] = '8001'
    env['FORCE_CELERY'] = '1'
    env['DATABASE_URL'] = (
        'postgresql://neuroinsight:'
        'JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg'
        '@localhost:5432/neuroinsight_dev'
    )
    env['REDIS_URL'] = 'redis://:redis_secure_password@localhost:6379/1'
    env['UPLOAD_DIR'] = upload_dir
    env['OUTPUT_DIR'] = output_dir
    env['PROCESSING_TIMEOUT'] = '25200'
    env['MAX_CONCURRENT_JOBS'] = '1'
    env['FREESURFER_CONTAINER_PREFIX'] = 'freesurfer-dev-job-'

    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    return env


def start_backend(env):
    """Start dev backend on port 8001."""
    log_info("Starting dev backend on port 8001...")
    proc = subprocess.Popen(
        [sys.executable, 'backend/main.py'],
        env=env,
        stdout=open('neuroinsight-dev.log', 'w'),
        stderr=subprocess.STDOUT,
    )
    with open('neuroinsight-dev.pid', 'w') as f:
        f.write(str(proc.pid))

    log_info("Waiting for dev backend health...")
    for _ in range(30):
        try:
            import requests
            response = requests.get('http://localhost:8001/health', timeout=2)
            if response.status_code == 200:
                log_success("Dev backend health check passed!")
                return proc
        except Exception:
            time.sleep(1)

    log_error("Dev backend failed to respond to health checks")
    proc.kill()
    return None


def start_celery(env):
    """Start dev Celery worker."""
    log_info("Starting dev Celery worker...")
    proc = subprocess.Popen(
        [
            sys.executable, '-m', 'celery',
            '-A', 'workers.tasks.processing_web', 'worker',
            '--loglevel=info', '--concurrency=1'
        ],
        env=env,
        stdout=open('celery-dev.log', 'w'),
        stderr=subprocess.STDOUT,
    )
    with open('celery-dev.pid', 'w') as f:
        f.write(str(proc.pid))
    log_success(f"Dev Celery started (PID: {proc.pid})")
    return proc


def start_job_monitor(env):
    """Start dev job monitor."""
    log_info("Starting dev job monitor...")
    proc = subprocess.Popen(
        [
            sys.executable, '-c',
            "import sys, time; sys.path.insert(0, '.'); "
            "from backend.services.job_monitor import JobMonitor; "
            "monitor = JobMonitor(); monitor.start_background_monitoring(); "
            "time.sleep(10**9)"
        ],
        env=env,
        stdout=open('dev_job_monitor.log', 'w'),
        stderr=subprocess.STDOUT,
    )
    with open('job_monitor-dev.pid', 'w') as f:
        f.write(str(proc.pid))
    log_success(f"Dev job monitor started (PID: {proc.pid})")
    return proc


def main():
    if not require_port_available(8001):
        sys.exit(1)

    if not ensure_dev_database():
        sys.exit(1)

    env = build_dev_env()
    backend_proc = start_backend(env)
    if not backend_proc:
        sys.exit(1)

    start_celery(env)
    start_job_monitor(env)
    log_success("Dev environment started on port 8001 (isolated from prod).")


if __name__ == "__main__":
    main()

