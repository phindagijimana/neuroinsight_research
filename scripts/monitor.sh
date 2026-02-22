#!/bin/bash
# NeuroInsight Process Monitor
# Monitors and manages NeuroInsight processes with automatic cleanup

set -e

# Configuration
CLEANUP_GRACE_PERIOD_MINUTES=180  # 3 hour grace period
MONITOR_STATE_FILE="/tmp/neuroinsight_monitor_state.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[MONITOR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[MONITOR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[MONITOR]${NC} $1"
}

log_error() {
    echo -e "${RED}[MONITOR]${NC} $1"
}

log_cleanup() {
    echo -e "${PURPLE}[CLEANUP]${NC} $1"
}

# Function to check if a process is actually responding
check_process_health() {
    local pid=$1
    local name=$2

    if [ ! -d "/proc/$pid" ]; then
        echo "dead"
        return
    fi

    # Check if process is responsive (not zombie)
    local stat=$(cat /proc/$pid/stat 2>/dev/null | awk '{print $3}')
    if [ "$stat" = "Z" ]; then
        echo "zombie"
        return
    fi

    # Additional health check based on process type
    case $name in
        "backend")
            if curl -s --max-time 5 http://localhost:8000/health > /dev/null 2>&1; then
                echo "healthy"
            else
                echo "unresponsive"
            fi
            ;;
        "celery")
            # For Celery, just check if process exists and is not zombie
            echo "running"
            ;;
        *)
            echo "running"
            ;;
    esac
}

# Function to initialize or load monitor state
load_monitor_state() {
    if [ -f "$MONITOR_STATE_FILE" ]; then
        cat "$MONITOR_STATE_FILE" 2>/dev/null || echo "{}"
    else
        echo "{}"
    fi
}

# Function to save monitor state
save_monitor_state() {
    local state="$1"
    echo "$state" > "$MONITOR_STATE_FILE.tmp" && mv "$MONITOR_STATE_FILE.tmp" "$MONITOR_STATE_FILE"
}

