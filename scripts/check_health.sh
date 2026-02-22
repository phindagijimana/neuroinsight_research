#!/bin/bash
# NeuroInsight Health Check Script
# Run this periodically via cron to monitor system health

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/neuroinsight_health.log"
ALERT_EMAIL=""  # Set this to receive email alerts

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
    echo -e "$1"
}

get_running_job_count() {
    # Return running job count; empty if API not reachable
    local response
    response=$(curl -s --max-time 5 http://localhost:8000/api/jobs/ 2>/dev/null || true)
    if [ -z "$response" ]; then
        echo ""
        return
    fi
    # Count jobs with status "running"
    echo "$response" | python3 -c "import sys, json; data = json.load(sys.stdin); jobs = data.get('jobs', []); running = [j for j in jobs if j.get('status') == 'running']; print(len(running))" 2>/dev/null || echo ""
}

alert() {
    local message="$1"
    log "${RED}ALERT: $message${NC}"

    # Send email alert if configured
    if [ -n "$ALERT_EMAIL" ]; then
        echo "NeuroInsight Alert: $message" | mail -s "NeuroInsight Health Alert" "$ALERT_EMAIL"
    fi
}

# Check system resources
check_resources() {
    log "Checking system resources..."

    # Memory check
    local mem_percent=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    log "Memory usage: ${mem_percent}%"

    if [ "$mem_percent" -gt 90 ]; then
        alert "High memory usage: ${mem_percent}%"
    fi

    # Disk check
    local disk_percent=$(df / | awk 'NR==2{print $5}' | sed 's/%//')
    log "Disk usage: ${disk_percent}%"

    if [ "$disk_percent" -gt 85 ]; then
        alert "High disk usage: ${disk_percent}%"
    fi
}

# Check Celery worker count
check_celery_workers() {
    log "Checking Celery workers..."
    
    # Count running Celery worker processes
    local worker_count=$(pgrep -f "celery.*worker.*processing_web" | wc -l)
    
    if [ "$worker_count" -eq 0 ]; then
        log "${RED}No Celery workers running${NC}"
        return 1
    elif [ "$worker_count" -gt 2 ]; then
        # More than 2 processes (parent + child) indicates multiple workers
        alert "Multiple Celery workers detected: $worker_count processes (expected 2)"
        log "${YELLOW}This could cause job processing conflicts${NC}"
        
        local running_jobs=$(get_running_job_count)
        if [ -n "$running_jobs" ] && [ "$running_jobs" -gt 0 ]; then
            log "${YELLOW}Skipping cleanup: ${running_jobs} job(s) currently running${NC}"
        else
            log "${YELLOW}Cleaning up duplicate workers...${NC}"
            pkill -9 -f "celery.*worker.*processing_web"
            sleep 2
            cd "$SCRIPT_DIR" && ./neuroinsight start celery
        fi
        return 1
    else
        log "${GREEN}Celery workers healthy: $worker_count processes${NC}"
        return 0
    fi
}

# Check Docker containers
check_containers() {
    log "Checking Docker containers..."

    if ! command -v docker &> /dev/null; then
        alert "Docker not available"
        return 1
    fi

    # Check required containers
    local containers=("neuroinsight-postgres" "neuroinsight-redis" "neuroinsight-minio")
    local all_healthy=true

    for container in "${containers[@]}"; do
        if ! docker ps --filter "name=$container" --format "{{.Names}}" | grep -q "$container"; then
            alert "Container $container is not running"
            all_healthy=false
        else
            log "${GREEN}Container $container is running${NC}"
        fi
    done

    # Check backend API
    if ! curl -s -f --max-time 5 http://localhost:8000/health >/dev/null 2>&1; then
        alert "Backend API is not responding"
        all_healthy=false
    else
        log "${GREEN}Backend API is responding${NC}"
    fi

    if [ "$all_healthy" = false ]; then
        local running_jobs=$(get_running_job_count)
        if [ -n "$running_jobs" ] && [ "$running_jobs" -gt 0 ]; then
            log "${YELLOW}Skipping restart: ${running_jobs} job(s) currently running${NC}"
            return 0
        fi
        
        # CRITICAL: Check if Celery workers are already running before starting
        local worker_count=$(pgrep -f "celery.*worker.*processing_web" | wc -l)
        if [ "$worker_count" -gt 0 ]; then
            log "${YELLOW}Celery workers already running ($worker_count processes), skipping restart${NC}"
            return 0
        fi
        
        log "${YELLOW}Attempting to restart services...${NC}"
        cd "$SCRIPT_DIR" && ./neuroinsight start
    fi
}

# Check for orphaned processes
check_processes() {
    log "Checking for orphaned processes..."

    # Check for orphaned NeuroInsight processes
    local orphaned=$(ps aux | grep -E "(python.*neuroinsight|celery.*neuroinsight)" | grep -v grep | wc -l)

    if [ "$orphaned" -gt 0 ]; then
        log "${YELLOW}Found $orphaned potential orphaned processes${NC}"
        local running_jobs=$(get_running_job_count)
        if [ -n "$running_jobs" ] && [ "$running_jobs" -gt 0 ]; then
            log "${YELLOW}Skipping cleanup: ${running_jobs} job(s) currently running${NC}"
            return 0
        fi
        # Run the monitor script to clean up
        cd "$SCRIPT_DIR" && ./neuroinsight monitor cleanup 2>/dev/null || true
    fi
}

# Main health check
main() {
    log "=== NeuroInsight Health Check Started ==="

    check_resources
    check_celery_workers
    check_containers
    check_processes

    log "${GREEN}Health check completed${NC}"
    log "=== NeuroInsight Health Check Finished ==="
    echo "" >> "$LOG_FILE"
}

# Run the health check
main "$@"
