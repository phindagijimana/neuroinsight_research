# NeuroInsight Docker Management CLI for Windows
# PowerShell equivalent of Linux neuroinsight-docker script

param(
    [Parameter(Position=0)]
    [string]$Command = "help",
    
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments
)

$ContainerName = "neuroinsight"
$ImageName = "phindagijimana321/neuroinsight:latest"
$VolumeName = "neuroinsight-data"

# Colors
function Write-Info { param([string]$Message); Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Success { param([string]$Message); Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message); Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message); Write-Host "[ERROR] $Message" -ForegroundColor Red }

# Helper functions
function Test-Docker {
    try {
        docker ps | Out-Null
        return $true
    } catch {
        Write-Error "Docker is not running"
        Write-Host "Please start Docker Desktop and try again"
        return $false
    }
}

function Test-ContainerExists {
    $exists = docker ps -a --filter "name=^${ContainerName}$" --format "{{.Names}}"
    return ($exists -eq $ContainerName)
}

function Test-ContainerRunning {
    $running = docker ps --filter "name=^${ContainerName}$" --format "{{.Names}}"
    return ($running -eq $ContainerName)
}

function Get-ContainerPort {
    $portMapping = docker port $ContainerName 8000 2>$null
    if ($portMapping) {
        return ($portMapping -replace '.*:', '')
    }
    return $null
}

# Command: install
function Invoke-Install {
    param([int]$Port = 8000)
    
    if (-not (Test-Docker)) { exit 1 }
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  NeuroInsight Docker Installation" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Check existing
    if (Test-ContainerExists) {
        Write-Warning "NeuroInsight container already exists"
        $response = Read-Host "Remove and reinstall? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            Write-Info "Installation cancelled"
            exit 0
        }
        Invoke-Remove
    }
    
    # Find available port
    Write-Info "Finding available port (range: 8000-8050)..."
    $selectedPort = $Port
    $portFound = $false
    
    for ($testPort = $selectedPort; $testPort -le 8050; $testPort++) {
        $connection = Test-NetConnection -ComputerName localhost -Port $testPort -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $connection) {
            $selectedPort = $testPort
            $portFound = $true
            break
        }
    }
    
    if (-not $portFound) {
        Write-Error "No available ports found in range 8000-8050"
        exit 1
    }
    
    Write-Success "Selected port: $selectedPort"
    
    # Calculate additional ports
    $minioApiPort = $selectedPort + 1000
    $minioConsolePort = $selectedPort + 1001
    
    # Search for license
    Write-Info "Searching for FreeSurfer license..."
    $licenseMount = @()
    
    $licensePaths = @(
        ".\license.txt",
        "..\license.txt",
        "$env:USERPROFILE\license.txt",
        "$env:USERPROFILE\Desktop\license.txt",
        "$env:USERPROFILE\Documents\license.txt"
    )
    
    $licenseFound = $false
    foreach ($path in $licensePaths) {
        if (Test-Path $path) {
            $content = Get-Content $path -Raw
            if ($content -notmatch "REPLACE THIS EXAMPLE" -and $content -notmatch "EXAMPLE") {
                $licenseFound = $true
                $fullPath = (Resolve-Path $path).Path
                $licenseMount = @("-v", "${fullPath}:/app/license.txt:ro")
                Write-Success "Found license: $fullPath"
                break
            }
        }
    }
    
    if (-not $licenseFound) {
        Write-Warning "FreeSurfer license not found (will run in demo mode)"
        Write-Host "Get license: https://surfer.nmr.mgh.harvard.edu/registration.html" -ForegroundColor Yellow
    }
    
    # Pull image
    Write-Info "Pulling NeuroInsight Docker image..."
    try {
        docker pull $ImageName
        Write-Success "Image pulled"
    } catch {
        Write-Error "Failed to pull image"
        exit 1
    }
    
    # Create volume
    Write-Info "Creating data volume..."
    $existingVolume = docker volume ls --filter "name=^${VolumeName}$" --format "{{.Name}}"
    if ($existingVolume -ne $VolumeName) {
        docker volume create $VolumeName | Out-Null
        Write-Success "Volume created"
    } else {
        Write-Success "Volume exists (preserving data)"
    }
    
    # Get volume path
    $volumePath = "/var/lib/docker/volumes/${VolumeName}/_data"
    
    # Create container
    Write-Info "Creating container..."
    Write-Info "  Web Interface: http://localhost:${selectedPort}"
    Write-Info "  MinIO Console: http://localhost:${minioConsolePort}"
    
    $dockerArgs = @(
        "run", "-d",
        "--name", $ContainerName,
        "-p", "${selectedPort}:8000",
        "-p", "${minioApiPort}:9000",
        "-p", "${minioConsolePort}:9001",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", "${VolumeName}:/data",
        "-e", "HOST_UPLOAD_DIR=${volumePath}/uploads",
        "-e", "HOST_OUTPUT_DIR=${volumePath}/outputs",
        "--restart", "unless-stopped"
    )
    
    if ($licenseMount.Count -gt 0) {
        $dockerArgs += $licenseMount
    }
    
    $dockerArgs += $ImageName
    
    try {
        docker @dockerArgs | Out-Null
        Write-Success "Container created"
    } catch {
        Write-Error "Failed to create container"
        exit 1
    }
    
    # Wait for startup
    Write-Info "Waiting for services to start (30 seconds)..."
    Start-Sleep -Seconds 30
    
    # Show status
    Invoke-Status
    
    Write-Host ""
    Write-Success "NeuroInsight is ready!"
    Write-Host "Web Interface: http://localhost:${selectedPort}" -ForegroundColor Cyan
    Write-Host ""
}

