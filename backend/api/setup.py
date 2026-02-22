"""
Setup API Router for NeuroInsight.

Provides endpoints for the web-based first-time setup wizard.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/setup", tags=["setup"])


class SystemCheckResponse(BaseModel):
    """Response model for system compatibility checks."""
    compatible: bool
    ram_gb: int
    disk_gb: int
    has_avx: bool
    network_ok: bool
    python_version: str
    container_engine: Optional[str]
    recommendations: Dict[str, str]


class LicenseValidationResponse(BaseModel):
    """Response model for license validation."""
    valid: bool
    message: str
    license_path: Optional[str]


class SetupStatusResponse(BaseModel):
    """Response model for setup status."""
    completed: bool
    current_step: int
    total_steps: int
    step_name: str
    can_proceed: bool


@router.get("/status", response_model=SetupStatusResponse)
async def get_setup_status():
    """
    Get the current setup status and progress.

    Returns information about whether setup is complete and current progress.
    """
    try:
        # Check if setup is already completed
        settings_file = Path(".env")
        if settings_file.exists():
            # Check for key indicators that setup is complete
            with open(settings_file, 'r') as f:
                content = f.read()
                if "FREESURFER_LICENSE_PATH" in content:
                    return SetupStatusResponse(
                        completed=True,
                        current_step=5,
                        total_steps=5,
                        step_name="Setup Complete",
                        can_proceed=False
                    )

        # Determine current step based on what's been done
        current_step = 1
        step_name = "Welcome"

        # Check for FreeSurfer license
        license_paths = [
            Path("./license.txt"),
            Path("./resources/licenses/freesurfer_license.txt")
        ]

        for path in license_paths:
            if path.exists():
                current_step = 4
                step_name = "License Configured"
                break

        return SetupStatusResponse(
            completed=False,
            current_step=current_step,
            total_steps=5,
            step_name=step_name,
            can_proceed=True
        )

    except Exception as e:
        logger.error("setup_status_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to check setup status")


@router.get("/system-check", response_model=SystemCheckResponse)
async def check_system_compatibility():
    """
    Perform comprehensive system compatibility checks.

    Returns detailed information about system compatibility for NeuroInsight.
    """
    try:
        # RAM check
        ram_gb = 0
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    total_kb = int(line.split()[1])
                    ram_gb = total_kb // (1024 * 1024)
                    break

        # Disk space check (home directory)
        home_dir = Path.home()
        stat = os.statvfs(str(home_dir))
        available_kb = stat.f_bavail * stat.f_frsize
        disk_gb = available_kb // (1024 * 1024 * 1024)

        # CPU AVX check
        has_avx = False
        try:
            with open('/proc/cpuinfo', 'r') as f:
                has_avx = 'avx' in f.read()
        except:
            pass

        # Network check
        network_ok = False
        try:
            import subprocess
            result = subprocess.run(
                ["curl", "-s", "--connect-timeout", "5", "https://github.com"],
                capture_output=True, timeout=10
            )
            network_ok = result.returncode == 0
        except:
            pass

        # Python version
        import sys
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        # Container engine detection
        container_engine = None
        for engine in ["docker", "apptainer", "singularity"]:
            try:
                result = subprocess.run(
                    [engine, "--version"],
                    capture_output=True, timeout=5
                )
                if result.returncode == 0:
                    container_engine = engine
                    break
            except:
                continue

        # Generate recommendations
        recommendations = {}
        if ram_gb < 16:
            recommendations["ram"] = f"Consider upgrading to 16GB+ RAM (currently {ram_gb}GB)"
        if disk_gb < 50:
            recommendations["disk"] = f"Need 50GB+ free space (currently {disk_gb}GB available)"

        compatible = ram_gb >= 16 and disk_gb >= 50 and network_ok

        return SystemCheckResponse(
            compatible=compatible,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            has_avx=has_avx,
            network_ok=network_ok,
            python_version=python_version,
            container_engine=container_engine,
            recommendations=recommendations
        )

    except Exception as e:
        logger.error("system_check_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to perform system check")


@router.post("/license/upload")
async def upload_license_file(file: UploadFile = File(...)):
    """
    Upload and validate a FreeSurfer license file.

    Accepts a license.txt file upload and validates its basic structure.
    """
    try:
        # Validate file type
        if not file.filename.endswith('.txt'):
            raise HTTPException(status_code=400, detail="License file must be a .txt file")

        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')

        # Basic validation - FreeSurfer licenses typically have multiple lines
        lines = content_str.strip().split('\n')
        if len(lines) < 3:
            raise HTTPException(status_code=400, detail="License file appears to be invalid (too few lines)")

        # Create licenses directory if it doesn't exist
        license_dir = Path("./resources/licenses")
        license_dir.mkdir(parents=True, exist_ok=True)

        # Save the license file
        license_path = license_dir / "freesurfer_license.txt"
        with open(license_path, 'wb') as f:
            f.write(content)

        logger.info("license_uploaded", path=str(license_path))

        return LicenseValidationResponse(
            valid=True,
            message="License file uploaded and validated successfully",
            license_path=str(license_path)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("license_upload_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload license file")


@router.get("/license/validate")
async def validate_existing_license():
    """
    Check if a valid FreeSurfer license already exists.

    Looks for license files in standard locations and validates them.
    """
    try:
        # Match the MRI processor license search paths
        license_paths = [
            Path("./license.txt"),  # Primary location for users
            Path("./freesurfer_license.txt"),  # Legacy support
            Path("./resources/licenses/license.txt"),
            Path("./resources/licenses/freesurfer_license.txt"),
            Path.home() / "neuroinsight" / "license.txt",
            Path("/usr/local/freesurfer/license.txt"),
        ]

        for license_path in license_paths:
            if license_path.exists():
                try:
                    with open(license_path, 'r') as f:
                        content = f.read().strip()
                        lines = content.split('\n')

                    if len(lines) >= 3:
                        return LicenseValidationResponse(
                            valid=True,
                            message=f"Valid license found at {license_path}",
                            license_path=str(license_path)
                        )
                except Exception as e:
                    logger.warning("license_validation_error", path=str(license_path), error=str(e))
                    continue

        return LicenseValidationResponse(
            valid=False,
            message="No valid FreeSurfer license found",
            license_path=None
        )

    except Exception as e:
        logger.error("license_validation_check_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to validate license")


@router.post("/complete")
async def complete_setup():
    """
    Mark the setup as complete and update configuration.

    Creates or updates the .env file with final configuration.
    """
    try:
        # Check that we have the minimum required setup
        license_check = await validate_existing_license()
        if not license_check.valid:
            raise HTTPException(status_code=400, detail="FreeSurfer license is required to complete setup")

        system_check = await check_system_compatibility()
        if not system_check.compatible:
            raise HTTPException(status_code=400, detail="System requirements not met")

        # Update .env file with setup completion markers
        env_path = Path(".env")
        env_content = ""

        if env_path.exists():
            with open(env_path, 'r') as f:
                env_content = f.read()

        # Add setup completion marker if not present
        if "SETUP_COMPLETED=true" not in env_content:
            env_content += "\n# Setup Configuration\nSETUP_COMPLETED=true\n"

        with open(env_path, 'w') as f:
            f.write(env_content)

        logger.info("setup_completed_successfully")

        return {
            "status": "success",
            "message": "Setup completed successfully! NeuroInsight is now ready to use.",
            "next_steps": [
                "Open http://localhost:8001 to access the application",
                "Upload MRI scans for processing",
                "View results and generate reports"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("setup_completion_error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to complete setup")


@router.get("/freesurfer-license-url")
async def get_freesurfer_license_url():
    """
    Get the URL for FreeSurfer license registration.

    Returns the official FreeSurfer license registration page URL.
    """
    return {
        "url": "https://surfer.nmr.mgh.harvard.edu/registration.html",
        "instructions": [
            "Visit the URL above",
            "Fill out the registration form",
            "Download the license.txt file",
            "Return here and upload the license file"
        ]
    }
