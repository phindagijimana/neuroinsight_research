# Restart NeuroInsight container

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }

Write-Info "Restarting NeuroInsight..."

# Stop
& "$PSScriptRoot\stop.ps1"

Start-Sleep -Seconds 2

# Start
& "$PSScriptRoot\start.ps1"
