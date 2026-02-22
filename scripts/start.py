#!/usr/bin/env python3
"""
NeuroInsight Start Script - Python-based for reliability
Bypasses terminal corruption issues by using Python directly
"""

import os
import sys
import subprocess
import time
import signal
import psutil
import requests
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

def find_and_kill_processes():
    """Aggressively find and kill all NeuroInsight processes"""
    killed_count = 0

    # Kill by command patterns
    patterns = [
        "python3.*backend/main.py",
        "python3.*celery.*processing_web",
        "python3.*job_monitor",
        "python3.*job_queue_processor"
    ]

    for pattern in patterns:
        try:
            # Use pgrep to find processes
            result = subprocess.run(['pgrep', '-f', pattern],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                            killed_count += 1
                            log_info(f"Killed process {pid}")
                        except (ProcessLookupError, OSError):
                            pass  # Process already dead
        except Exception as e:
            log_warning(f"Error killing {pattern}: {e}")

    # Also try pkill as fallback
    try:
        subprocess.run(['pkill', '-9', '-f', 'neuroinsight'], check=False)
        subprocess.run(['pkill', '-9', '-f', 'celery'], check=False)
        subprocess.run(['pkill', '-9', '-f', 'backend/main.py'], check=False)
        subprocess.run(['pkill', '-9', '-f', 'job_queue_processor'], check=False)
    except Exception:
        pass

    if killed_count > 0:
        log_success(f"Cleaned up {killed_count} existing processes")
        time.sleep(2)  # Wait for cleanup

    return killed_count

def check_port_available(port):
    """Check if a port is available"""
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

def start_docker_services():
    """Start Docker services individually (bypassing docker-compose issues)"""
    try:
        log_info("Starting Docker services individually...")

        services_started = []

        # Start PostgreSQL
        log_info("Starting PostgreSQL...")
        postgres_cmd = [
            'docker', 'run', '-d',
            '--name', 'neuroinsight-postgres',
            '-e', 'POSTGRES_DB=neuroinsight',
            '-e', 'POSTGRES_USER=neuroinsight',
            '-e', 'POSTGRES_PASSWORD=JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg',
            '-p', '5432:5432',
            '--restart', 'unless-stopped',
            'postgres:15-alpine'
        ]

        result = subprocess.run(postgres_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_success("PostgreSQL started")
            services_started.append('postgres')
        else:
            log_error(f"PostgreSQL startup failed: {result.stderr}")
            return False

        # Start Redis
        log_info("Starting Redis...")
        redis_cmd = [
            'docker', 'run', '-d',
            '--name', 'neuroinsight-redis',
            '-p', '6379:6379',
            '--restart', 'unless-stopped',
            'redis:7-alpine',
            'redis-server', '--appendonly', 'yes', '--requirepass', 'redis_secure_password'
        ]

        result = subprocess.run(redis_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_success("Redis started")
            services_started.append('redis')
        else:
            log_error(f"Redis startup failed: {result.stderr}")
            return False

        # Start MinIO
        log_info("Starting MinIO...")
        minio_cmd = [
            'docker', 'run', '-d',
            '--name', 'neuroinsight-minio',
            '-e', 'MINIO_ROOT_USER=neuroinsight_minio',
            '-e', 'MINIO_ROOT_PASSWORD=minio_secure_password',
            '-p', '9000:9000',
            '-p', '9001:9001',
            '--restart', 'unless-stopped',
            'minio/minio:latest',
            'server', '/data', '--console-address', ':9001'
        ]

        result = subprocess.run(minio_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            log_success("MinIO started")
            services_started.append('minio')
        else:
            log_error(f"MinIO startup failed: {result.stderr}")
            return False

        log_success(f"All Docker services started: {', '.join(services_started)}")
        return True

    except Exception as e:
        log_error(f"Docker error: {e}")
        return False

def start_backend(port):
    """Start the NeuroInsight backend"""
    try:
        log_info(f"Starting NeuroInsight backend on port {port}...")

        # Set environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path.cwd())
        env['API_PORT'] = str(port)
        env['PORT'] = str(port)
        env['ENVIRONMENT'] = 'production'
        env['MAX_CONCURRENT_JOBS'] = '1'
        # Force PostgreSQL usage for production
        env['DATABASE_URL'] = 'postgresql://neuroinsight:JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg@localhost:5432/neuroinsight'

        # Start backend with docker group access
        # Use 'sg docker' to ensure docker group is active even if user just logged in
        proc = subprocess.Popen([
            'sg', 'docker', '-c',
            f'{sys.executable} backend/main.py'
        ], env=env, stdout=open('neuroinsight.log', 'w'),
           stderr=subprocess.STDOUT)

        # Save PID
        with open('neuroinsight.pid', 'w') as f:
            f.write(str(proc.pid))

        log_success(f"Backend started (PID: {proc.pid})")

        # Wait for health check
        log_info("Waiting for backend to be ready...")
        for i in range(30):  # 30 second timeout
            try:
                response = requests.get(f'http://localhost:{port}/health', timeout=2)
                if response.status_code == 200:
                    log_success("Backend health check passed!")
                    return proc
            except:
                pass
            time.sleep(1)

        log_error("Backend failed to respond to health checks")
        proc.kill()
        return None

    except Exception as e:
        log_error(f"Backend startup failed: {e}")
        return None

def start_celery():
    """Start Celery worker"""
    try:
        log_info("Starting Celery worker...")

        # CRITICAL: Kill any existing Celery workers first to prevent multiple workers
        log_info("Checking for existing Celery workers...")
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'celery.*worker.*processing_web'],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                existing_pids = result.stdout.strip().split('\n')
                log_warning(f"Found {len(existing_pids)} existing Celery worker(s), killing them...")
                
                for pid in existing_pids:
                    try:
                        subprocess.run(['kill', '-9', pid], check=False)
                        log_info(f"Killed worker PID {pid}")
                    except Exception as e:
                        log_warning(f"Failed to kill PID {pid}: {e}")
                
                # Wait for cleanup
                time.sleep(3)
                log_success("Existing workers cleaned up")
            else:
                log_info("No existing workers found")
        except Exception as e:
            log_warning(f"Error checking for existing workers: {e}")

        # Set environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path.cwd())
        env['ENVIRONMENT'] = 'production'
        env['DATABASE_URL'] = 'postgresql://neuroinsight:JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg@localhost:5432/neuroinsight'
        env['FREESURFER_CONTAINER_PREFIX'] = 'freesurfer-job-'

        # Start celery with docker group access
        # Use 'sg docker' to ensure FreeSurfer container operations work
        proc = subprocess.Popen([
            'sg', 'docker', '-c',
            f'{sys.executable} -m celery -A workers.tasks.processing_web worker --loglevel=info --concurrency=1'
        ], env=env, stdout=open('celery_worker.log', 'w'),
           stderr=subprocess.STDOUT)

        # Save PID
        with open('celery.pid', 'w') as f:
            f.write(str(proc.pid))

        log_success(f"Celery worker started (PID: {proc.pid})")
        
        # Verify only one worker is running
        time.sleep(2)
        result = subprocess.run(
            ['pgrep', '-f', 'celery.*worker.*processing_web'],
            capture_output=True,
            text=True,
            check=False
        )
        worker_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        if worker_count > 2:  # parent + child is normal
            log_warning(f"WARNING: {worker_count} Celery processes detected (expected 2)!")
        else:
            log_success(f"Worker count validated: {worker_count} processes")
        
        return proc

    except Exception as e:
        log_warning(f"Celery startup failed: {e}")
        return None

def start_celery_beat():
    """Start Celery Beat scheduler for periodic tasks"""
    try:
        log_info("Starting Celery Beat scheduler...")

        # Set up environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path.cwd())
        env['ENVIRONMENT'] = 'production'
        env['DATABASE_URL'] = 'postgresql://neuroinsight:JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg@localhost:5432/neuroinsight'

        # Start celery beat
        proc = subprocess.Popen([
            sys.executable, '-m', 'celery',
            '-A', 'workers.tasks.processing_web',
            'beat', '--loglevel=info'
        ], env=env, stdout=open('celery_beat.log', 'w'),
           stderr=subprocess.STDOUT)

        # Save PID
        with open('celery_beat.pid', 'w') as f:
            f.write(str(proc.pid))

        log_success(f"Celery Beat started (PID: {proc.pid})")
        return proc

    except Exception as e:
        log_warning(f"Celery Beat startup failed: {e}")
        return None

def start_job_monitor():
    """Start job monitoring service"""
    try:
        log_info("Starting job monitor...")

        # Set environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path.cwd())
        env['ENVIRONMENT'] = 'production'
        env['DATABASE_URL'] = 'postgresql://neuroinsight:JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg@localhost:5432/neuroinsight'
        env['FREESURFER_CONTAINER_PREFIX'] = 'freesurfer-job-'

        # Start monitor
        proc = subprocess.Popen([
            sys.executable, '-c',
            """
import sys
import time
sys.path.insert(0, '.')
from backend.services.job_monitor import JobMonitor
monitor = JobMonitor()
monitor.start_background_monitoring()
while True:
    time.sleep(60)
"""
        ], env=env, stdout=open('job_monitor.log', 'w'),
           stderr=subprocess.STDOUT)

        # Save PID
        with open('job_monitor.pid', 'w') as f:
            f.write(str(proc.pid))

        log_success(f"Job monitor started (PID: {proc.pid})")
        return proc

    except Exception as e:
        log_warning(f"Job monitor startup failed: {e}")
        return None

def start_job_queue_processor():
    """Start job queue processor service"""
    try:
        if os.environ.get("ENVIRONMENT", "production") == "production":
            log_info("Skipping job queue processor in production")
            return None

        log_info("Starting job queue processor...")

        # Set environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path.cwd())
        env['ENVIRONMENT'] = os.environ.get("ENVIRONMENT", "production")

        # Start job queue processor
        proc = subprocess.Popen([
            sys.executable, '-c',
            """
import sys
sys.path.insert(0, '.')
from backend.services.job_queue_processor import start_job_queue_processor
start_job_queue_processor()
import time
while True:
    time.sleep(60)  # Keep process alive
"""
        ], env=env, stdout=open('job_queue_processor.log', 'w'),
           stderr=subprocess.STDOUT)

        # Save PID
        with open('job_queue_processor.pid', 'w') as f:
            f.write(str(proc.pid))

        log_success(f"Job queue processor started (PID: {proc.pid})")
        return proc

    except Exception as e:
        log_warning(f"Job queue processor startup failed: {e}")
        return None

def check_for_conflicts():
    """Check for existing NeuroInsight instances and warn user"""
    conflicts_found = []
    
    # Check for PID files
    pid_files = ['neuroinsight.pid', 'celery.pid', 'job_monitor.pid', 'job_queue_processor.pid']
    existing_pids = []
    for pid_file in pid_files:
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    if psutil.pid_exists(pid):
                        existing_pids.append((pid_file, pid))
            except (ValueError, IOError):
                pass
    
    if existing_pids:
        conflicts_found.append("PID files")
        log_warning("Found existing PID files:")
        for pid_file, pid in existing_pids:
            log_warning(f"  • {pid_file}: process {pid} is running")
    
    # Check for running processes
    running_procs = []
    patterns = ['backend/main.py', 'celery.*processing_web', 'job_monitor']
    for pattern in patterns:
        result = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            running_procs.extend([p for p in pids if p.strip()])
    
    if running_procs:
        conflicts_found.append("running processes")
        log_warning(f"Found {len(running_procs)} NeuroInsight process(es) already running")
    
    # Check for port conflicts
    ports_in_use = []
    for port in [8000, 5432, 6379, 9000]:
        if not check_port_available(port):
            ports_in_use.append(port)
            conflicts_found.append(f"port {port}")
    
    if ports_in_use:
        log_warning(f"Ports in use: {', '.join(map(str, ports_in_use))}")
    
    # Check for existing Docker containers
    result = subprocess.run(
        ['docker', 'ps', '-q', '--filter', 'name=neuroinsight'],
        capture_output=True, text=True, check=False
    )
    if result.returncode == 0 and result.stdout.strip():
        container_count = len(result.stdout.strip().split('\n'))
        conflicts_found.append("Docker containers")
        log_warning(f"Found {container_count} NeuroInsight Docker container(s) already running")
    
    # If conflicts found, show warning and prompt
    if conflicts_found:
        print()
        log_error("CONFLICT DETECTED: NeuroInsight appears to be already running!")
        print()
        print(f"{RED}Conflicts found:{NC}")
        for conflict in set(conflicts_found):
            print(f"  • {conflict}")
        print()
        print(f"{YELLOW}This usually means:{NC}")
        print("  1. NeuroInsight is already running (use './neuroinsight status' to check)")
        print("  2. A previous shutdown didn't complete cleanly")
        print()
        print(f"{BLUE}What to do:{NC}")
        print(f"  • Stop existing instance first: {GREEN}./neuroinsight stop{NC}")
        print(f"  • Check status: {GREEN}./neuroinsight status{NC}")
        print(f"  • Or force cleanup and continue: Press {GREEN}Y{NC} to continue anyway")
        print()
        
        # Ask user what to do
        try:
            response = input(f"{YELLOW}Force cleanup and continue? [y/N]:{NC} ").strip().lower()
            if response != 'y':
                log_info("Startup cancelled by user")
                log_info(f"Run '{GREEN}./neuroinsight stop{NC}' first, then try starting again")
                sys.exit(1)
            else:
                log_warning("User chose to force cleanup and continue")
                return True  # Will clean up existing processes
        except KeyboardInterrupt:
            print()
            log_info("Startup cancelled by user")
            sys.exit(1)
    
    return False  # No conflicts

def main():
    print("=" * 50)
    print("   NeuroInsight Startup (Python-based)")
    print("=" * 50)
    print()

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Check for conflicts before starting
    force_cleanup = check_for_conflicts()

    # Clean up existing processes if needed
    if force_cleanup:
        log_info("Cleaning up existing NeuroInsight processes...")
        killed = find_and_kill_processes()
    else:
        log_info("No conflicts detected, proceeding with startup...")
        killed = 0

    # Start Docker services
    if not start_docker_services():
        log_error("Failed to start Docker services")
        sys.exit(1)

    # Find available port in range 8000-8050
    port = None
    for candidate_port in range(8000, 8051):
        if check_port_available(candidate_port):
            port = candidate_port
            log_success(f"Selected port: {port}")
            break
    
    if port is None:
        log_error("No available ports found in range 8000-8050")
        log_error("Please stop other services or free up a port in this range")
        sys.exit(1)

    # Start backend
    backend_proc = start_backend(port)
    if not backend_proc:
        log_error("Failed to start backend")
        sys.exit(1)

    # Start Celery worker
    celery_proc = start_celery()
    if not celery_proc:
        log_warning("Celery worker failed to start - continuing anyway")

    # Start Celery Beat (periodic task scheduler)
    beat_proc = start_celery_beat()
    if not beat_proc:
        log_warning("Celery Beat failed to start - continuing anyway")

    # Start job monitor
    monitor_proc = start_job_monitor()
    if not monitor_proc:
        log_warning("Job monitor failed to start - continuing anyway")

    # Start job queue processor only outside production
    queue_proc = start_job_queue_processor()
    if not queue_proc and os.environ.get("ENVIRONMENT", "production") != "production":
        log_warning("Job queue processor failed to start - continuing anyway")

    print()
    print("=" * 50)
    log_success("NeuroInsight is running!")
    print(f"   Web Interface: http://localhost:{port}")
    print(f"   API Docs: http://localhost:{port}/docs")
    print(f"   Health Check: http://localhost:{port}/health")
    print()
    print("Management commands:")
    print("  ./neuroinsight status    # Check system status")
    print("  ./neuroinsight stop      # Stop all services")
    print("  ./neuroinsight monitor   # Advanced monitoring")
    print("=" * 50)

if __name__ == "__main__":
    main()
