# Backup NeuroInsight data

param(
    [string]$OutputPath = "neuroinsight-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz"
)

$ContainerName = "neuroinsight"
$VolumeName = "neuroinsight-data"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NeuroInsight Data Backup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

Write-Info "Creating backup..."
Write-Info "Output: $OutputPath"
Write-Host ""

try {
    # Create backup using alpine container
    docker run --rm `
        -v "${VolumeName}:/data" `
        -v "$(Get-Location):/backup" `
        alpine tar czf "/backup/$OutputPath" /data
    
    $backupSize = (Get-Item $OutputPath).Length / 1MB
    Write-Success "Backup created successfully"
    Write-Host "File: $OutputPath" -ForegroundColor Cyan
    Write-Host "Size: $([math]::Round($backupSize, 2)) MB" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Error "Backup failed: $_"
    exit 1
}
