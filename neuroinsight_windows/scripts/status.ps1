# Check NeuroInsight status

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NeuroInsight Docker Status" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if container exists
$containerExists = docker ps -a --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerExists -ne $ContainerName) {
    Write-Error "Container does not exist"
    Write-Host "Run install.ps1 to create the container"
    exit 1
}

# Check if running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -eq $ContainerName) {
    Write-Success "Container is running"
    Write-Host ""
    
    # Get port
    $portMapping = docker port $ContainerName 8000 2>$null
    if ($portMapping) {
        $port = $portMapping -replace '.*:', ''
        Write-Host "Web Interface: " -NoNewline
        Write-Host "http://localhost:$port" -ForegroundColor Cyan
        Write-Host ""
    }
    
    # Show container info
    Write-Info "Container details:"
    docker ps --filter "name=^${ContainerName}$" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    Write-Host ""
    
    # Show service status
    Write-Info "Service status:"
    try {
        docker exec $ContainerName supervisorctl status 2>$null
    } catch {
        Write-Warning "Could not get service status"
    }
} else {
    Write-Warning "Container exists but is not running"
    Write-Host "Run: .\scripts\start.ps1"
}

Write-Host ""