# Command: start
function Invoke-Start {
    if (-not (Test-Docker)) { exit 1 }
    
    if (-not (Test-ContainerExists)) {
        Write-Error "Container does not exist. Run: .\neuroinsight-docker.ps1 install"
        exit 1
    }
    
    if (Test-ContainerRunning) {
        Write-Warning "Container is already running"
        $port = Get-ContainerPort
        if ($port) {
            Write-Host "Web Interface: http://localhost:$port" -ForegroundColor Cyan
        }
        exit 0
    }
    
    Write-Info "Starting NeuroInsight..."
    docker start $ContainerName | Out-Null
    Start-Sleep -Seconds 5
    
    Write-Success "Container started"
    $port = Get-ContainerPort
    if ($port) {
        Write-Host "Web Interface: http://localhost:$port" -ForegroundColor Cyan
    }
}

# Command: stop
function Invoke-Stop {
    if (-not (Test-Docker)) { exit 1 }
    
    if (-not (Test-ContainerRunning)) {
        Write-Warning "Container is not running"
        exit 0
    }
    
    Write-Info "Stopping NeuroInsight..."
    docker stop $ContainerName | Out-Null
    Write-Success "Container stopped"
}

# Command: restart
function Invoke-Restart {
    Invoke-Stop
    Start-Sleep -Seconds 2
    Invoke-Start
}

# Command: status
function Invoke-Status {
    if (-not (Test-Docker)) { exit 1 }
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  NeuroInsight Docker Status" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    
    if (-not (Test-ContainerExists)) {
        Write-Error "Container does not exist"
        Write-Host "Run: .\neuroinsight-docker.ps1 install"
        exit 1
    }
    
    if (Test-ContainerRunning) {
        Write-Success "Container is running"
        Write-Host ""
        
        $port = Get-ContainerPort
        if ($port) {
            Write-Host "Web Interface: http://localhost:$port" -ForegroundColor Cyan
            Write-Host ""
        }
        
        # Container details
        docker ps --filter "name=^${ContainerName}$" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        Write-Host ""
        
        # Service status
        Write-Info "Services:"
        try {
            docker exec $ContainerName supervisorctl status 2>$null
        } catch {
            Write-Warning "Could not get service status"
        }
    } else {
        Write-Warning "Container exists but is not running"
        Write-Host "Run: .\neuroinsight-docker.ps1 start"
    }
    
    Write-Host ""
}

