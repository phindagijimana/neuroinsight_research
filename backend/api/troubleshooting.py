"""
Troubleshooting API Router for NeuroInsight.

Provides intelligent error detection and auto-fix capabilities.
"""

import os
import re
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/troubleshooting", tags=["troubleshooting"])


class ErrorDiagnosis(BaseModel):
    """Response model for error diagnosis."""
    error_type: str
    severity: str  # "critical", "warning", "info"
    description: str
    root_cause: str
    suggested_fixes: List[Dict[str, Any]]
    can_auto_fix: bool
    confidence: float  # 0.0 to 1.0


class AutoFixResponse(BaseModel):
    """Response model for auto-fix operations."""
    success: bool
    message: str
    actions_taken: List[str]
    requires_restart: bool
    follow_up_steps: List[str]


class SystemHealthResponse(BaseModel):
    """Response model for system health checks."""
    overall_health: str  # "healthy", "warning", "critical"
    issues: List[Dict[str, Any]]
    recommendations: List[str]
    last_checked: str


# Common error patterns and their fixes
ERROR_PATTERNS = {
    # FreeSurfer license errors
    "freesurfer_license_not_found": {
        "pattern": r"FreeSurfer license not found",
        "error_type": "license_missing",
        "severity": "critical",
        "description": "FreeSurfer license file is missing or invalid",
        "fixes": [
            {
                "type": "upload_license",
                "description": "Upload a valid FreeSurfer license.txt file",
                "auto_fix": False
            },
            {
                "type": "check_paths",
                "description": "Ensure license is in the correct location",
                "auto_fix": True
            }
        ]
    },

    # Docker/Podman errors
    "docker_daemon_not_running": {
        "pattern": r"docker.*daemon.*not.*running",
        "error_type": "docker_daemon",
        "severity": "warning",
        "description": "Docker daemon is not running",
        "fixes": [
            {
                "type": "start_service",
                "description": "Start Docker daemon service",
                "auto_fix": True,
                "command": "sudo systemctl start docker"
            }
        ]
    },

    # Port conflicts
    "port_already_in_use": {
        "pattern": r"port.*already.*in.*use|address.*already.*in.*use",
        "error_type": "port_conflict",
        "severity": "warning",
        "description": "The requested port is already in use",
        "fixes": [
            {
                "type": "find_free_port",
                "description": "Automatically find an available port",
                "auto_fix": True
            },
            {
                "type": "kill_process",
                "description": "Stop the process using the port",
                "auto_fix": False
            }
        ]
    },

    # Permission errors
    "permission_denied": {
        "pattern": r"permission.*denied|access.*denied",
        "error_type": "permissions",
        "severity": "warning",
        "description": "Insufficient permissions to access required resources",
        "fixes": [
            {
                "type": "fix_permissions",
                "description": "Fix file/directory permissions",
                "auto_fix": True
            },
            {
                "type": "run_as_sudo",
                "description": "Run command with elevated privileges",
                "auto_fix": False
            }
        ]
    },

    # Memory errors
    "out_of_memory": {
        "pattern": r"out.*of.*memory|cannot.*allocate.*memory",
        "error_type": "memory",
        "severity": "critical",
        "description": "System ran out of available RAM",
        "fixes": [
            {
                "type": "reduce_load",
                "description": "Reduce processing load or free up memory",
                "auto_fix": False
            },
            {
                "type": "increase_swap",
                "description": "Increase system swap space",
                "auto_fix": True
            }
        ]
    },

    # Disk space errors
    "no_space_left": {
        "pattern": r"no.*space.*left|disk.*full",
        "error_type": "disk_space",
        "severity": "critical",
        "description": "Insufficient disk space for processing",
        "fixes": [
            {
                "type": "cleanup_files",
                "description": "Clean up temporary and cache files",
                "auto_fix": True
            },
            {
                "type": "free_space",
                "description": "Free up disk space manually",
                "auto_fix": False
            }
        ]
    },

    # Network errors
    "network_unreachable": {
        "pattern": r"network.*unreachable|connection.*refused|timeout",
        "error_type": "network",
        "severity": "warning",
        "description": "Network connectivity issues",
        "fixes": [
            {
                "type": "check_connectivity",
                "description": "Verify internet connection and DNS resolution",
                "auto_fix": True
            }
        ]
    }
}


