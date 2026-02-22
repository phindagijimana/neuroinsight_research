# View NeuroInsight logs

param(
    [string]$Service = "all",
    [switch]$Follow
)

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

# Check if container is running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -ne $ContainerName) {
    Write-Error "Container is not running"
    exit 1
}

$followArg = if ($Follow) { "-f" } else { "" }

switch ($Service) {
    "backend" {
        Write-Info "Showing backend logs (Ctrl+C to exit)..."
        docker exec $ContainerName tail $followArg /var/log/supervisor/backend.log
    }
    "worker" {
        Write-Info "Showing worker logs (Ctrl+C to exit)..."
        docker exec $ContainerName tail $followArg /var/log/supervisor/worker.log
    }
    "postgresql" {
        Write-Info "Showing PostgreSQL logs (Ctrl+C to exit)..."
        docker exec $ContainerName tail $followArg /var/log/supervisor/postgresql.log
    }
    "redis" {
        Write-Info "Showing Redis logs (Ctrl+C to exit)..."
        docker exec $ContainerName tail $followArg /var/log/supervisor/redis.log
    }
    "minio" {
        Write-Info "Showing MinIO logs (Ctrl+C to exit)..."
        docker exec $ContainerName tail $followArg /var/log/supervisor/minio.log
    }
    default {
        Write-Info "Showing all container logs (Ctrl+C to exit)..."
        if ($Follow) {
            docker logs -f $ContainerName
        } else {
            docker logs --tail 100 $ContainerName
        }
    }
}