# Command: logs
function Invoke-Logs {
    param([string]$Service = "all", [switch]$Follow)
    
    if (-not (Test-ContainerRunning)) {
        Write-Error "Container is not running"
        exit 1
    }
    
    $followArg = if ($Follow) { "-f" } else { "--tail", "100" }
    
    switch ($Service) {
        "backend" {
            Write-Info "Backend logs:"
            docker exec $ContainerName tail $followArg /var/log/supervisor/backend.log
        }
        "worker" {
            Write-Info "Worker logs:"
            docker exec $ContainerName tail $followArg /var/log/supervisor/celery_worker.log
        }
        "monitor" {
            Write-Info "Job monitor logs:"
            docker exec $ContainerName tail $followArg /var/log/supervisor/job_monitor.log
        }
        default {
            Write-Info "All container logs:"
            docker logs @followArg $ContainerName
        }
    }
}

# Command: health
function Invoke-Health {
    if (-not (Test-ContainerRunning)) {
        Write-Error "Container is not running"
        exit 1
    }
    
    Write-Info "Running health check..."
    docker exec $ContainerName /app/healthcheck.sh
}

# Command: clean
function Invoke-Clean {
    param([int]$Days = 30, [switch]$DryRun)
    
    if (-not (Test-ContainerRunning)) {
        Write-Error "Container is not running"
        exit 1
    }
    
    Write-Info "Cleaning jobs older than $Days days..."
    if ($DryRun) {
        Write-Warning "DRY RUN MODE"
    }
    
    $cleanCmd = "cd /app && python -c `"from scripts.clean import main; main(days=$Days"
    if ($DryRun) { $cleanCmd += ", dry_run=True" }
    $cleanCmd += ")`""
    
    docker exec -it $ContainerName bash -c $cleanCmd
}

# Command: backup
function Invoke-Backup {
    param([string]$Output = "neuroinsight-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').tar.gz")
    
    Write-Info "Creating backup: $Output"
    docker run --rm -v "${VolumeName}:/data" -v "$(Get-Location):/backup" alpine tar czf "/backup/$Output" /data
    Write-Success "Backup created: $Output"
}

# Command: restore
function Invoke-Restore {
    param([string]$BackupFile)
    
    if (-not $BackupFile) {
        Write-Error "Please specify backup file"
        Write-Host "Usage: .\neuroinsight-docker.ps1 restore <backup-file>"
        exit 1
    }
    
    if (-not (Test-Path $BackupFile)) {
        Write-Error "Backup file not found: $BackupFile"
        exit 1
    }
    
    Write-Warning "This will overwrite all data"
    $response = Read-Host "Continue? (yes/no)"
    if ($response -ne "yes") { exit 0 }
    
    if (Test-ContainerRunning) {
        Write-Info "Stopping container..."
        docker stop $ContainerName | Out-Null
        $needRestart = $true
    } else {
        $needRestart = $false
    }
    
    $fullPath = (Resolve-Path $BackupFile).Path
    Write-Info "Restoring from: $fullPath"
    
    docker run --rm -v "${VolumeName}:/data" -v "$(Split-Path $fullPath):/backup" alpine sh -c "cd / && tar xzf /backup/$(Split-Path $fullPath -Leaf)"
    Write-Success "Restore completed"
    
    if ($needRestart) {
        docker start $ContainerName | Out-Null
        Write-Success "Container restarted"
    }
}

# Command: remove/uninstall
function Invoke-Remove {
    if (-not (Test-Docker)) { exit 1 }
    
    Write-Warning "This will remove the NeuroInsight container"
    Write-Info "Data volume will be preserved (use 'clean --all' to remove data)"
    
    if (Test-ContainerRunning) {
        Write-Info "Stopping container..."
        docker stop $ContainerName | Out-Null
    }
    
    if (Test-ContainerExists) {
        Write-Info "Removing container..."
        docker rm $ContainerName | Out-Null
        Write-Success "Container removed"
    } else {
        Write-Warning "Container does not exist"
    }
}

# Command: update
function Invoke-Update {
    if (-not (Test-Docker)) { exit 1 }
    
    Write-Info "Updating NeuroInsight to latest version..."
    Write-Host ""
    
    # Pull latest
    Write-Info "Pulling latest image..."
    docker pull $ImageName
    Write-Success "Image updated"
    
    if (-not (Test-ContainerExists)) {
        Write-Info "No container to update. Run: .\neuroinsight-docker.ps1 install"
        exit 0
    }
    
    # Recreate container
    Write-Info "Recreating container with new image..."
    $port = Get-ContainerPort
    if (-not $port) { $port = 8000 }
    
    Invoke-Remove
    Invoke-Install -Port $port
}

# Command: license
function Invoke-License {
    if (-not (Test-ContainerRunning)) {
        Write-Error "Container is not running"
        exit 1
    }
    
    Write-Host ""
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host "  FreeSurfer License" -ForegroundColor Cyan
    Write-Host "======================================" -ForegroundColor Cyan
    Write-Host ""
    
    $licenseExists = docker exec $ContainerName test -f /app/license.txt 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "License found in container"
        Write-Host ""
        docker exec $ContainerName cat /app/license.txt
        Write-Host ""
    } else {
        Write-Warning "No license in container"
        Write-Host ""
        Write-Host "To add license:" -ForegroundColor Yellow
        Write-Host "  1. Get license: https://surfer.nmr.mgh.harvard.edu/registration.html"
        Write-Host "  2. Save as 'license.txt' in this folder"
        Write-Host "  3. Run: .\neuroinsight-docker.ps1 restart"
        Write-Host ""
    }
}

