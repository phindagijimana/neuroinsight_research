# Update NeuroInsight to latest version

param(
    [switch]$Check
)

$ContainerName = "neuroinsight"
$ImageName = "phindagijimana321/neuroinsight:latest"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }

if ($Check) {
    Write-Info "Checking for updates..."
    docker pull $ImageName
    Write-Host ""
    Write-Info "To update, run: .\scripts\update.ps1"
    exit 0
}

Write-Warning "Backup recommended before updating!"
$response = Read-Host "Continue with update? (y/N)"
if ($response -ne "y" -and $response -ne "Y") {
    Write-Info "Update cancelled"
    exit 0
}

# Pull latest image
Write-Info "Pulling latest image..."
docker pull $ImageName

# Stop and remove old container
Write-Info "Stopping container..."
docker stop $ContainerName 2>$null | Out-Null
docker rm $ContainerName 2>$null | Out-Null

Write-Success "Update complete. Run install.ps1 to create new container"
