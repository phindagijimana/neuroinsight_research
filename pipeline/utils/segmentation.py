"""
Segmentation utility functions.

Handles parsing of FastSurfer/FreeSurfer statistics files.
"""

from pathlib import Path
from typing import Dict

from backend.core.logging import get_logger

logger = get_logger(__name__)


def parse_hippo_stats(stats_file: Path) -> Dict[str, float]:
    """
    Parse hippocampal subfield statistics file.
    
    Extracts volume measurements from FastSurfer/FreeSurfer
    hippocampal segmentation output.
    
    Args:
        stats_file: Path to stats file (e.g., lh.hippoSfVolumes-T1.v21.txt)
    
    Returns:
        Dictionary mapping region names to volumes (mm³)
    """
    volumes = {}
    
    if not stats_file.exists():
        logger.error("stats_file_not_found", file=str(stats_file))
        return volumes
    
    try:
        with open(stats_file, "r") as f:
            for line in f:
                # Skip comments and empty lines
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # Parse region and volume
                parts = line.split()
                if len(parts) >= 2:
                    region = parts[0]
                    try:
                        volume = float(parts[1])
                        volumes[region] = volume
                    except ValueError:
                        logger.warning(
                            "invalid_volume_value",
                            region=region,
                            value=parts[1],
                        )
        
        logger.info(
            "stats_parsed",
            file=str(stats_file),
            regions=len(volumes),
        )
    
    except Exception as e:
        logger.error("stats_parsing_failed", file=str(stats_file), error=str(e))
    
    return volumes


def extract_total_hippocampal_volume(volumes: Dict[str, float]) -> float:
    """
    Calculate total hippocampal volume from subfield volumes.
    
    Args:
        volumes: Dictionary of subfield volumes
    
    Returns:
        Total hippocampal volume (mm³)
    """
    total = sum(volumes.values())
    return round(total, 2)


def parse_aseg_stats(stats_file: Path) -> Dict[str, float]:
    """
    Parse FastSurfer aseg+DKT statistics file for hippocampal volumes.
    
    This is used as a fallback when SegmentHA (subfield segmentation) is not available.
    Extracts total hippocampus volume for each hemisphere from FastSurfer's output.
    
    Args:
        stats_file: Path to aseg+DKT.stats file
    
    Returns:
        Dictionary with 'left' and 'right' hippocampal volumes (mm³)
    """
    volumes = {}
    
    if not stats_file.exists():
        logger.error("aseg_stats_file_not_found", file=str(stats_file))
        return volumes
    
    try:
        with open(stats_file, "r") as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                
                # Look for hippocampus entries
                # Format: Index SegId NVoxels Volume_mm3 StructName ...
                if "Left-Hippocampus" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            # Column index 3 is the volume in mm³
                            volumes["left"] = float(parts[3])
                            logger.info("left_hippocampus_found", volume=volumes["left"])
                        except (ValueError, IndexError) as e:
                            logger.warning("failed_to_parse_left_hippocampus", error=str(e))
                
                elif "Right-Hippocampus" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            volumes["right"] = float(parts[3])
                            logger.info("right_hippocampus_found", volume=volumes["right"])
                        except (ValueError, IndexError) as e:
                            logger.warning("failed_to_parse_right_hippocampus", error=str(e))
        
        logger.info(
            "aseg_hippocampal_volumes_extracted",
            left=volumes.get("left"),
            right=volumes.get("right"),
        )
    
    except Exception as e:
        logger.error("aseg_stats_parsing_failed", file=str(stats_file), error=str(e))
    
    return volumes

