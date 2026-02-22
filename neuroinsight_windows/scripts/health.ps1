# Check NeuroInsight health

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NeuroInsight System Health Check" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
Write-Info "Docker:"
try {
    $dockerVersion = docker --version
    Write-Success "  $dockerVersion"
} catch {
    Write-Error "  Docker not available"
}

# Check container
Write-Host ""
Write-Info "Container Status:"
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -eq $ContainerName) {
    Write-Success "  Container is running"
    
    # Get port
    $portMapping = docker port $ContainerName 8000 2>$null
    if ($portMapping) {
        $port = $portMapping -replace '.*:', ''
        Write-Host "  Web Interface: http://localhost:$port" -ForegroundColor Cyan
    }
} else {
    Write-Error "  Container is not running"
    Write-Host "  Run: .\scripts\start.ps1" -ForegroundColor Yellow
}

# Check API health
if ($containerRunning -eq $ContainerName) {
    Write-Host ""
    Write-Info "API Health:"
    try {
        $portMapping = docker port $ContainerName 8000 2>$null
        $port = $portMapping -replace '.*:', ''
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Success "  Backend API responding"
        }
    } catch {
        Write-Error "  Backend API not responding"
    }
}

# Check services
if ($containerRunning -eq $ContainerName) {
    Write-Host ""
    Write-Info "Services:"
    try {
        $services = docker exec $ContainerName supervisorctl status 2>$null
        $runningCount = ($services | Select-String "RUNNING").Count
        $totalCount = ($services | Measure-Object).Count
        
        if ($runningCount -eq $totalCount) {
            Write-Success "  All $runningCount services running"
        } else {
            Write-Warning "  $runningCount/$totalCount services running"
        }
    } catch {
        Write-Warning "  Could not check services"
    }
}

# Check disk space
Write-Host ""
Write-Info "System Resources:"
$volumes = docker system df -v --format "table {{.Name}}\t{{.Size}}" 2>$null | Select-String "neuroinsight"
if ($volumes) {
    Write-Host "  Volume: $volumes" -ForegroundColor Cyan
}

# Overall assessment
Write-Host ""
Write-Info "Overall Status:"
if ($containerRunning -eq $ContainerName) {
    try {
        $portMapping = docker port $ContainerName 8000 2>$null
        $port = $portMapping -replace '.*:', ''
        $response = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Success "  SYSTEM HEALTHY - All services operational"
    } catch {
        Write-Warning "  ISSUES DETECTED - Some services may be down"
        Write-Host "  Run: .\scripts\logs.ps1" -ForegroundColor Yellow
    }
} else {
    Write-Error "  SYSTEM NOT RUNNING"
    Write-Host "  Run: .\scripts\start.ps1" -ForegroundColor Yellow
}

Write-Host ""
