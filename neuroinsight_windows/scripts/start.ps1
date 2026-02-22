# Start NeuroInsight container

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Info "Starting NeuroInsight container..."

# Check if container exists
$containerExists = docker ps -a --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerExists -ne $ContainerName) {
    Write-Error "Container not found. Please run install.ps1 first"
    exit 1
}

# Check if already running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -eq $ContainerName) {
    Write-Warning "Container is already running"
    
    # Get port
    $portMapping = docker port $ContainerName 8000 2>$null
    if ($portMapping) {
        $port = $portMapping -replace '.*:', ''
        Write-Host "Web Interface: http://localhost:$port" -ForegroundColor Cyan
    }
    
    exit 0
}

# Start container
try {
    docker start $ContainerName | Out-Null
    Write-Success "Container started"
    
    Start-Sleep -Seconds 5
    
    # Get port
    $portMapping = docker port $ContainerName 8000 2>$null
    if ($portMapping) {
        $port = $portMapping -replace '.*:', ''
        Write-Host ""
        Write-Success "NeuroInsight is ready!"
        Write-Host "Web Interface: http://localhost:$port" -ForegroundColor Cyan
        Write-Host ""
    }
} catch {
    Write-Error "Failed to start container: $_"
    exit 1
}
