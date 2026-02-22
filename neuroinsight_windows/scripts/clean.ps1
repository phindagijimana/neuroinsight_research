# Clean old NeuroInsight jobs

param(
    [int]$Days = 30,
    [switch]$DryRun
)

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  NeuroInsight Data Cleanup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if container is running
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -ne $ContainerName) {
    Write-Error "Container is not running"
    exit 1
}

Write-Info "Cleaning jobs older than $Days days..."
if ($DryRun) {
    Write-Warning "DRY RUN MODE - No data will be deleted"
}
Write-Host ""

# Build clean command
$cleanCmd = "python -c `"import sys; sys.path.insert(0, '/app'); from scripts.clean import main; main(days=$Days"
if ($DryRun) {
    $cleanCmd += ", dry_run=True"
}
$cleanCmd += ")`""

try {
    docker exec -it $ContainerName bash -c $cleanCmd
    Write-Host ""
    Write-Success "Cleanup completed"
} catch {
    Write-Error "Cleanup failed: $_"
    exit 1
}