# Command: help
function Show-Help {
    Write-Host @"

NeuroInsight Docker Management CLI for Windows

USAGE:
    .\neuroinsight-docker.ps1 <command> [options]

COMMANDS:
    install         Install and start NeuroInsight
    start           Start the container
    stop            Stop the container
    restart         Restart the container
    status          Show container status
    logs [service]  View logs (all, backend, worker, monitor)
    health          Run health check
    clean [days]    Clean old jobs (default: 30 days)
    backup [file]   Backup all data
    restore <file>  Restore from backup
    license         Check FreeSurfer license
    update          Update to latest version
    remove          Remove container (keeps data)
    uninstall       Same as remove
    help            Show this help

EXAMPLES:
    .\neuroinsight-docker.ps1 install
    .\neuroinsight-docker.ps1 start
    .\neuroinsight-docker.ps1 status
    .\neuroinsight-docker.ps1 logs worker
    .\neuroinsight-docker.ps1 clean -Days 7
    .\neuroinsight-docker.ps1 backup
    .\neuroinsight-docker.ps1 restore backup.tar.gz

QUICK SHORTCUTS (Batch files):
    install.bat     Install
    start.bat       Start
    stop.bat        Stop
    status.bat      Status
    logs.bat        Logs

MORE INFO:
    README.md              Complete documentation
    QUICK_REFERENCE.md     Command reference

"@
}

# Main command dispatcher
switch ($Command.ToLower()) {
    "install" {
        $portArg = if ($Arguments[0]) { [int]$Arguments[0] } else { 8000 }
        Invoke-Install -Port $portArg
    }
    "start" {
        Invoke-Start
    }
    "stop" {
        Invoke-Stop
    }
    "restart" {
        Invoke-Restart
    }
    "status" {
        Invoke-Status
    }
    "logs" {
        $service = if ($Arguments[0]) { $Arguments[0] } else { "all" }
        $follow = $Arguments -contains "-f" -or $Arguments -contains "--follow"
        Invoke-Logs -Service $service -Follow:$follow
    }
    "health" {
        Invoke-Health
    }
    "clean" {
        $days = 30
        $dryRun = $false
        foreach ($arg in $Arguments) {
            if ($arg -match '^\d+$') {
                $days = [int]$arg
            } elseif ($arg -eq "--dry-run" -or $arg -eq "-d") {
                $dryRun = $true
            }
        }
        Invoke-Clean -Days $days -DryRun:$dryRun
    }
    "backup" {
        $output = if ($Arguments[0]) { $Arguments[0] } else { "" }
        if ($output) {
            Invoke-Backup -Output $output
        } else {
            Invoke-Backup
        }
    }
    "restore" {
        if (-not $Arguments[0]) {
            Write-Error "Please specify backup file"
            exit 1
        }
        Invoke-Restore -BackupFile $Arguments[0]
    }
    "license" {
        Invoke-License
    }
    "update" {
        Invoke-Update
    }
    { $_ -in @("remove", "uninstall") } {
        Invoke-Remove
    }
    { $_ -in @("help", "--help", "-h", "?") } {
        Show-Help
    }
    default {
        Write-Error "Unknown command: $Command"
        Write-Host ""
        Show-Help
        exit 1
    }
}
