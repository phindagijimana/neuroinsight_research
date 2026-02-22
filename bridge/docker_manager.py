"""
Docker Manager for FreeSurfer API Bridge

This module handles all Docker operations for FreeSurfer containers:
- Starting FreeSurfer containers with proper volume mounts
- Monitoring container status and logs
- Managing container lifecycle (start, stop, cleanup)
- Collecting processing results

This isolates all Docker operations from the main application,
solving Docker-in-Docker complexity issues.
"""

import os
import logging
import time
from typing import Dict, Any, Optional
from pathlib import Path

import docker
from docker.errors import DockerException, APIError, ContainerError, ImageNotFound

logger = logging.getLogger(__name__)

class DockerManager:
    """
    Manages Docker operations for FreeSurfer containers

    This class provides a clean interface for:
    - Starting FreeSurfer analysis containers
    - Monitoring container execution
    - Managing container lifecycle
    - Collecting results
    """

    def __init__(self):
        """Initialize Docker client"""
        try:
            self.client = docker.from_env()
            logger.info("Docker client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise

        # FreeSurfer configuration
        self.freesurfer_image = os.getenv("FREESURFER_IMAGE", "freesurfer/freesurfer:7.4.1")
        self.freesurfer_license_path = os.getenv("FREESURFER_LICENSE", "/usr/local/freesurfer/license.txt")
        self.container_prefix = os.getenv("FREESURFER_CONTAINER_PREFIX", "freesurfer-job-")

        # Resource limits
        self.memory_limit = os.getenv("FREESURFER_MEMORY", "8g")
        self.cpu_limit = os.getenv("FREESURFER_CPUS", "2.0")

        logger.info(f"FreeSurfer image: {self.freesurfer_image}")
        logger.info(f"Memory limit: {self.memory_limit}, CPU limit: {self.cpu_limit}")

    def start_freesurfer_container(
        self,
        job_id: str,
        input_file: str,
        output_dir: str,
        subject_id: str = "subject"
    ) -> Dict[str, Any]:
        """
        Start a FreeSurfer container for MRI processing

        Args:
            job_id: Unique job identifier
            input_file: Path to input MRI file
            output_dir: Directory for output results
            subject_id: FreeSurfer subject identifier

        Returns:
            Dict containing container information
        """
        try:
            logger.info(f"Starting FreeSurfer container for job {job_id}")

            # Validate inputs
            input_path = Path(input_file)
            output_path = Path(output_dir)

            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")

            # Create output directory
            output_path.mkdir(parents=True, exist_ok=True)

            # Prepare FreeSurfer command
            freesurfer_cmd = self._build_freesurfer_command(
                input_file=str(input_path),
                output_dir=str(output_path),
                subject_id=subject_id
            )

            # Prepare volume mounts
            volumes = self._prepare_volume_mounts(input_path, output_path)

            # Container configuration
            container_config = {
                "image": self.freesurfer_image,
                "command": freesurfer_cmd,
                "volumes": volumes,
                "working_dir": "/opt/freesurfer/subjects",
                "environment": self._get_environment_variables(),
                "mem_limit": self.memory_limit,
                "cpu_quota": int(float(self.cpu_limit) * 100000),  # Docker CPU quota format
                "cpu_period": 100000,
                "detach": True,  # Run in background
                "remove": False,  # Keep container for inspection
                "name": f"{self.container_prefix}{job_id}",
                "labels": {
                    "neuroinsight.job_id": job_id,
                    "neuroinsight.type": "freesurfer-processor"
                }
            }

            logger.info(f"Container config: {container_config}")

            # Start container
            container = self.client.containers.run(**container_config)

            logger.info(f"Started FreeSurfer container {container.id} for job {job_id}")

            return {
                "container_id": container.id,
                "container_name": container.name,
                "job_id": job_id,
                "status": "running",
                "start_time": time.time(),
                "input_file": str(input_path),
                "output_dir": str(output_path)
            }

        except Exception as e:
            logger.error(f"Failed to start FreeSurfer container for job {job_id}: {e}")
            raise

    def get_container_status(self, container_id: str) -> str:
        """
        Get the status of a container

        Args:
            container_id: Docker container ID

        Returns:
            Container status string
        """
        try:
            container = self.client.containers.get(container_id)
            return container.status
        except Exception as e:
            logger.error(f"Error getting container status for {container_id}: {e}")
            return "unknown"

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get logs from a container

        Args:
            container_id: Docker container ID
            tail: Number of log lines to retrieve

        Returns:
            Container logs as string
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail).decode('utf-8')
            return logs
        except Exception as e:
            logger.error(f"Error getting logs for container {container_id}: {e}")
            return ""

    def stop_container(self, container_id: str) -> bool:
        """
        Stop a running container

        Args:
            container_id: Docker container ID

        Returns:
            True if stopped successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=30)
            logger.info(f"Stopped container {container_id}")
            return True
        except Exception as e:
            logger.error(f"Error stopping container {container_id}: {e}")
            return False

    def remove_container(self, container_id: str) -> bool:
        """
        Remove a stopped container

        Args:
            container_id: Docker container ID

        Returns:
            True if removed successfully
        """
        try:
            container = self.client.containers.get(container_id)
            container.remove()
            logger.info(f"Removed container {container_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing container {container_id}: {e}")
            return False

    def collect_results(self, job_id: str, output_dir: str) -> Dict[str, Any]:
        """
        Collect processing results from output directory

        Args:
            job_id: Job identifier
            output_dir: Directory containing FreeSurfer outputs

        Returns:
            Dict containing parsed results
        """
        try:
            output_path = Path(output_dir)
            results = {
                "job_id": job_id,
                "output_dir": str(output_path),
                "files_generated": [],
                "processing_completed": False
            }

            # Check for key FreeSurfer output files
            key_files = [
                "scripts/recon-all.log",  # Main processing log
                "surf/lh.pial",           # Left hemisphere surface
                "surf/rh.pial",           # Right hemisphere surface
                "stats/lh.aparc.stats",   # Left hemisphere stats
                "stats/rh.aparc.stats",   # Right hemisphere stats
                "stats/aseg.stats"        # Segmentation stats
            ]

            for file_path in key_files:
                full_path = output_path / file_path
                if full_path.exists():
                    results["files_generated"].append(str(full_path))

            # Check if processing completed successfully
            log_file = output_path / "scripts" / "recon-all.log"
            if log_file.exists():
                log_content = log_file.read_text()
                if "finished without error" in log_content.lower():
                    results["processing_completed"] = True

            # Extract basic metrics if available
            results["metrics"] = self._extract_basic_metrics(output_path)

            logger.info(f"Collected results for job {job_id}: {len(results['files_generated'])} files")
            return results

        except Exception as e:
            logger.error(f"Error collecting results for job {job_id}: {e}")
            return {
                "job_id": job_id,
                "error": str(e),
                "processing_completed": False
            }

    def _build_freesurfer_command(
        self,
        input_file: str,
        output_dir: str,
        subject_id: str
    ) -> str:
        """
        Build the FreeSurfer recon-all command

        Args:
            input_file: Path to input MRI file
            output_dir: Output directory path
            subject_id: FreeSurfer subject identifier

        Returns:
            Complete FreeSurfer command string
        """
        # Convert paths to container paths
        container_input = f"/data/input/{Path(input_file).name}"
        container_output = f"/data/output/{subject_id}"

        # Basic recon-all command for cortical reconstruction
        cmd = (
            f"recon-all "
            f"-subjid {subject_id} "
            f"-i {container_input} "
            f"-sd /data/output "
            f"-all "  # Run all reconstruction steps
            f"-no-isrunning "  # Don't check for running processes
            f"2>&1 | tee /data/output/{subject_id}/scripts/recon-all.log"
        )

        logger.info(f"FreeSurfer command: {cmd}")
        return cmd

    def _prepare_volume_mounts(self, input_path: Path, output_path: Path) -> Dict[str, Dict[str, str]]:
        """
        Prepare volume mounts for FreeSurfer container

        Args:
            input_path: Path to input file
            output_path: Path to output directory

        Returns:
            Docker volume mount configuration
        """
        volumes = {}

        # Mount input file directory
        input_dir = str(input_path.parent)
        volumes[input_dir] = {"bind": "/data/input", "mode": "ro"}

        # Mount output directory
        output_dir = str(output_path.parent)
        volumes[output_dir] = {"bind": "/data/output", "mode": "rw"}

        # Mount FreeSurfer license if available
        if Path(self.freesurfer_license_path).exists():
            license_dir = str(Path(self.freesurfer_license_path).parent)
            volumes[license_dir] = {"bind": "/opt/freesurfer/license", "mode": "ro"}

        logger.info(f"Volume mounts: {volumes}")
        return volumes

    def _get_environment_variables(self) -> Dict[str, str]:
        """
        Get environment variables for FreeSurfer container

        Returns:
            Dict of environment variables
        """
        env_vars = {
            "FREESURFER_HOME": "/opt/freesurfer",
            "SUBJECTS_DIR": "/opt/freesurfer/subjects",
            "PATH": "/opt/freesurfer/bin:/opt/freesurfer/fsfast/bin:/opt/freesurfer/tktools:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        }

        # Add FreeSurfer license path if available
        if Path(self.freesurfer_license_path).exists():
            env_vars["FS_LICENSE"] = "/opt/freesurfer/license/license.txt"

        return env_vars

    def _extract_basic_metrics(self, output_path: Path) -> Dict[str, Any]:
        """
        Extract basic metrics from FreeSurfer output

        Args:
            output_path: Path to FreeSurfer output directory

        Returns:
            Dict containing basic metrics
        """
        metrics = {}

        try:
            # Try to extract some basic stats from aseg.stats
            aseg_stats = output_path / "stats" / "aseg.stats"
            if aseg_stats.exists():
                content = aseg_stats.read_text()
                # This is a simplified extraction - real implementation would parse properly
                metrics["aseg_stats_available"] = True
                metrics["stats_file_size"] = aseg_stats.stat().st_size

        except Exception as e:
            logger.warning(f"Could not extract metrics: {e}")

        return metrics
