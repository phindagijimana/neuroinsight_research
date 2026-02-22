#!/usr/bin/env python3
"""
NeuroInsight Log Viewer
View logs from different components of the system.
"""

import sys
import os
import subprocess
from pathlib import Path

# Available log sources
LOG_SOURCES = {
    'backend': {
        'file': 'neuroinsight.log',
        'description': 'Backend API server logs',
        'tail_lines': 100
    },
    'celery': {
        'file': 'celery_worker.log',
        'description': 'Celery worker (job processing) logs',
        'tail_lines': 100
    },
    'beat': {
        'file': 'celery_beat.log',
        'description': 'Celery beat scheduler logs',
        'tail_lines': 50
    },
    'monitor': {
        'file': 'job_monitor.log',
        'description': 'Job monitoring service logs',
        'tail_lines': 50
    },
    'freesurfer': {
        'description': 'FreeSurfer processing logs (requires job ID)',
        'requires_job_id': True
    },
    'database': {
        'description': 'PostgreSQL database logs',
        'command': 'docker logs neuroinsight-postgres'
    },
    'redis': {
        'description': 'Redis message broker logs',
        'command': 'docker logs neuroinsight-redis'
    }
}


def show_usage():
    print("Usage: neuroinsight logs [SOURCE] [OPTIONS]")
    print()
    print("Available log sources:")
    for source, info in LOG_SOURCES.items():
        print(f"  {source:<12} - {info['description']}")
    print()
    print("Options:")
    print("  -f, --follow     Follow log output (tail -f)")
    print("  -n, --lines N    Number of lines to show (default: 100)")
    print("  --job-id ID      Job ID (for freesurfer logs)")
    print()
    print("Examples:")
    print("  neuroinsight logs backend")
    print("  neuroinsight logs backend --follow")
    print("  neuroinsight logs celery -n 50")
    print("  neuroinsight logs freesurfer --job-id abc123")
    print("  neuroinsight logs                    # Interactive menu")


def show_log_file(filepath, lines=100, follow=False):
    """Show log file contents."""
    if not os.path.exists(filepath):
        print(f"ERROR: Log file not found: {filepath}")
        return False
    
    cmd = ['tail', f'-n{lines}']
    if follow:
        cmd.append('-f')
    cmd.append(filepath)
    
    try:
        subprocess.run(cmd)
        return True
    except KeyboardInterrupt:
        print("\n\nLog viewing interrupted.")
        return True
    except Exception as e:
        print(f"ERROR: Error reading log: {e}")
        return False


def show_docker_log(container_name, lines=100, follow=False):
    """Show Docker container logs."""
    cmd = ['docker', 'logs']
    if follow:
        cmd.append('-f')
    cmd.extend(['--tail', str(lines), container_name])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if 'No such container' in result.stderr:
                print(f"ERROR: Container '{container_name}' is not running")
            else:
                print(f"ERROR: {result.stderr}")
            return False
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        return True
    except Exception as e:
        print(f"ERROR: Error reading Docker logs: {e}")
        return False


def show_freesurfer_logs(job_id, lines=100, follow=False):
    """Show FreeSurfer logs for a specific job."""
    from backend.core.config import get_settings
    
    settings = get_settings()
    output_dir = Path(settings.output_dir) / job_id
    
    if not output_dir.exists():
        print(f"ERROR: Job output directory not found: {output_dir}")
        return False
    
    # Check for FreeSurfer logs
    log_files = [
        output_dir / 'freesurfer' / 'freesurfer_docker' / f'freesurfer_docker_{job_id}' / 'scripts' / 'recon-all.log',
        output_dir / 'freesurfer' / 'freesurfer_docker' / f'freesurfer_docker_{job_id}' / 'scripts' / 'recon-all-status.log',
    ]
    
    found = False
    for log_file in log_files:
        if log_file.exists():
            print(f"\n{'='*70}")
            print(f"LOG: {log_file.name}")
            print('='*70)
            show_log_file(str(log_file), lines, follow)
            found = True
            if not follow:
                print()
    
    if not found:
        print(f"ERROR: No FreeSurfer logs found for job {job_id}")
        print(f"       Checked: {output_dir}")
    
    return found


def interactive_menu():
    """Show interactive menu for log selection."""
    print("\n" + "="*70)
    print("NeuroInsight Log Viewer")
    print("="*70)
    print("\nSelect log source:")
    print()
    
    sources = list(LOG_SOURCES.keys())
    for i, source in enumerate(sources, 1):
        info = LOG_SOURCES[source]
        print(f"  {i}. {source:<12} - {info['description']}")
    
    print(f"  {len(sources)+1}. All logs     - Show all available logs")
    print("  0. Exit")
    print()
    
    try:
        choice = input("Enter choice [0-{}]: ".format(len(sources)+1)).strip()
        
        if choice == '0':
            return
        
        choice_num = int(choice)
        
        if choice_num == len(sources) + 1:
            # Show all logs
            for source in sources:
                if source == 'freesurfer':
                    continue  # Skip freesurfer (needs job ID)
                print(f"\n{'='*70}")
                print(f"{source.upper()} LOGS")
                print('='*70)
                show_logs(source, lines=50, follow=False)
        elif 1 <= choice_num <= len(sources):
            source = sources[choice_num - 1]
            
            if source == 'freesurfer':
                job_id = input("Enter job ID: ").strip()
                if job_id:
                    show_freesurfer_logs(job_id, lines=100, follow=False)
            else:
                show_logs(source, lines=100, follow=False)
        else:
            print("ERROR: Invalid choice")
    
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")


def show_logs(source, lines=100, follow=False):
    """Show logs for specified source."""
    if source not in LOG_SOURCES:
        print(f"ERROR: Unknown log source: {source}")
        print(f"       Available: {', '.join(LOG_SOURCES.keys())}")
        return False
    
    info = LOG_SOURCES[source]
    
    if info.get('requires_job_id'):
        print(f"ERROR: {source} logs require a job ID")
        print(f"       Use: neuroinsight logs {source} --job-id <ID>")
        return False
    
    if 'command' in info:
        # Docker container logs
        container = info['command'].split()[-1]
        return show_docker_log(container, lines, follow)
    elif 'file' in info:
        # File logs
        return show_log_file(info['file'], lines, follow)
    
    return False


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    if not args:
        # No arguments - show interactive menu
        interactive_menu()
        return
    
    # Parse arguments
    source = None
    lines = 100
    follow = False
    job_id = None
    
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg in ['-h', '--help']:
            show_usage()
            return
        elif arg in ['-f', '--follow']:
            follow = True
        elif arg in ['-n', '--lines']:
            i += 1
            if i < len(args):
                try:
                    lines = int(args[i])
                except ValueError:
                    print(f"ERROR: Invalid number: {args[i]}")
                    sys.exit(1)
        elif arg == '--job-id':
            i += 1
            if i < len(args):
                job_id = args[i]
        elif not source:
            source = arg
        else:
            print(f"ERROR: Unknown argument: {arg}")
            show_usage()
            sys.exit(1)
        
        i += 1
    
    # Show logs
    if not source:
        show_usage()
        return
    
    if source == 'freesurfer':
        if not job_id:
            print("ERROR: FreeSurfer logs require a job ID")
            print("       Use: neuroinsight logs freesurfer --job-id <ID>")
            sys.exit(1)
        show_freesurfer_logs(job_id, lines, follow)
    else:
        show_logs(source, lines, follow)


if __name__ == '__main__':
    main()
