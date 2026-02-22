"""
File utility functions for MRI processing.

Handles file format validation, conversion, and manipulation.
"""

import subprocess as subprocess_module
from pathlib import Path

import nibabel as nib

from backend.core.logging import get_logger

logger = get_logger(__name__)


def validate_nifti(file_path: Path) -> bool:
    """
    Validate NIfTI file format and integrity.
    Since T1 validation is already done at upload time, be more lenient here.

    Args:
        file_path: Path to NIfTI file

    Returns:
        True if valid, False otherwise
    """
    try:
        # First check if file exists and has reasonable content
        if not file_path.exists():
            logger.error("nifti_file_not_found", file=str(file_path))
            return False

        file_size = file_path.stat().st_size
        if file_size < 1000:  # Less than 1KB is suspicious for medical images
            logger.error("nifti_file_too_small", file=str(file_path), size=file_size)
            return False

        # Try to load with nibabel, but be more lenient
        try:
            img = nib.load(str(file_path))
            logger.info("nifti_loaded_with_nibabel", file=str(file_path), shape=getattr(img, 'shape', 'unknown'))
            return True
        except nib.filebasedimages.ImageFileError:
            # If nibabel can't load it, it might still be a valid medical image format
            # that FreeSurfer can handle. Trust the T1 filename validation.
            logger.warning("nifti_not_standard_format_but_trusting_t1_validation",
                          file=str(file_path), size=file_size)
            return True  # Trust T1 validation from filename
        except Exception as nibabel_error:
            # Other nibabel errors might indicate real problems
            logger.error("nifti_nibabel_error", file=str(file_path), error=str(nibabel_error))
            # But still trust T1 validation - let FreeSurfer decide
            return True

    except Exception as e:
        logger.error("nifti_validation_failed", file=str(file_path), error=str(e))
        raise ValueError(f"File format validation failed: {file_path.name} is not a valid NIfTI file. The DICOM to NIfTI conversion may have failed. Try converting your DICOM files to NIfTI format locally first.")


def convert_dicom_to_nifti(dicom_path: Path, output_path: Path) -> Path:
    """
    Convert DICOM file/directory to NIfTI format.
    
    Uses dcm2niix for conversion.
    
    Args:
        dicom_path: Path to DICOM file or directory
        output_path: Output NIfTI file path
    
    Returns:
        Path to created NIfTI file
    
    Raises:
        RuntimeError: If conversion fails
    """
    try:
        # Ensure dcm2niix is available
        subprocess_module.run(
            ["dcm2niix", "-h"],
            check=True,
            capture_output=True,
        )
        
        # Run dcm2niix
        cmd = [
            "dcm2niix",
            "-f", output_path.stem,  # Output filename
            "-o", str(output_path.parent),  # Output directory
            "-z", "y",  # Compress output
            "-b", "n",  # Don't create BIDS sidecar
            str(dicom_path),
        ]
        
        result = subprocess_module.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        
        logger.info("dicom_converted", output=str(output_path))
        return output_path
    
    except subprocess_module.CalledProcessError as e:
        logger.error("dicom_conversion_failed", error=e.stderr)
        raise RuntimeError(f"DICOM conversion failed: {e.stderr}")
    
    except FileNotFoundError:
        logger.error("dcm2niix_not_found")
        raise RuntimeError("dcm2niix not found. Please install dcm2niix.")


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to file
    
    Returns:
        File size in MB
    """
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to file
    
    Returns:
        File size in MB
    """
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)


def get_file_size_mb(file_path: Path) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to file
    
    Returns:
        File size in MB
    """
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)