@router.post("/diagnose", response_model=ErrorDiagnosis)
async def diagnose_error(error_message: str, error_context: Optional[Dict[str, Any]] = None):
    """
    Diagnose an error message and provide intelligent fixes.

    Analyzes error messages using pattern matching and context to provide
    targeted solutions and auto-fix capabilities.
    """
    try:
        error_message = error_message.lower()

        # Try to match error patterns
        for pattern_key, pattern_info in ERROR_PATTERNS.items():
            if re.search(pattern_info["pattern"], error_message, re.IGNORECASE):
                diagnosis = ErrorDiagnosis(
                    error_type=pattern_info["error_type"],
                    severity=pattern_info["severity"],
                    description=pattern_info["description"],
                    root_cause=pattern_info["description"],
                    suggested_fixes=pattern_info["fixes"],
                    can_auto_fix=any(fix.get("auto_fix", False) for fix in pattern_info["fixes"]),
                    confidence=0.8  # High confidence for pattern matches
                )
                return diagnosis

        # Generic error diagnosis
        return ErrorDiagnosis(
            error_type="unknown_error",
            severity="warning",
            description="Unrecognized error occurred",
            root_cause="Error doesn't match known patterns",
            suggested_fixes=[
                {
                    "type": "check_logs",
                    "description": "Check application logs for more details",
                    "auto_fix": False
                },
                {
                    "type": "restart_service",
                    "description": "Restart the NeuroInsight service",
                    "auto_fix": True
                }
            ],
            can_auto_fix=True,
            confidence=0.3
        )

    except Exception as e:
        logger.error("error_diagnosis_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to diagnose error")