# Function to add item to tracking
track_item() {
    local item_type="$1"  # "process" or "job"
    local item_id="$2"
    local timestamp=$(date +%s)

    local state=$(load_monitor_state)
    local updated_state=$(echo "$state" | python3 -c "
import sys, json, time
state = json.load(sys.stdin)
item_type = sys.argv[1]
item_id = sys.argv[2]
timestamp = int(sys.argv[3])

if item_type not in state:
    state[item_type] = {}

state[item_type][item_id] = {
    'first_detected': timestamp,
    'last_seen': timestamp,
    'status': 'tracked'
}

print(json.dumps(state, indent=2))
" "$item_type" "$item_id" "$timestamp")

    save_monitor_state "$updated_state"
}

# Function to check if item should be cleaned up
should_cleanup_item() {
    local item_type="$1"
    local item_id="$2"

    local state=$(load_monitor_state)
    local result=$(echo "$state" | python3 -c "
import sys, json, time
state = json.load(sys.stdin)
item_type = sys.argv[1]
item_id = sys.argv[2]
grace_period = int(sys.argv[3]) * 60  # Convert to seconds

current_time = time.time()

if item_type in state and item_id in state[item_type]:
    first_detected = state[item_type][item_id]['first_detected']
    if current_time - first_detected > grace_period:
        print('cleanup')
    else:
        print('wait')
else:
    print('not_tracked')
" "$item_type" "$item_id" "$CLEANUP_GRACE_PERIOD_MINUTES")

    echo "$result"
}

# Function to remove item from tracking
untrack_item() {
    local item_type="$1"
    local item_id="$2"

    local state=$(load_monitor_state)
    local updated_state=$(echo "$state" | python3 -c "
import sys, json
state = json.load(sys.stdin)
item_type = sys.argv[1]
item_id = sys.argv[2]

if item_type in state and item_id in state[item_type]:
    del state[item_type][item_id]

print(json.dumps(state, indent=2))
" "$item_type" "$item_id")

    save_monitor_state "$updated_state"
}

# Function to clean up orphaned processes with grace period
cleanup_processes() {
    log_info "Checking for orphaned NeuroInsight processes..."

    local cleaned=0
    local tracked=0

    # Find all Python processes related to NeuroInsight
    local pids=$(pgrep -f "python3.*neuroinsight\|python3.*backend\|python3.*celery.*processing_web" 2>/dev/null || true)

    for pid in $pids; do
        if [ -n "$pid" ] && [ "$pid" != "$$" ]; then  # Don't kill ourselves
            local cmdline=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ' || echo "unknown")
            local health=$(check_process_health $pid "unknown")

            if [ "$health" = "dead" ] || [ "$health" = "zombie" ] || [ "$health" = "unresponsive" ]; then
                log_warning "Found unhealthy process: PID $pid (Status: $health)"
                log_warning "Command: $cmdline"

                # Check if we should clean up immediately or wait
                local cleanup_action=$(should_cleanup_item "process" "$pid")

                if [ "$cleanup_action" = "cleanup" ]; then
                    log_cleanup "[CLEANUP] AUTO-CLEANUP: Orphaned process PID $pid (tracked for >${CLEANUP_GRACE_PERIOD_MINUTES}min = 3 hours)"

                    # Kill the process
                    if kill -15 $pid 2>/dev/null; then
                        log_success "Sent SIGTERM to PID $pid"
                        # Wait a moment for graceful shutdown
                        sleep 2
                        if kill -0 $pid 2>/dev/null; then
                            kill -9 $pid 2>/dev/null || true
                            log_warning "Force killed PID $pid"
                        fi
                    fi

                    # Remove from tracking
                    untrack_item "process" "$pid"
                    cleaned=$((cleaned + 1))
                else
                    # Track for future cleanup
                    track_item "process" "$pid"
                    log_warning "Tracking orphaned process PID $pid for auto-cleanup in ${CLEANUP_GRACE_PERIOD_MINUTES}min (3 hours)"
                    tracked=$((tracked + 1))
                fi
            fi
        fi
    done

    if [ $cleaned -gt 0 ]; then
        log_success "[CLEANUP] Auto-cleaned up $cleaned orphaned process(es) after ${CLEANUP_GRACE_PERIOD_MINUTES}min (3 hours) grace period"
    fi

    if [ $tracked -gt 0 ]; then
        log_info "Tracking $tracked orphaned process(es) for future auto-cleanup"
    fi

    if [ $cleaned -eq 0 ] && [ $tracked -eq 0 ]; then
        log_info "No orphaned processes found"
    fi
}

# Function to check system resources
check_resources() {
    log_info "Checking system resources..."

    # Memory usage
    local mem_percent=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ $mem_percent -gt 90 ]; then
        log_error "CRITICAL: Memory usage at ${mem_percent}%"
    elif [ $mem_percent -gt 75 ]; then
        log_warning "WARNING: High memory usage at ${mem_percent}%"
    else
        log_success "Memory usage: ${mem_percent}%"
    fi

    # Disk usage
    local disk_percent=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ $disk_percent -gt 95 ]; then
        log_error "CRITICAL: Disk usage at ${disk_percent}%"
    elif [ $disk_percent -gt 85 ]; then
        log_warning "WARNING: High disk usage at ${disk_percent}%"
    else
        log_success "Disk usage: ${disk_percent}%"
    fi

    # Check for NeuroInsight-specific resource issues
    if [ -d "data/outputs" ]; then
        local output_size=$(du -sm data/outputs 2>/dev/null | cut -f1 || echo "0")
        if [ "$output_size" -gt 1000 ]; then  # More than 1GB
            log_warning "Large output directory: ${output_size}MB - consider cleanup"
        fi
    fi
}

# Function to check job health and cleanup stuck jobs
check_jobs() {
    log_info "Checking job health and stuck jobs..."

    # Check if we can connect to the API
    if curl -s --max-time 5 http://localhost:8000/api/jobs/stats > /dev/null 2>&1; then
        local status_json=$(curl -s http://localhost:8000/api/jobs/stats)

        # Extract job counts
        local running=$(echo "$status_json" | python3 -c "import sys, json; print(json.load(sys.stdin).get('jobs', {}).get('running', 0))" 2>/dev/null || echo "0")
        local pending=$(echo "$status_json" | python3 -c "import sys, json; print(json.load(sys.stdin).get('jobs', {}).get('pending', 0))" 2>/dev/null || echo "0")
        local failed=$(echo "$status_json" | python3 -c "import sys, json; print(json.load(sys.stdin).get('jobs', {}).get('failed', 0))" 2>/dev/null || echo "0")

        log_info "Job status - Running: $running, Pending: $pending, Failed: $failed"

        # Check for stuck jobs via database
        if [ "$running" -gt 0 ] || [ "$pending" -gt 0 ]; then
            log_info "Checking for stuck jobs in database..."

            # Use Python to check for stuck jobs
            local stuck_check=$(python3 -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import get_db
from backend.models.job import Job, JobStatus
from datetime import datetime, timedelta
import json

try:
    db = next(get_db())
    now = datetime.utcnow()

    # Find running jobs stuck for > 5 hours
    stuck_running = db.query(Job).filter(
        Job.status == JobStatus.RUNNING,
        Job.started_at < (now - timedelta(hours=5))
    ).all()

    # Find pending jobs stuck for > 5 hours
    stuck_pending = db.query(Job).filter(
        Job.status == JobStatus.PENDING,
        Job.created_at < (now - timedelta(hours=5))
    ).all()

    stuck_jobs = []
    for job in stuck_running + stuck_pending:
        stuck_jobs.append({
            'id': str(job.id),
            'status': job.status.value,
            'age_hours': (now - (job.started_at or job.created_at)).total_seconds() / 3600
        })

    print(json.dumps(stuck_jobs))

except Exception as e:
    print('[]')
" 2>/dev/null || echo "[]")

            # Process stuck jobs
            local stuck_count=$(echo "$stuck_check" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

            if [ "$stuck_count" -gt 0 ]; then
                log_warning "Found $stuck_count potentially stuck job(s)"

                # Process each stuck job
                echo "$stuck_check" | python3 -c "
import sys, json
stuck_jobs = json.load(sys.stdin)

for job in stuck_jobs:
    job_id = job['id']
    status = job['status']
    age_hours = job['age_hours']
    
    cleanup_action = input(f'Job {job_id} ({status}) stuck for {age_hours:.1f}h - cleanup? (y/n): ')
    if cleanup_action.lower() == 'y':
        print(f'AUTO_CLEANUP_JOB:{job_id}')
" 2>/dev/null | while read -r line; do
                    if [[ "$line" == AUTO_CLEANUP_JOB:* ]]; then
                        local job_id=$(echo "$line" | cut -d: -f2)
                        log_cleanup "[CLEANUP] AUTO-CLEANUP: Stuck job $job_id"

                        # Track the job for cleanup
                        local cleanup_action=$(should_cleanup_item "job" "$job_id")
                        if [ "$cleanup_action" = "cleanup" ]; then
                            # Actually cleanup the job
                            python3 -c "
import sys
sys.path.insert(0, '.')
from backend.core.database import get_db
from backend.services.job_service import JobService
from backend.models.job import JobStatus

try:
    db = next(get_db())
    job_id = '$job_id'
    
    # Fail the stuck job
    JobService.fail_job(db, job_id, f'Auto-cleaned: Stuck job after ${CLEANUP_GRACE_PERIOD_MINUTES}min grace period')
    
    # Process next job in queue
    JobService.process_job_queue(db)
    
    print('CLEANED_JOB:$job_id')
except Exception as e:
    print('ERROR:$job_id')
" 2>/dev/null | while read -r result; do
                                if [[ "$result" == CLEANED_JOB:* ]]; then
                                    log_success "Successfully cleaned stuck job $job_id"
                                    untrack_item "job" "$job_id"
                                elif [[ "$result" == ERROR:* ]]; then
                                    log_error "Failed to clean stuck job $job_id"
                                fi
                            done
                        else
                            # Track for future cleanup
                            track_item "job" "$job_id"
                            log_warning "Tracking stuck job $job_id for auto-cleanup in ${CLEANUP_GRACE_PERIOD_MINUTES}min"
                        fi
                    fi
                done
            fi
        fi

        if [ "$failed" -gt 10 ]; then
            log_error "CRITICAL: Very high number of failed jobs ($failed) - system may need attention"
        elif [ "$failed" -gt 5 ]; then
            log_warning "High number of failed jobs ($failed) - check system health"
        fi

    else
        log_error "Cannot connect to NeuroInsight API - jobs cannot be monitored"
    fi
}

# Function to show tracking status
show_tracking_status() {
    log_info "Current tracking status:"

    local state=$(load_monitor_state)

    # Count tracked items
    local tracked_processes=$(echo "$state" | python3 -c "
import sys, json, time
state = json.load(sys.stdin)
processes = state.get('processes', {})
jobs = state.get('jobs', {})

current_time = time.time()
grace_period = $CLEANUP_GRACE_PERIOD_MINUTES * 60

ready_cleanup = 0
waiting = 0

for item_type, items in [('processes', processes), ('jobs', jobs)]:
    for item_id, data in items.items():
        first_detected = data['first_detected']
        if current_time - first_detected > grace_period:
            ready_cleanup += 1
        else:
            waiting += 1

print(f'{ready_cleanup},{waiting}')
" 2>/dev/null || echo "0,0")

    local ready_cleanup=$(echo "$tracked_processes" | cut -d, -f1)
    local waiting=$(echo "$tracked_processes" | cut -d, -f2)

    if [ "$ready_cleanup" -gt 0 ]; then
        log_cleanup "[CLEANUP] $ready_cleanup item(s) ready for auto-cleanup (> ${CLEANUP_GRACE_PERIOD_MINUTES}min old)"
    fi

    if [ "$waiting" -gt 0 ]; then
        log_info "$waiting item(s) being tracked for future cleanup"
    fi

    if [ "$ready_cleanup" -eq 0 ] && [ "$waiting" -eq 0 ]; then
        log_success "No items currently being tracked for cleanup"
    fi
}

# Main monitoring logic
main() {
    echo "========================================"
    echo "   NeuroInsight Auto-Cleanup Monitor"
    echo "   Grace Period: ${CLEANUP_GRACE_PERIOD_MINUTES} minutes (3 hours)"
    echo "========================================"
    echo

    # Parse command line arguments
    case "${1:-}" in
        "cleanup")
            cleanup_processes
            echo
            check_jobs
            ;;
        "resources")
            check_resources
            ;;
        "jobs")
            check_jobs
            ;;
        "status")
            show_tracking_status
            ;;
        "full"|*)
            cleanup_processes
            echo
            check_resources
            echo
            check_jobs
            echo
            show_tracking_status
            ;;
    esac

    echo
    echo "========================================"
    echo "Monitor commands:"
    echo "  ./monitor.sh          # Full check with auto-cleanup"
    echo "  ./monitor.sh cleanup  # Clean orphaned processes & stuck jobs"
    echo "  ./monitor.sh resources# Check system resources"
    echo "  ./monitor.sh jobs     # Check job health"
    echo "  ./monitor.sh status   # Show tracking status"
    echo "========================================"
}

# Run main function
main "$@"
