# Check FreeSurfer license status

$ContainerName = "neuroinsight"

function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  FreeSurfer License Management" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check container
$containerRunning = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
if ($containerRunning -ne $ContainerName) {
    Write-Error "Container is not running"
    Write-Host "Run: .\scripts\start.ps1" -ForegroundColor Yellow
    exit 1
}

# Check license in container
Write-Info "Checking license in container..."
try {
    $licenseExists = docker exec $ContainerName test -f /app/license.txt 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "License file found in container"
        Write-Host ""
        
        # Show license content
        Write-Info "License information:"
        docker exec $ContainerName cat /app/license.txt
        Write-Host ""
    } else {
        Write-Warning "No license file found in container"
        Write-Host ""
        Write-Host "To add FreeSurfer license:" -ForegroundColor Yellow
        Write-Host "  1. Get license: https://surfer.nmr.mgh.harvard.edu/registration.html"
        Write-Host "  2. Save as 'license.txt' in current directory"
        Write-Host "  3. Run: .\scripts\restart.ps1"
        Write-Host ""
    }
} catch {
    Write-Error "Could not check license: $_"
}

# Check local license files
Write-Host ""
Write-Info "Checking for local license files..."
$licensePaths = @(
    ".\license.txt",
    "$env:USERPROFILE\license.txt",
    "$env:USERPROFILE\Desktop\license.txt",
    "$env:USERPROFILE\Documents\license.txt"
)

$foundLocal = $false
foreach ($path in $licensePaths) {
    if (Test-Path $path) {
        $content = Get-Content $path -Raw
        if ($content -notmatch "REPLACE THIS EXAMPLE" -and $content -notmatch "FreeSurfer License File - EXAMPLE") {
            Write-Success "Found license: $path"
            $foundLocal = $true
        }
    }
}

if (-not $foundLocal) {
    Write-Warning "No local license files found"
    Write-Host ""
    Write-Host "To obtain a FreeSurfer license (free for research):"
    Write-Host "  Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
    Write-Host ""
}

Write-Host ""
