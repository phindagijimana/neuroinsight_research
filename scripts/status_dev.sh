#!/bin/bash
# NeuroInsight Dev Status Script
# Check the status of dev backend services

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "========================================"
echo "  NeuroInsight Dev System Status Check"
echo "========================================"
echo

log_info "Checking dev backend..."
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    log_success "Dev backend API is running"
else
    log_error "Dev backend API is not responding"
fi

log_info "Checking dev process PID files..."
for pidfile in dev_backend.pid dev_celery.pid dev_job_monitor.pid dev_job_queue_processor.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile" 2>/dev/null || echo "")
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
            log_success "$pidfile (PID $pid) is running"
        else
            log_warning "$pidfile exists but process not running"
        fi
    else
        log_warning "$pidfile not found"
    fi
done

echo

log_info "Fetching dev system status..."
if curl -s http://localhost:8001/api/jobs/stats > /dev/null 2>&1; then
    STATUS_JSON=$(curl -s http://localhost:8001/api/jobs/stats)
    echo "Dev System Status:"
    echo "$STATUS_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'  Status: {data.get(\"status\", \"unknown\")}')
print(f'  Jobs - Total: {data.get(\"jobs\", {}).get(\"total\", 0)}, Running: {data.get(\"jobs\", {}).get(\"running\", 0)}, Pending: {data.get(\"jobs\", {}).get(\"pending\", 0)}, Failed: {data.get(\"jobs\", {}).get(\"failed\", 0)}')
print(f'  Success rate: {data.get(\"jobs\", {}).get(\"success_rate\", 0)}%')
print(f'  Avg processing time: {data.get(\"performance\", {}).get(\"avg_processing_time_seconds\", \"n/a\")}s')
print(f'  Queue size: {data.get(\"system\", {}).get(\"queue_size\", 0)}')
print(f'  Storage used: {data.get(\"system\", {}).get(\"storage_used_mb\", 0)} MB')
"
else
    log_warning "Could not fetch dev system status"
fi

echo

log_info "Checking dev jobs..."
JOBS_JSON=$(curl -s http://localhost:8001/api/jobs/)
if [ $? -eq 0 ] && [ "$JOBS_JSON" != "" ]; then
    JOB_COUNT=$(echo "$JOBS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('jobs', [])))")
    echo "Dev jobs: $JOB_COUNT found"
    echo "$JOBS_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = data.get('jobs', [])[:3]
for job in jobs:
    status = job.get('status', 'unknown')
    filename = job.get('filename', 'unknown')[:30]
    print(f'  {job.get(\"id\", \"unknown\")} - {filename} - {status}')
"
else
    log_warning "Could not fetch dev job information"
fi

echo
log_info "Checking port 8001..."
if command -v netstat &> /dev/null; then
    PORT_8001=$(netstat -tln 2>/dev/null | grep :8001 || echo "")
    if [ ! -z "$PORT_8001" ]; then
        log_success "Port 8001 is in use (expected)"
    else
        log_warning "Port 8001 is not in use"
    fi
else
    log_info "netstat not available, skipping port check"
fi

echo
echo "========================================"
echo "Dev logs:"
echo "  Backend: tail -f dev_backend.log"
echo "  Celery:  tail -f dev_celery_worker.log"
echo "========================================"


