# Stop NeuroInsight container

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Info "Stopping NeuroInsight container..."

# Check if container exists
$containerExists = docker ps -a --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerExists -ne $ContainerName) {
    Write-Error "Container not found"
    exit 1
}

# Check if running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -ne $ContainerName) {
    Write-Warning "Container is not running"
    exit 0
}

# Stop container
try {
    docker stop $ContainerName | Out-Null
    Write-Success "Container stopped"
} catch {
    Write-Error "Failed to stop container: $_"
    exit 1
}
