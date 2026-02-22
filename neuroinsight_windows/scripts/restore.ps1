# Restore NeuroInsight data from backup

param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

$ContainerName = "neuroinsight"
$VolumeName = "neuroinsight-data"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NeuroInsight Data Restore" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if backup file exists
if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 1
}

$fullPath = (Resolve-Path $BackupFile).Path
Write-Warning "This will overwrite all existing data in the volume"
$response = Read-Host "Continue? (yes/no)"
if ($response -ne "yes") {
    Write-Info "Restore cancelled"
    exit 0
}

Write-Info "Restoring from backup..."
Write-Info "File: $fullPath"
Write-Host ""

# Stop container if running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -eq $ContainerName) {
    Write-Info "Stopping container..."
    docker stop $ContainerName | Out-Null
    $wasRunning = $true
} else {
    $wasRunning = $false
}

try {
    # Restore using alpine container
    docker run --rm `
        -v "${VolumeName}:/data" `
        -v "$(Split-Path $fullPath):/backup" `
        alpine sh -c "cd / && tar xzf /backup/$(Split-Path $fullPath -Leaf)"
    
    Write-Success "Restore completed successfully"
    Write-Host ""
    
    # Restart container if it was running
    if ($wasRunning) {
        Write-Info "Restarting container..."
        docker start $ContainerName | Out-Null
        Start-Sleep -Seconds 5
        Write-Success "Container restarted"
    }
} catch {
    Write-Error "Restore failed: $_"
    if ($wasRunning) {
        Write-Info "Attempting to restart container..."
        docker start $ContainerName | Out-Null
    }
    exit 1
}
