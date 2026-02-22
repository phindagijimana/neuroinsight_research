#!/bin/bash
# Health check script for NeuroInsight all-in-one container
# Checks that all critical services are running

set -e

# Function to check if a service is running
check_service() {
    service_name=$1
    check_command=$2
    
    if eval "$check_command" > /dev/null 2>&1; then
        echo "✓ $service_name is healthy"
        return 0
    else
        echo "✗ $service_name is not responding"
        return 1
    fi
}

# Check PostgreSQL
check_service "PostgreSQL" "pg_isready -U neuroinsight -h localhost" || exit 1

# Check Redis
check_service "Redis" "redis-cli -a redis_secure_password ping" || exit 1

# Check MinIO
check_service "MinIO" "curl -f http://localhost:9000/minio/health/live" || exit 1

# Check Backend API
check_service "Backend API" "curl -f http://localhost:8000/health" || exit 1

# All checks passed
echo "All services are healthy"
exit 0