@router.post("/auto-fix", response_model=AutoFixResponse)
async def apply_auto_fix(error_type: str, fix_type: str):
    """
    Apply an automatic fix for a diagnosed error.

    Attempts to automatically resolve common issues without user intervention.
    """
    try:
        actions_taken = []
        requires_restart = False
        follow_up_steps = []

        if error_type == "docker_daemon" and fix_type == "start_service":
            # Start Docker daemon
            system = platform.system().lower()
            if system == "linux":
                try:
                    result = subprocess.run(
                        ["sudo", "systemctl", "start", "docker"],
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        actions_taken.append("Started Docker daemon service")
                        requires_restart = True
                    else:
                        raise Exception(f"Failed to start Docker: {result.stderr}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to start Docker: {str(e)}")

        elif error_type == "port_conflict" and fix_type == "find_free_port":
            # Find an available port
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('', 0))
            available_port = sock.getsockname()[1]
            sock.close()

            actions_taken.append(f"Found available port: {available_port}")
            follow_up_steps.append(f"Update configuration to use port {available_port}")

        elif error_type == "permissions" and fix_type == "fix_permissions":
            # Fix common permission issues
            install_dir = Path.home() / "neuroinsight"

            # Fix permissions on install directory
            if install_dir.exists():
                try:
                    # Make directories readable/executable
                    for dir_path in [install_dir, install_dir / "resources"]:
                        if dir_path.exists():
                            os.chmod(str(dir_path), 0o755)

                    # Make license files readable
                    license_file = install_dir / "resources" / "licenses" / "freesurfer_license.txt"
                    if license_file.exists():
                        os.chmod(str(license_file), 0o644)

                    actions_taken.append("Fixed permissions on NeuroInsight directories and files")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to fix permissions: {str(e)}")

        elif error_type == "disk_space" and fix_type == "cleanup_files":
            # Clean up temporary files
            import shutil

            # Clean up Python cache
            cache_dirs = [
                Path.home() / ".cache" / "pip",
                Path.cwd() / "__pycache__",
                Path.cwd() / ".pytest_cache"
            ]

            cleaned_size = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    try:
                        size_before = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
                        shutil.rmtree(cache_dir)
                        cleaned_size += size_before
                        actions_taken.append(f"Cleaned {cache_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to clean {cache_dir}: {e}")

            if cleaned_size > 0:
                size_mb = cleaned_size // (1024 * 1024)
                actions_taken.append(f"Freed approximately {size_mb} MB of disk space")

        elif error_type == "unknown_error" and fix_type == "restart_service":
            # Generic restart suggestion
            actions_taken.append("Recommended service restart")
            follow_up_steps.append("Restart NeuroInsight application")
            requires_restart = True

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported auto-fix: {error_type} -> {fix_type}")

        return AutoFixResponse(
            success=True,
            message="Auto-fix applied successfully",
            actions_taken=actions_taken,
            requires_restart=requires_restart,
            follow_up_steps=follow_up_steps
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("auto_fix_failed", error=str(e), error_type=error_type, fix_type=fix_type)
        raise HTTPException(status_code=500, detail=f"Auto-fix failed: {str(e)}")


@router.get("/health", response_model=SystemHealthResponse)
async def check_system_health():
    """
    Perform comprehensive system health checks.

    Returns overall system health status and specific issues that need attention.
    """
    try:
        issues = []
        recommendations = []

        # Check disk space
        try:
            stat = os.statvfs(str(Path.home()))
            available_gb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024 * 1024)
            if available_gb < 10:
                issues.append({
                    "type": "disk_space",
                    "severity": "critical",
                    "description": f"Only {available_gb:.1f}GB disk space available",
                    "recommendation": "Free up disk space or move to a larger drive"
                })
            elif available_gb < 50:
                issues.append({
                    "type": "disk_space",
                    "severity": "warning",
                    "description": f"Low disk space: {available_gb:.1f}GB available",
                    "recommendation": "Consider freeing up disk space for better performance"
                })
        except Exception as e:
            logger.warning(f"Failed to check disk space: {e}")

        # Check memory
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        total_kb = int(line.split()[1])
                        total_gb = total_kb / (1024 * 1024)
                        if total_gb < 8:
                            issues.append({
                                "type": "memory",
                                "severity": "critical",
                                "description": f"Only {total_gb:.1f}GB RAM available",
                                "recommendation": "Upgrade to at least 16GB RAM for FreeSurfer processing"
                            })
                        break
        except Exception as e:
            logger.warning(f"Failed to check memory: {e}")

        # Check Docker/Podman status
        container_engines = ["docker", "podman", "apptainer", "singularity"]
        container_found = False

        for engine in container_engines:
            try:
                result = subprocess.run(
                    [engine, "--version"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    container_found = True

                    # Additional check for Docker daemon
                    if engine == "docker":
                        try:
                            result = subprocess.run(
                                ["docker", "info"],
                                capture_output=True, timeout=10
                            )
                            if result.returncode != 0:
                                issues.append({
                                    "type": "docker_daemon",
                                    "severity": "warning",
                                    "description": "Docker installed but daemon not running",
                                    "recommendation": "Start Docker daemon: sudo systemctl start docker"
                                })
                        except:
                            pass
                    break
            except:
                continue

        if not container_found:
            issues.append({
                "type": "no_container",
                "severity": "warning",
                "description": "No container engine found (Docker/Podman/Apptainer)",
                "recommendation": "Install Docker for best FreeSurfer performance"
            })
            recommendations.append("Install Docker: curl -fsSL https://get.docker.com | sh")

        # Determine overall health
        if any(issue["severity"] == "critical" for issue in issues):
            overall_health = "critical"
        elif issues:
            overall_health = "warning"
        else:
            overall_health = "healthy"

        # Generate general recommendations
        if overall_health == "healthy":
            recommendations.append("System is healthy and ready for NeuroInsight processing")
        else:
            recommendations.append("Address the issues above for optimal NeuroInsight performance")

        import datetime
        return SystemHealthResponse(
            overall_health=overall_health,
            issues=issues,
            recommendations=recommendations,
            last_checked=datetime.datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error("system_health_check_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check system health")


@router.get("/logs/recent")
async def get_recent_logs(lines: int = 50):
    """
    Get recent application logs for troubleshooting.

    Returns the last N lines of application logs to help with debugging.
    """
    try:
        # Try to find log files
        possible_log_paths = [
            Path.cwd() / "logs" / "neuroinsight.log",
            Path.home() / ".neuroinsight" / "logs" / "neuroinsight.log",
            Path("/var/log/neuroinsight.log")
        ]

        for log_path in possible_log_paths:
            if log_path.exists():
                try:
                    with open(log_path, 'r') as f:
                        lines_content = f.readlines()[-lines:]
                        return {
                            "log_file": str(log_path),
                            "lines": lines_content,
                            "total_lines_returned": len(lines_content)
                        }
                except Exception as e:
                    logger.warning(f"Failed to read log file {log_path}: {e}")
                    continue

        return {
            "log_file": None,
            "lines": ["No log files found. Logs may be written to stdout/stderr."],
            "total_lines_returned": 1
        }

    except Exception as e:
        logger.error("failed_to_get_logs", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve logs")













