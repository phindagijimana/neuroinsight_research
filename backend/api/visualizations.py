"""
API routes for serving segmentation visualizations.

Provides endpoints to retrieve NIfTI files and images for web viewers.
"""

from pathlib import Path
from uuid import UUID

import numpy as np

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models.job import JobStatus
from backend.services import JobService

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/visualizations", tags=["visualizations"])


def _find_optimal_hippocampus_slice(seg_data: np.ndarray, orientation: str, slice_idx: int, actual_orientation: tuple = None) -> int:
    """
    Find the optimal slice number for hippocampus visualization.

    Analyzes hippocampus distribution and maps slice indices 0-9 to evenly spaced
    slices within the region containing the most hippocampus voxels.

    Args:
        seg_data: Segmentation data array
        orientation: Image orientation ('axial', 'sagittal', 'coronal')
        slice_idx: Slice index (0-9) to map to optimal region

    Returns:
        Optimal slice number for the given orientation and index
    """
    # Create hippocampus mask (both left and right)
    hippocampus_mask = ((seg_data == 17) | (seg_data == 53))

    # Analyze hippocampus distribution along the specified orientation
    # Adapt based on actual file orientation for robust hippocampus detection
    if actual_orientation == ('L', 'S', 'P'):
        # FreeSurfer common orientation: Axis 0=L-R (X), Axis 1=S-I (Z), Axis 2=P-A (Y, flipped)
        if orientation == "axial":
            # Axial: horizontal cuts, sum over X and Y axes (0,2) for each Z slice (axis 1)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 2))
            total_slices = seg_data.shape[1]
        elif orientation == "sagittal":
            # Sagittal: left-right cuts, sum over Y and Z axes (1,2) for each X slice (axis 0)
            hippocampus_density = np.sum(hippocampus_mask, axis=(1, 2))
            total_slices = seg_data.shape[0]
        elif orientation == "coronal":
            # Coronal: front-back cuts, sum over X and Z axes (0,1) for each Y slice (axis 2)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 1))
            total_slices = seg_data.shape[2]
        else:
            # Fallback to linear mapping
            logger.warning("unknown_orientation_density_fallback", orientation=orientation)
            return slice_idx * (total_slices // 10)
    elif actual_orientation == ('L', 'I', 'A'):
        # FreeSurfer variant: Axis 0=L-R (X), Axis 1=I-S (inferior-superior, Z), Axis 2=A-P (Y)
        if orientation == "axial":
            # Axial: horizontal cuts, sum over X and Y axes (0,2) for each Z slice (axis 1)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 2))
            total_slices = seg_data.shape[1]
        elif orientation == "sagittal":
            # Sagittal: left-right cuts, sum over Y and Z axes (1,2) for each X slice (axis 0)
            hippocampus_density = np.sum(hippocampus_mask, axis=(1, 2))
            total_slices = seg_data.shape[0]
        elif orientation == "coronal":
            # Coronal: front-back cuts, sum over X and Z axes (0,1) for each A-P slice (axis 2)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 1))
            total_slices = seg_data.shape[2]
        else:
            # Fallback to linear mapping
            logger.warning("unknown_orientation_density_fallback", orientation=orientation)
            return slice_idx * (total_slices // 10)
    elif actual_orientation == ('R', 'A', 'S'):
        # Standard RAS+ orientation: Axis 0=R-L (X), Axis 1=A-P (Y), Axis 2=S-I (Z)
        if orientation == "axial":
            # Axial: horizontal cuts, sum over X and Y axes (0,1) for each Z slice (axis 2)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 1))
            total_slices = seg_data.shape[2]
        elif orientation == "sagittal":
            # Sagittal: left-right cuts, sum over Y and Z axes (1,2) for each X slice (axis 0)
            hippocampus_density = np.sum(hippocampus_mask, axis=(1, 2))
            total_slices = seg_data.shape[0]
        elif orientation == "coronal":
            # Coronal: front-back cuts, sum over X and Z axes (0,2) for each Y slice (axis 1)
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 2))
            total_slices = seg_data.shape[1]
        else:
            # Fallback to linear mapping
            logger.warning("unknown_orientation_density_fallback", orientation=orientation)
            return slice_idx * (total_slices // 10)
    else:
        # Unknown orientation - log warning and use standard assumption
        logger.warning("unknown_file_orientation_density_calculation",
                     detected_orientation=actual_orientation,
                     requested_orientation=orientation,
                     using_standard_fallback=True)
        # Assume standard orientation as fallback
        if orientation == "axial":
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 1))
            total_slices = seg_data.shape[2]
        elif orientation == "sagittal":
            hippocampus_density = np.sum(hippocampus_mask, axis=(1, 2))
            total_slices = seg_data.shape[0]
        elif orientation == "coronal":
            hippocampus_density = np.sum(hippocampus_mask, axis=(0, 2))
            total_slices = seg_data.shape[1]
        else:
            return slice_idx * (total_slices // 10)

    # Find the region with highest hippocampus concentration
    # Look for contiguous regions with high hippocampus density
    threshold = np.max(hippocampus_density) * 0.1  # 10% of max density
    high_density_slices = np.where(hippocampus_density > threshold)[0]

    if len(high_density_slices) == 0:
        # Fallback: use middle 50% of brain
        start_slice = total_slices // 4
        end_slice = 3 * total_slices // 4
    else:
        # Find the most concentrated contiguous region
        start_slice = np.min(high_density_slices)
        end_slice = np.max(high_density_slices)

        # Expand region slightly to include surrounding context
        region_size = end_slice - start_slice + 1
        expansion = max(1, region_size // 4)
        start_slice = max(0, start_slice - expansion)
        end_slice = min(total_slices - 1, end_slice + expansion)

    # Map 10 slice indices (0-9) evenly across the optimal region
    optimal_region_size = end_slice - start_slice + 1
    if optimal_region_size >= 10:
        # Evenly distribute 10 slices across the optimal region
        step = optimal_region_size / 9  # 9 intervals for 10 slices
        slice_position = start_slice + (slice_idx * step)
        optimal_slice = int(round(slice_position))
    else:
        # If optimal region is small, just use the middle area
        optimal_slice = start_slice + (slice_idx * optimal_region_size // 10)

    # Ensure slice number is within valid bounds
    optimal_slice = max(0, min(total_slices - 1, optimal_slice))

    return optimal_slice


def _generate_overlay_image(job_id: str, slice_id: str, orientation: str, layer: str, output_path: Path) -> bool:
    """
    Generate PNG overlay image on-demand from NIfTI files.

    Args:
        job_id: Job identifier
        slice_id: Slice identifier (e.g., 'slice_03')
        orientation: Image orientation ('axial', 'sagittal', 'coronal')
        layer: Layer type ('anatomical' or 'overlay')
        output_path: Path to save the PNG image

    Returns:
        bool: True if image was generated successfully
    """
    try:
        import nibabel as nib
        import numpy as np
        from PIL import Image
        import matplotlib.pyplot as plt
        import matplotlib.cm as cm
        logger.info("imports_successful")
    except ImportError as e:
        logger.error("missing_visualization_dependencies", error=str(e))
        return False

    # Find output directory - check both FastSurfer and FreeSurfer locations
    base_output_dir = Path(settings.output_dir) / str(job_id)

    # Try FastSurfer first (preferred)
    job_output_dir = base_output_dir / "fastsurfer"
    is_freesurfer = False

    if not job_output_dir.exists():
        # Try FreeSurfer Docker output
        freesurfer_dir = base_output_dir / "freesurfer" / "freesurfer_docker"
        if freesurfer_dir.exists():
            # Find the subject directory (format: freesurfer_docker_{job_id})
            subject_dirs = list(freesurfer_dir.glob(f"freesurfer_docker_{job_id}"))
            if subject_dirs:
                job_output_dir = subject_dirs[0]
                is_freesurfer = True
            else:
                # Check for any subject directory
                all_dirs = [d for d in freesurfer_dir.iterdir() if d.is_dir()]
                if all_dirs:
                    job_output_dir = all_dirs[0]
                    is_freesurfer = True

    if not job_output_dir.exists():
        logger.error("processing_output_not_found",
                    job_id=job_id,
                    fastsurfer_path=str(base_output_dir / "fastsurfer"),
                    freesurfer_path=str(base_output_dir / "freesurfer" / "freesurfer_docker"))
        return False

    logger.info("starting_image_generation", job_id=job_id, slice_id=slice_id, orientation=orientation, layer=layer)

    # Find segmentation file (needed for optimal slice selection for both layers)
    seg_paths = [
        job_output_dir / "mri" / "aseg.mgz",                    # Primary FreeSurfer output
        job_output_dir / "mri" / "aparc+aseg.mgz",             # Cortical parcellation + subcortical
        job_output_dir / "mri" / "aseg.presurf.mgz",           # Pre-surface segmentation
        job_output_dir / "mri" / "aseg.auto.mgz",              # Automatic segmentation
        job_output_dir / "mri" / "aseg.auto_noCCseg.mgz",      # Auto without corpus callosum
        job_output_dir / "mri" / "hippocampus_seg.nii.gz",     # Specialized hippocampus segmentation
    ]

    seg_file = None
    for path in seg_paths:
        if path.exists():
            seg_file = path
            break

    if not seg_file:
        logger.error("segmentation_file_not_found", job_id=job_id)
        return False

    logger.info("seg_file_found", seg_file=str(seg_file))

    # Load segmentation for optimal slice selection
    try:
        seg_img = nib.load(str(seg_file))
        seg_data = seg_img.get_fdata()

        # Check file orientation and adapt axis mapping
        actual_orientation = nib.aff2axcodes(seg_img.affine, labels=(("L", "R"), ("A", "P"), ("S", "I")))
        logger.info("backend_detected_orientation", orientation=actual_orientation, requested_orientation=orientation)

    except Exception as load_error:
        logger.error("segmentation_loading_failed", seg_file=str(seg_file), error=str(load_error))
        return False

    try:
        if layer == "anatomical":
            # Try to find anatomical T1 image
            anatomical_paths = [
                job_output_dir / "mri" / "orig_nu.mgz",
                job_output_dir / "mri" / "nu.mgz",
                job_output_dir / "mri" / "T1.mgz",
                job_output_dir / "mri" / "rawavg.mgz",
            ]

            anatomical_file = None
            for path in anatomical_paths:
                if path.exists():
                    anatomical_file = path
                    logger.info("found_anatomical_file", file=str(path))
                    break

            if not anatomical_file:
                logger.error("anatomical_file_not_found", job_id=job_id, paths=[str(p) for p in anatomical_paths])
                return False

            # Load and process anatomical image
            logger.info("loading_anatomical_file", file=str(anatomical_file))
            img = nib.load(str(anatomical_file))
            data = img.get_fdata()
            logger.info("anatomical_loaded", shape=data.shape, dtype=str(data.dtype))

        else:  # overlay
            # Create separate masks for left and right hippocampus
            left_hippocampus = (seg_data == 17).astype(np.uint8)   # Left hippocampus (blue)
            right_hippocampus = (seg_data == 53).astype(np.uint8)  # Right hippocampus (red)

            # Create RGBA overlay image
            data = np.zeros((*seg_data.shape, 4), dtype=np.uint8)

            # Set left hippocampus to blue with transparency
            data[left_hippocampus == 1] = [0, 100, 255, 180]   # Blue with 70% transparency

            # Set right hippocampus to red with transparency
            data[right_hippocampus == 1] = [255, 50, 50, 180]   # Red with 70% transparency

        # Extract slice based on orientation with optimal hippocampus region mapping
        slice_idx = int(slice_id.split('_')[1])  # Extract number from 'slice_03' (0-9)

        # Find optimal hippocampus region for this orientation
        optimal_slice_num = _find_optimal_hippocampus_slice(
            seg_data, orientation, slice_idx, actual_orientation
        )

        # Extract slice based on orientation and actual file orientation
        # Robust handling for different NIfTI orientations
        if actual_orientation == ('L', 'S', 'P'):
            # FreeSurfer common: Axis 0=L-R (X), Axis 1=S-I (Z), Axis 2=P-A (Y, flipped)
            if orientation == "axial":
                # Axial: horizontal cuts through brain, slice along Z-axis (axis 1)
                slice_data = data[:, optimal_slice_num, :] if layer == "anatomical" else data[:, optimal_slice_num, :]
            elif orientation == "sagittal":
                # Sagittal: left-right cuts, slice along X-axis (axis 0)
                slice_data = data[optimal_slice_num, :, :] if layer == "anatomical" else data[optimal_slice_num, :, :]
            elif orientation == "coronal":
                # Coronal: front-back cuts, slice along Y-axis (axis 2, flipped)
                slice_data = data[:, :, optimal_slice_num]  # Shape: (L, S) or (L, S, 4) for RGBA
                # For proper coronal display:
                # - Vertical should be Superior→Inferior (top of head→bottom)
                # - Horizontal should be Left→Right
                # Current: vertical=L-R, horizontal=S-I (rotated 90 degrees!)
                # Fix: transpose spatial axes only (preserve channel axis if present)
                if len(slice_data.shape) == 3:
                    # RGBA data with shape (L, S, 4) - transpose only first 2 axes
                    slice_data = np.transpose(slice_data, (1, 0, 2))  # Now (S, L, 4)
                else:
                    # Grayscale with shape (L, S) - simple transpose
                    slice_data = slice_data.T  # Now (S, L)
            else:
                logger.error("unsupported_orientation", orientation=orientation, file_orientation=actual_orientation)
                return False
        elif actual_orientation == ('L', 'I', 'A'):
            # FreeSurfer variant: Axis 0=L-R (X), Axis 1=I-S (inferior-superior, reversed Z), Axis 2=A-P (Y)
            if orientation == "axial":
                # Axial: horizontal cuts through brain, slice along Z-axis (axis 1)
                slice_data = data[:, optimal_slice_num, :]
                # For LIA: axis 1 is I-S (inferior to superior), so no flip needed for axial
            elif orientation == "sagittal":
                # Sagittal: left-right cuts, slice along X-axis (axis 0)
                slice_data = data[optimal_slice_num, :, :]
            elif orientation == "coronal":
                # Coronal: front-back cuts, slice along A-P axis (axis 2)
                slice_data = data[:, :, optimal_slice_num]  # Shape: (L, I) or (L, I, 4) for RGBA
                # For proper coronal display:
                # - Vertical should be Superior→Inferior (top of head→bottom)
                # - Horizontal should be Left→Right
                # Current: vertical=L-R, horizontal=I-S (WRONG!)
                # Fix: transpose spatial axes to get vertical=I-S, then flip to get S→I order
                if len(slice_data.shape) == 3:
                    # RGBA data with shape (L, I, 4) - transpose only first 2 axes
                    slice_data = np.transpose(slice_data, (1, 0, 2))  # Now (I, L, 4)
                    slice_data = np.flipud(slice_data)  # Flip to get Superior at top
                else:
                    # Grayscale with shape (L, I) - simple transpose and flip
                    slice_data = slice_data.T  # Now (I, L)
                    slice_data = np.flipud(slice_data)  # Flip to get Superior at top
            else:
                logger.error("unsupported_orientation", orientation=orientation, file_orientation=actual_orientation)
                return False
        elif actual_orientation == ('R', 'A', 'S'):
            # Standard RAS+ orientation: Axis 0=R-L (X), Axis 1=A-P (Y), Axis 2=S-I (Z)
            if orientation == "axial":
                # Axial: vary x,y, fix z
                slice_data = data[:, :, optimal_slice_num] if layer == "anatomical" else data[:, :, optimal_slice_num]
            elif orientation == "sagittal":
                slice_data = data[optimal_slice_num, :, :] if layer == "anatomical" else data[optimal_slice_num, :, :]
            elif orientation == "coronal":
                # Coronal: vary x,z, fix y
                slice_data = data[:, optimal_slice_num, :] if layer == "anatomical" else data[:, optimal_slice_num, :]
            else:
                logger.error("unsupported_orientation", orientation=orientation, file_orientation=actual_orientation)
                return False
        else:
            # Fallback for unknown orientations
            logger.warning("unknown_orientation_backend_fallback",
                         detected_orientation=actual_orientation,
                         requested_orientation=orientation,
                         using_standard_assumption=True)
            # Assume standard orientation as fallback
            if orientation == "axial":
                slice_data = data[:, :, optimal_slice_num] if layer == "anatomical" else data[:, :, optimal_slice_num]
            elif orientation == "sagittal":
                slice_data = data[optimal_slice_num, :, :] if layer == "anatomical" else data[optimal_slice_num, :, :]
            elif orientation == "coronal":
                slice_data = data[:, optimal_slice_num, :] if layer == "anatomical" else data[:, optimal_slice_num, :]
            else:
                logger.error("unsupported_orientation", orientation=orientation, file_orientation=actual_orientation)
                return False

        # Convert to PIL Image
        if layer == "anatomical":
            # Better normalization for brain tissue visualization
            # Use percentile-based contrast stretching for better brain visibility

            # Find brain tissue (non-zero voxels)
            brain_mask = slice_data > 0
            if np.sum(brain_mask) > 0:
                brain_intensities = slice_data[brain_mask]

                # Use 5th and 95th percentiles for robust contrast stretching
                # This avoids outliers and provides better brain tissue visibility
                p5 = np.percentile(brain_intensities, 5)
                p95 = np.percentile(brain_intensities, 95)

                # Apply contrast stretching
                slice_normalized = np.clip((slice_data - p5) / (p95 - p5), 0, 1)
                slice_normalized = (slice_normalized * 255).astype(np.uint8)
            else:
                # Fallback to simple normalization if no brain tissue found
                slice_normalized = ((slice_data - slice_data.min()) /
                                  (slice_data.max() - slice_data.min()) * 255).astype(np.uint8)

            # Create grayscale image
            img_pil = Image.fromarray(slice_normalized, mode='L').convert('RGB')
        else:
            # Create RGBA image for overlay
            height, width = slice_data.shape[:2]
            img_pil = Image.new('RGBA', (width, height), (0, 0, 0, 0))

            # Apply the overlay data
            overlay_pixels = img_pil.load()
            for y in range(height):
                for x in range(width):
                    if len(slice_data.shape) > 2 and slice_data.shape[2] == 4:
                        # RGBA data
                        r, g, b, a = slice_data[y, x]
                        overlay_pixels[x, y] = (r, g, b, a)
                    else:
                        # Binary mask or grayscale - check if pixel has value
                        pixel_val = slice_data[y, x]
                        # Handle both scalar and array pixel values
                        if np.any(pixel_val > 0):
                            # Binary mask - make red with transparency
                            overlay_pixels[x, y] = (255, 0, 0, 128)

        # Save the image
        img_pil.save(str(output_path), 'PNG')
        logger.info("generated_overlay_image", job_id=job_id, slice=slice_id, layer=layer, path=str(output_path))

        return True

    except Exception as e:
        import traceback
        logger.error("image_generation_failed", job_id=job_id, slice=slice_id, layer=layer, error=str(e), traceback=traceback.format_exc())
        return False


@router.get("/{job_id}/whole-hippocampus/anatomical")
def get_anatomical_t1(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get anatomical T1-weighted NIfTI file.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        NIfTI file (.nii.gz)
    
    Raises:
        HTTPException: If job not found or file missing
    """
    logger.info(f"Visualization request for job_id: {job_id}")

    job = JobService.get_job(db, job_id)
    logger.info(f"Job lookup result: {job}")

    if not job:
        logger.error(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        logger.error(f"Job not completed: {job.status}")
        raise HTTPException(status_code=400, detail="Job not yet completed")

    # Construct path to T1 file
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "whole_hippocampus"
    t1_path = viz_dir / "anatomical.nii.gz"

    logger.info(f"Looking for file at: {t1_path}")
    logger.info(f"File exists: {t1_path.exists()}")
    logger.info(f"Directory exists: {viz_dir.exists()}")
    logger.info(f"Directory contents: {list(viz_dir.glob('*')) if viz_dir.exists() else 'N/A'}")

    if not t1_path.exists():
        logger.error(f"Anatomical image not found at: {t1_path}")
        raise HTTPException(status_code=404, detail="Anatomical image not found")
    
    logger.info("serving_anatomical_t1", job_id=str(job_id))
    
    return FileResponse(
        path=t1_path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{job_id}_anatomical.nii.gz"',
            "Accept-Ranges": "bytes"
        }
    )


@router.get("/{job_id}/whole-hippocampus/nifti")
def get_whole_hippocampus_nifti(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get NIfTI file for whole hippocampus segmentation.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        NIfTI file (.nii.gz)
    
    Raises:
        HTTPException: If job not found or file missing
    """
    job = JobService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not yet completed")
    
    # Construct path to visualization files
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "whole_hippocampus"
    nifti_path = viz_dir / "segmentation.nii.gz"
    
    if not nifti_path.exists():
        raise HTTPException(status_code=404, detail="Segmentation file not found")
    
    logger.info("serving_whole_hippocampus_nifti", job_id=str(job_id))
    
    return FileResponse(
        path=nifti_path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{job_id}_whole_hippocampus.nii.gz"',
            "Accept-Ranges": "bytes"
        }
    )


@router.get("/{job_id}/whole-hippocampus/metadata")
def get_whole_hippocampus_metadata(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get metadata for whole hippocampus segmentation.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        JSON with label information and colormap
    
    Raises:
        HTTPException: If job not found or file missing
    """
    import json
    
    job = JobService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "whole_hippocampus"
    metadata_path = viz_dir / "segmentation_metadata.json"
    
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    return metadata


@router.get("/{job_id}/subfields/nifti")
def get_subfields_nifti(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get NIfTI file for hippocampal subfields segmentation.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        NIfTI file (.nii.gz)
    
    Raises:
        HTTPException: If job not found or file missing
    """
    job = JobService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not yet completed")
    
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "subfields"
    nifti_path = viz_dir / "segmentation.nii.gz"
    
    if not nifti_path.exists():
        raise HTTPException(status_code=404, detail="Subfields segmentation not found")
    
    logger.info("serving_subfields_nifti", job_id=str(job_id))
    
    return FileResponse(
        path=nifti_path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{job_id}_subfields.nii.gz"',
            "Accept-Ranges": "bytes"
        }
    )


@router.get("/{job_id}/subfields/metadata")
def get_subfields_metadata(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get metadata for hippocampal subfields segmentation.
    
    Args:
        job_id: Job identifier
        db: Database session dependency
    
    Returns:
        JSON with label information and colormap
    
    Raises:
        HTTPException: If job not found or file missing
    """
    import json
    
    job = JobService.get_job(db, job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "subfields"
    metadata_path = viz_dir / "segmentation_metadata.json"
    
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="Metadata not found")
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    return metadata


@router.api_route("/{job_id}/overlay/{slice_id}", methods=["GET", "HEAD"])
def get_overlay_image(
    job_id: str,
    slice_id: str,
    orientation: str = "axial",
    layer: str = "overlay",
    request: Request = None,
    db: Session = Depends(get_db),
):
    """
    Get PNG overlay image for a specific slice.

    Args:
        job_id: Job identifier
        slice_id: Slice identifier (e.g., "slice_00", "slice_01")
        orientation: Orientation (axial or coronal)
        layer: Layer type (anatomical or overlay)
        request: FastAPI request object
        db: Database session dependency

    Returns:
        PNG image file

    Raises:
        HTTPException: If job not found or file missing
    """
    is_head_request = request and request.method == "HEAD"

    logger.info("overlay_request", job_id=job_id, slice_id=slice_id, orientation=orientation, layer=layer, method=request.method if request else "unknown")

    # Get job by string ID
    job = JobService.get_job(db, job_id)

    if not job:
        logger.error("job_not_found", job_id=str(job_id))
        if is_head_request:
            return Response(status_code=404)
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        logger.error("job_not_completed", job_id=str(job_id), status=job.status)
        if is_head_request:
            return Response(status_code=404)  # Return 404 for incomplete jobs on HEAD
        raise HTTPException(status_code=400, detail="Job not yet completed")

    # Try to find existing PNG first, then generate on-demand
    viz_dir = Path(settings.output_dir) / str(job_id) / "visualizations" / "overlays" / orientation
    viz_dir.mkdir(parents=True, exist_ok=True)

    # Extract slice number from slice_id (format: "slice_00" -> 0)
    try:
        slice_num = int(slice_id.split('_')[1])
        slice_str = f"{slice_num:02d}"
    except (ValueError, IndexError):
        slice_str = slice_id  # fallback to original

    if layer == "anatomical":
        image_path = viz_dir / f"anatomical_slice_{slice_str}.png"
    else:
        image_path = viz_dir / f"hippocampus_overlay_slice_{slice_str}.png"

    logger.info("checking_image_path", path=str(image_path), exists=image_path.exists())

    # If image doesn't exist, try to generate it from NIfTI files
    if not image_path.exists():
        logger.info("generating_image_on_demand", job_id=str(job_id), slice=slice_id, layer=layer)
        try:
            success = _generate_overlay_image(job_id, slice_id, orientation, layer, image_path)
            if not success:
                logger.error("image_generation_failed", job_id=str(job_id), slice=slice_id, layer=layer)
                if is_head_request:
                    return Response(status_code=404)
                raise HTTPException(status_code=404, detail=f"Could not generate {layer} image for {orientation} {slice_id}")
        except Exception as e:
            logger.error("image_generation_error", job_id=str(job_id), slice=slice_id, layer=layer, error=str(e))
            if is_head_request:
                return Response(status_code=404)
            raise HTTPException(status_code=500, detail=f"Error generating {layer} image: {str(e)}")

    logger.info("serving_overlay_image", job_id=str(job_id), slice=slice_id, orientation=orientation, layer=layer)

    logger.info("serving_overlay_image", job_id=str(job_id), slice=slice_id, orientation=orientation, layer=layer)

    if is_head_request:
        # For HEAD requests, just return success status
        return Response(status_code=200)

    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=f"{job_id}_{orientation}_{layer}_{slice_id}.png"
    )


# Placeholder endpoints for frontend compatibility
# These need to be mounted at the root API level, not under visualizations router

