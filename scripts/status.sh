#!/bin/bash
# NeuroInsight Status Script
# Check the status of all NeuroInsight services

set -e

# Colors for output
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
echo "    NeuroInsight System Status Check"
echo "========================================"
echo

# Check if services are running
log_info "Checking service status..."

# Check backend API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    log_success "Backend API is running"
else
    log_error "Backend API is not responding"
fi

# Check Celery workers
CELERY_COUNT=$(pgrep -f "celery.*processing_web" | wc -l)
if [ $CELERY_COUNT -gt 0 ]; then
    log_success "Celery workers running: $CELERY_COUNT process(es)"
else
    log_error "No Celery workers found"
fi

# Check job monitor
if pgrep -f "job_monitor" > /dev/null 2>&1; then
    log_success "Job monitor is running"
else
    log_warning "Job monitor not found (may be started by backend)"
fi

# Check Docker containers
DOCKER_COUNT=$(docker ps | grep neuroinsight | wc -l)
if [ $DOCKER_COUNT -gt 0 ]; then
    log_success "Docker containers running: $DOCKER_COUNT"
    echo "   Containers:"
    docker ps --filter name=neuroinsight --format "table {{.Names}}\t{{.Status}}"
else
    log_info "No NeuroInsight Docker containers running"
fi

echo

# Get system status from API
log_info "Fetching system status..."
if curl -s http://localhost:8000/api/jobs/stats > /dev/null 2>&1; then
    STATUS_JSON=$(curl -s http://localhost:8000/api/jobs/stats)
    echo "System Status:"
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
    log_warning "Could not fetch detailed system status"
fi

echo

# Check recent jobs
log_info "Checking recent job activity..."
JOBS_JSON=$(curl -s http://localhost:8000/api/jobs/)
if [ $? -eq 0 ] && [ "$JOBS_JSON" != "" ]; then
    JOB_COUNT=$(echo "$JOBS_JSON" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('jobs', [])))")
    echo "Recent jobs: $JOB_COUNT found"
    
    # Show last few jobs
    echo "$JOBS_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = data.get('jobs', [])[:3]  # Show first 3
for job in jobs:
    status = job.get('status', 'unknown')
    filename = job.get('filename', 'unknown')[:30]
    print(f'  {job.get(\"id\", \"unknown\")} - {filename} - {status}')
"
else
    log_warning "Could not fetch job information"
fi

echo

# Check port usage
log_info "Checking port usage..."
if command -v netstat &> /dev/null; then
    PORT_8000=$(netstat -tln 2>/dev/null | grep :8000 || echo "")
    if [ ! -z "$PORT_8000" ]; then
        log_success "Port 8000 is in use (expected)"
    else
        log_warning "Port 8000 is not in use"
    fi
else
    log_info "netstat not available, skipping port check"
fi

echo
echo "========================================"
echo "For detailed logs:"
echo "  Backend: tail -f neuroinsight.log"
echo "  Celery:  tail -f celery_worker.log"
echo ""
echo "To restart services:"
echo "  ./neuroinsight stop && ./neuroinsight start"
echo ""
echo "To check job details:"
echo "  curl http://localhost:8000/api/jobs/{job_id}"
echo "========================================"