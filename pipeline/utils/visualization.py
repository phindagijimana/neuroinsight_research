"""Visualization utilities for MRI segmentation.

Responsibilities
- Extract and convert FreeSurfer outputs for visualization
- Generate overlay PNGs with hippocampus highlighted
- Preserve physical aspect ratio and upright orientation for images/text
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    MATPLOTLIB_AVAILABLE = True
except ImportError as e:
    # Fail loudly - matplotlib is required for visualization generation
    raise ImportError(
        "matplotlib is required for visualization generation but is not installed. "
        "Please install it with: pip install matplotlib>=3.5.0"
    ) from e

import nibabel as nib
import numpy as np

from backend.core.logging import get_logger
import subprocess as subprocess_module

logger = get_logger(__name__)


# Color map for hippocampal subfields - Unified NeuroInsight theme
# All hippocampal regions use the same #003d7a (RGB: 0, 61, 122) color
SUBFIELD_COLORS = {
    "whole_hippocampus": [0, 61, 122],     # NeuroInsight blue
    "CA1": [0, 61, 122],                   # NeuroInsight blue
    "CA3": [0, 61, 122],                   # NeuroInsight blue
    "CA4_DG": [0, 61, 122],                # NeuroInsight blue (dentate gyrus)
    "subiculum": [0, 61, 122],             # NeuroInsight blue
    "presubiculum": [0, 61, 122],          # NeuroInsight blue
    "fimbria": [0, 61, 122],               # NeuroInsight blue
    "HATA": [0, 61, 122],                  # NeuroInsight blue
}

# FreeSurfer label constants
ASEG_HIPPOCAMPUS_LABELS = {
    17: "Left-Hippocampus",
    53: "Right-Hippocampus"
}

# FreeSurfer doesn't provide detailed hippocampal subfields
# These would be available if using specialized subfield segmentation
HIPPOCAMPAL_SUBFIELD_LABELS = {
    # Placeholder for future subfield segmentation
    # Currently, FreeSurfer only provides whole hippocampus labels
}


def generate_all_orientation_overlays(
    t1_path: Path,
    seg_path: Path,
    output_base_dir: Path,
    prefix: str = "hippocampus",
    specific_labels: list = None
) -> Dict[str, Dict[str, str]]:
    """
    Generate overlay images for axial and coronal orientations.
    
    Args:
        t1_path: Path to T1 NIfTI file
        seg_path: Path to segmentation NIfTI file
        output_base_dir: Base output directory (will create subdirs for each orientation)
        prefix: Filename prefix
        specific_labels: Optional list of label values to display
    
    Returns:
        Dictionary mapping orientation to overlay paths:
        {'axial': {'slice_00': 'path...', ...}, 'coronal': {...}}
    """
    logger.info("generating_all_orientations", 
                t1=str(t1_path), 
                seg=str(seg_path),
                labels=specific_labels)
    
    results = {}
    
    for orientation in ['axial', 'coronal']:
        try:
            orientation_dir = output_base_dir / orientation
            orientation_dir.mkdir(parents=True, exist_ok=True)
            
            overlays = generate_segmentation_overlays(
                t1_path,
                seg_path,
                orientation_dir,
                prefix=prefix,
                specific_labels=specific_labels,
                orientation=orientation
            )
            
            results[orientation] = overlays
            logger.info(f"{orientation}_overlays_generated", count=len(overlays))
            
        except Exception as e:
            logger.error(f"{orientation}_overlay_generation_failed", error=str(e))
            results[orientation] = {}
    
    return results


def generate_segmentation_overlays(
    t1_path: Path,
    seg_path: Path,
    output_dir: Path,
    prefix: str = "overlay",
    specific_labels: list = None,
    orientation: str = "axial"
) -> Dict[str, str]:
    """
    Generate PNG overlay images showing segmentation on T1 scan.
    
    Creates multiple slices with segmentation overlay in specified orientation.
    Generates 10 evenly-spaced images showing the extent of the segmented structure.
    
    Args:
        t1_path: Path to T1 NIfTI file
        seg_path: Path to segmentation NIfTI file
        output_dir: Output directory for images
        prefix: Filename prefix
        specific_labels: Optional list of label values to display (e.g., [17, 53] for hippocampus)
                        If None, shows all labels
        orientation: One of 'axial' or 'coronal'
    
    Returns:
        Dictionary with paths to generated images (e.g., {'slice_00': 'path/to/image.png', ...})
    """
    logger.info("generating_segmentation_overlays", 
                t1=str(t1_path), 
                seg=str(seg_path), 
                labels=specific_labels,
                orientation=orientation)
    
    # Validate orientation
    if orientation not in ['axial', 'coronal']:
        raise ValueError(f"Invalid orientation: {orientation}. Must be 'axial' or 'coronal'")
    
    try:
        # Load images
        t1_img = nib.load(t1_path)
        seg_img = nib.load(seg_path)
        
        t1_data = t1_img.get_fdata()
        # Voxel sizes (mm) to preserve physical aspect ratio
        vx, vy, vz = t1_img.header.get_zooms()[:3]
        seg_data = seg_img.get_fdata()
        
        # Determine slicing parameters based on orientation
        # Check actual file orientation and adapt accordingly for robust handling
        actual_orientation = nib.aff2axcodes(t1_img.affine, labels=(("L", "R"), ("A", "P"), ("S", "I")))
        logger.info("detected_file_orientation", orientation=actual_orientation, requested_orientation=orientation)

        # Map orientations to correct axis slicing based on actual file orientation
        # Standard neuroimaging: axial = horizontal (Z), coronal = front-back (Y), sagittal = left-right (X)
        if actual_orientation == ('L', 'S', 'P'):
            # FreeSurfer common orientation: Axis 0=L-R (X), Axis 1=S-I (Z), Axis 2=P-A (Y, flipped)
            orientation_axis_map = {
                'axial': 1,      # Superior-Inferior (Z-axis) - horizontal brain cuts
                'coronal': 2,    # Anterior-Posterior (Y-axis, flipped) - front-back brain cuts
                'sagittal': 0    # Left-Right (X-axis) - left-right brain cuts
            }
            if orientation == 'axial':
                slice_axis = 1
                display_axes = (0, 2)  # L-R vs A-P (accounting for flip)
                voxel_sizes = (vx, vz)
                axis_labels = ('Left-Right', 'Anterior-Posterior')
            elif orientation == 'coronal':
                slice_axis = 2
                display_axes = (0, 1)  # L-R vs S-I
                voxel_sizes = (vx, vy)
                axis_labels = ('Left-Right', 'Superior-Inferior')
        elif actual_orientation == ('R', 'A', 'S'):
            # Standard RAS+ orientation: Axis 0=R-L (X), Axis 1=A-P (Y), Axis 2=S-I (Z)
            if orientation == 'axial':
                slice_axis = 2  # Superior-Inferior (Z-axis)
                display_axes = (0, 1)  # R-L vs A-P
                voxel_sizes = (vx, vy)
                axis_labels = ('Right-Left', 'Anterior-Posterior')
            elif orientation == 'coronal':
                slice_axis = 1  # Anterior-Posterior (Y-axis)
                display_axes = (0, 2)  # R-L vs S-I
                voxel_sizes = (vx, vz)
                axis_labels = ('Right-Left', 'Superior-Inferior')
        else:
            # Fallback for other orientations - log warning and use reasonable defaults
            logger.warning("unknown_orientation_fallback",
                         detected_orientation=actual_orientation,
                         requested_orientation=orientation,
                         using_standard_fallback=True)
            # Assume orientation similar to RAS+ but with unknown axis ordering
            if orientation == 'axial':
                slice_axis = 2  # Assume Z-axis for axial (most common)
                display_axes = (0, 1)
                voxel_sizes = (vx, vy)
                axis_labels = ('Axis-0', 'Axis-1')
            elif orientation == 'coronal':
                slice_axis = 1  # Assume Y-axis for coronal
                display_axes = (0, 2)
                voxel_sizes = (vx, vz)
                axis_labels = ('Axis-0', 'Axis-2')
        
        # Verify spatial alignment - check affine matrices match
        # This ensures T1 and segmentation are in the same coordinate system
        affine_t1 = t1_img.affine
        affine_seg = seg_img.affine
        
        if not np.allclose(affine_t1, affine_seg, atol=1e-2):
            logger.warning("affine_mismatch",
                          t1_affine=str(affine_t1),
                          seg_affine=str(affine_seg),
                          max_diff=str(np.abs(affine_t1 - affine_seg).max()),
                          note="T1 and segmentation may not be properly aligned spatially")
        else:
            logger.info("affine_verified", 
                       note="T1 and segmentation are in the same coordinate space")
        
        # CRITICAL: Handle spatial transformation between different coordinate systems
        # FreeSurfer segmentation is in conformed space, T1 is in scanner space
        if not np.allclose(affine_t1, affine_seg, atol=1e-3):
            logger.warning("coordinate_system_mismatch",
                          note="T1 and segmentation are in different coordinate systems - applying spatial transformation")

            # Use nibabel to properly transform segmentation to T1 space
            # nibabel is already imported at the top of the file
            from nibabel.processing import resample_to_output

            # Create NIfTI images with their respective affines
            t1_img = nib.Nifti1Image(t1_data, affine_t1)
            seg_img = nib.Nifti1Image(seg_data.astype(np.int16), affine_seg)

            # Resample segmentation to match T1 space using proper nibabel resampling
            from nibabel import processing
            resampled_seg_img = processing.resample_from_to(seg_img, (t1_img.shape, t1_img.affine), order=0)
            seg_data = resampled_seg_img.get_fdata()

            logger.info("spatial_transformation_applied",
                       original_shape=seg_img.shape,
                       target_shape=t1_img.shape,
                       final_shape=seg_data.shape,
                       note="Segmentation transformed to T1 coordinate space")

        # Check dimensions after transformation
        if t1_data.shape != seg_data.shape:
            logger.warning("dimension_mismatch_after_transform",
                          t1_shape=t1_data.shape, 
                          seg_shape=seg_data.shape,
                          note="Dimensions still don't match after spatial transformation")

            # Final fallback: simple zoom if needed (shouldn't be necessary after proper transform)
            from scipy.ndimage import zoom
            zoom_factors = [t1_data.shape[i] / seg_data.shape[i] for i in range(3)]
            if not all(abs(f - 1.0) < 0.01 for f in zoom_factors):  # Only zoom if significant difference
                seg_data = zoom(seg_data, zoom_factors, order=0)
                logger.warning("final_dimension_adjustment",
                             zoom_factors=zoom_factors,
                             note="Applied final dimension adjustment")
        
        # Create a mask for specific labels if requested (for hippocampus highlighting)
        highlight_mask = None
        if specific_labels is not None:
            logger.info("filtering_segmentation_labels", labels=specific_labels)
            highlight_mask = np.zeros_like(seg_data, dtype=bool)
            for label in specific_labels:
                highlight_mask |= (seg_data == label)
                count = np.sum(seg_data == label)
                logger.info("label_voxel_count", label=label, count=int(count))
        
        # Normalize T1 data for display using percentile-based normalization
        # This prevents uniform grey appearance from skewed data distributions
        t1_min = np.percentile(t1_data[t1_data > 0], 5) if np.any(t1_data > 0) else np.min(t1_data)
        t1_max = np.percentile(t1_data[t1_data > 0], 95) if np.any(t1_data > 0) else np.max(t1_data)

        # Ensure we have a valid range
        if t1_max <= t1_min:
            t1_max = np.max(t1_data)
            t1_min = np.min(t1_data)

        if t1_max > t1_min:
            t1_normalized = np.clip((t1_data - t1_min) / (t1_max - t1_min), 0, 1)
        else:
            # Fallback: use simple scaling
            t1_normalized = (t1_data - np.min(t1_data)) / (np.max(t1_data) - np.min(t1_data) + 1e-8)
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Smart slice selection: prioritize slices with highest hippocampus visibility
        # Uses anatomical knowledge and segmentation data to select optimal slices
        total_slices = t1_data.shape[slice_axis]
        num_slices = 10

        # Method 1: Find hippocampus extent and sample evenly across full range
        if highlight_mask is not None:
            # Count hippocampus voxels in each slice along the current axis
            hippocampus_counts = []
            for slice_idx in range(total_slices):
                if slice_axis == 2:  # axial (Z-axis)
                    slice_voxels = highlight_mask[:, :, slice_idx]
                elif slice_axis == 1:  # coronal (Y-axis)
                    slice_voxels = highlight_mask[:, slice_idx, :]
                else:  # sagittal (X-axis)
                    slice_voxels = highlight_mask[slice_idx, :, :]

                hippo_count = np.sum(slice_voxels)
                hippocampus_counts.append(hippo_count)

            # Find hippocampus visibility region using adaptive threshold
            max_hippo_count = max(hippocampus_counts) if hippocampus_counts else 0

            # Adaptive threshold: 5% of max count, but at least 1 voxel
            threshold = max(max_hippo_count * 0.05, 1.0)

            # Find start: first slice where hippocampus becomes visible
            hippo_start = None
            for i, count in enumerate(hippocampus_counts):
                if count >= threshold:
                    hippo_start = i
                    break

            # Find end: last slice where hippocampus is still visible
            hippo_end = None
            for i in range(len(hippocampus_counts) - 1, -1, -1):
                if hippocampus_counts[i] >= threshold:
                    hippo_end = i
                    break

            if hippo_start is not None and hippo_end is not None and hippo_end > hippo_start:
                # Evenly divide hippocampus extent into 10 slices
                hippo_range = hippo_end - hippo_start
                slice_indices = []

                for i in range(num_slices):
                    # Linear interpolation across hippocampus extent
                    fraction = i / (num_slices - 1) if num_slices > 1 else 0
                    slice_position = hippo_start + (fraction * hippo_range)
                    slice_idx = int(round(slice_position))

                    # Ensure bounds
                    slice_idx = max(0, min(slice_idx, total_slices - 1))
                    slice_indices.append(slice_idx)

                # Remove duplicates while maintaining order
                unique_indices = []
                for idx in slice_indices:
                    if idx not in unique_indices:
                        unique_indices.append(idx)

                # If we lost slices due to duplicates, add adjacent slices
                while len(unique_indices) < num_slices and len(unique_indices) > 0:
                    last_idx = unique_indices[-1]
                    next_idx = min(last_idx + 1, total_slices - 1)
                    if next_idx not in unique_indices:
                        unique_indices.append(next_idx)

                slice_indices = unique_indices[:num_slices]

                logger.info(f"generating_{orientation}_slices_hippocampus_extent",
                           indices=slice_indices,
                           hippo_start=hippo_start,
                           hippo_end=hippo_end,
                           hippo_range=hippo_range,
                           threshold=int(threshold),
                           max_count=max_hippo_count,
                           total_volume_slices=total_slices,
                           note=f"Evenly sampled {len(slice_indices)} slices across hippocampus extent ({hippo_start}-{hippo_end})")

            else:
                # Fallback: use top slices if extent detection fails
                logger.warning(f"hippocampus_extent_detection_failed_{orientation}",
                             max_count=max_hippo_count,
                             threshold=int(threshold),
                             hippo_start=hippo_start,
                             hippo_end=hippo_end,
                             note="Falling back to top slice selection")

                # Create index-count pairs and sort by count
                slice_count_pairs = [(i, count) for i, count in enumerate(hippocampus_counts)]
                slice_count_pairs.sort(key=lambda x: x[1], reverse=True)

                # Take top slices
                top_slices = [s[0] for s in slice_count_pairs[:num_slices]]
                slice_indices = sorted(top_slices)

                logger.info(f"generating_{orientation}_slices_fallback_top",
                           indices=slice_indices,
                           hippo_counts=[s[1] for s in slice_count_pairs[:num_slices]],
                           note=f"Fallback: selected top {len(slice_indices)} hippocampus-containing slices")

        else:
            # Fallback: Use anatomical knowledge for hippocampus location
            # Hippocampus is typically in inferior temporal region
            if orientation == 'axial':
                # Axial: Focus on inferior slices where temporal lobe is visible
                # Hippocampus spans roughly 30-70% of superior-inferior axis
                start_percent = 0.25  # Start from more inferior position
                end_percent = 0.75    # End before most superior slices
            elif orientation == 'coronal':
                # Coronal: Hippocampus visible in posterior temporal region
                # Focus on slices showing temporal lobe (typically middle 60%)
                start_percent = 0.20
                end_percent = 0.80
            else:  # sagittal
                # Sagittal: Focus on medial slices
                start_percent = 0.30
                end_percent = 0.70

            start_offset = int(total_slices * start_percent)
            end_offset = int(total_slices * end_percent)
            usable_range = end_offset - start_offset

            slice_indices = []
            for i in range(num_slices):
                slice_idx = start_offset + int((i + 0.5) * usable_range / num_slices)
                slice_idx = max(0, min(slice_idx, total_slices - 1))
                slice_indices.append(slice_idx)

            logger.info(f"generating_{orientation}_slices_anatomy_optimized",
                       indices=slice_indices,
                       total_volume_slices=total_slices,
                       note=f"Using anatomy-optimized slices for {orientation} view ({start_percent:.0%}-{end_percent:.0%} range)")
        
        output_paths = {}
        
        # Generate overlay for each slice
        for idx, slice_num in enumerate(slice_indices):
            # Get T1 and segmentation data for this slice based on orientation
            # Dynamic slicing based on orientation - CRITICAL for alignment
            if slice_axis == 0:  # Sagittal (X-axis slicing)
                t1_slice = t1_normalized[slice_num, :, :]
                seg_slice = seg_data[slice_num, :, :]
            elif slice_axis == 1:  # Coronal (Y-axis slicing)
                t1_slice = t1_normalized[:, slice_num, :]
                seg_slice = seg_data[:, slice_num, :]
            else:  # Axial (slice_axis == 2, Z-axis slicing)
                t1_slice = t1_normalized[:, :, slice_num]
                seg_slice = seg_data[:, :, slice_num]
            
            # Reorder axes if needed for consistent display
            # Flip 180 degrees for both axial and coronal to ensure correct anatomical orientation
            # Axial: view from below (looking up) - neurological convention
            # Coronal: anterior up (front of brain at top) - standard radiological view
            if orientation in ['axial', 'coronal']:
                t1_slice = np.flip(t1_slice, axis=(0, 1))
                seg_slice = np.flip(seg_slice, axis=(0, 1))
            
            # ====================================================================
            # STEP 1: Generate anatomical-only image (grayscale T1 brain)
            # ====================================================================
            fig, ax = plt.subplots(figsize=(8, 8))

            # Ensure we have valid data and proper scaling
            # Ensure we have valid data and proper scaling
            if t1_slice.size > 0 and np.any(t1_slice != 0):
                # Use the already correctly extracted and oriented t1_slice
                t1_display = t1_slice

                # Simple display without complex extent calculation
                ax.imshow(t1_display.T, cmap="gray", origin="upper", interpolation="bilinear")
                ax.axis("off")
                # Simple display without complex extent calculation
                ax.imshow(t1_display.T, cmap='gray', origin='upper', interpolation='bilinear')
                ax.axis('off')

                # Save anatomical-only image
                anatomical_path = output_dir / f"anatomical_slice_{idx:02d}.png"
                plt.savefig(anatomical_path, bbox_inches='tight', dpi=150, facecolor='white')
                plt.close()
                logger.info("saved_anatomical_slice", slice_num=slice_num, idx=idx, path=str(anatomical_path), orientation=orientation)
            else:
                logger.warning("empty_t1_slice", slice_num=slice_num, idx=idx, orientation=orientation)
                # Create empty placeholder
                fig.patch.set_facecolor('white')
                ax.text(0.5, 0.5, 'No brain data', ha='center', va='center', transform=ax.transAxes)
                anatomical_path = output_dir / f"anatomical_slice_{idx:02d}.png"
                plt.savefig(anatomical_path, bbox_inches='tight', dpi=150, facecolor='white')
                plt.close()
            
            
            # ====================================================================
            # STEP 2: Generate overlay-only image (transparent PNG with hippocampus)
            # ====================================================================
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.set_aspect('equal')
            
            # Make background transparent
            fig.patch.set_alpha(0)
            ax.patch.set_alpha(0)
            
            # Overlay segmentation with label-specific colors
            if specific_labels is not None:
                # Create a colored overlay preserving label values
                # Only show voxels that match specific labels (e.g., 17, 53 for hippocampus)
                overlay_data = np.zeros_like(seg_slice)
                for label in specific_labels:
                    overlay_data[seg_slice == label] = label
                
                # Mask zero values (background)
                overlay_masked = np.ma.masked_where(overlay_data == 0, overlay_data)
                
                if np.any(overlay_masked):
                    # Create custom colormap for hippocampus labels
                    # Label 17 (Left-Hippocampus) -> Red
                    # Label 53 (Right-Hippocampus) -> Blue
                    
                    # Define colors for each label
                    colors = [(0, 0, 0, 0)]  # Transparent background
                    bounds = [0]
                    for label in specific_labels:
                        if label == 17:  # Left-Hippocampus
                            colors.append('#FF3333')  # Bright red
                        elif label == 53:  # Right-Hippocampus
                            colors.append('#3399FF')  # Bright blue
                        else:
                            colors.append('#FFAA00')  # Orange for other labels
                        bounds.append(label)
                    
                    bounds.append(max(specific_labels) + 1)
                    cmap = ListedColormap(colors)
                    norm = BoundaryNorm(bounds, cmap.N)
                    
                    # Display overlay with full opacity (opacity will be controlled by frontend)
                    ax.imshow(
                        overlay_masked.T,
                        cmap=cmap,
                        norm=norm,
                        alpha=1.0,  # Full opacity - frontend will control the blending
                        origin='upper',
                        interpolation='nearest',
                        extent=[0, voxel_sizes[0] * t1_slice.shape[0], 0, voxel_sizes[1] * t1_slice.shape[1]],
                        aspect='equal',
                    )
            else:
                # Show all labels with generic hot colormap
                overlay_masked = np.ma.masked_where(seg_slice == 0, seg_slice)
                if np.any(overlay_masked):
                    ax.imshow(
                        overlay_masked.T,
                        cmap='hot',
                        alpha=1.0,  # Full opacity - frontend will control the blending
                        origin='upper',
                        interpolation='nearest',
                        extent=[0, voxel_sizes[0] * t1_slice.shape[0], 0, voxel_sizes[1] * t1_slice.shape[1]],
                        aspect='equal',
                    )
            
            ax.axis('off')
            # Save overlay-only image (transparent PNG)
            overlay_path = output_dir / f"hippocampus_overlay_slice_{idx:02d}.png"
            plt.savefig(overlay_path, bbox_inches='tight', dpi=150, transparent=True)
            plt.close()
            
            logger.info("saved_overlay_slice", slice_num=slice_num, idx=idx, path=str(overlay_path), orientation=orientation)
            
            # Store both paths
            output_paths[f"slice_{idx:02d}"] = {
                "anatomical": str(anatomical_path),
                "overlay": str(overlay_path)
            }
            logger.info("saved_layered_slices", slice_num=slice_num, idx=idx, orientation=orientation)
        
        return output_paths
    
    except Exception as e:
        logger.error("overlay_generation_failed", error=str(e))
        return {}


def convert_t1_to_nifti(
    t1_mgz_path: Path,
    output_dir: Path
) -> Path:
    """
    Convert T1-weighted anatomical image from MGZ to NIfTI format.
    
    Args:
        t1_mgz_path: Path to orig.mgz or similar T1 image
        output_dir: Output directory
        
    Returns:
        Path to converted NIfTI file
    """
    logger.info("converting_t1_to_nifti", input=str(t1_mgz_path))
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "anatomical.nii.gz"
    
    try:
        # Load MGZ and save as NIfTI
        img = nib.load(t1_mgz_path)
        nib.save(img, output_path)
        
        logger.info("t1_conversion_complete", output=str(output_path))
        return output_path
        
    except Exception as e:
        logger.error("t1_conversion_failed", error=str(e))
        raise


def prepare_nifti_for_viewer(
    seg_path: Path,
    output_dir: Path,
    label_map: Dict[int, str],
    highlight_labels: list = None
) -> Dict[str, str]:
    """
    Prepare NIfTI segmentation file for web-based viewer.
    
    Creates a compressed NIfTI file and associated metadata JSON.
    
    Args:
        seg_path: Path to segmentation NIfTI file
        output_dir: Output directory
        label_map: Mapping of label values to names
        highlight_labels: Optional list of labels to show in legend (e.g., [17, 53] for hippocampus)
                         If None, shows all labels. Other labels still visible but not in legend.
    
    Returns:
        Dictionary with paths to files
    """
    logger.info("preparing_nifti_for_viewer", 
                seg=str(seg_path),
                highlight_labels=highlight_labels)
    
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load segmentation
        seg_img = nib.load(seg_path)
        seg_data = seg_img.get_fdata()
        
        # Get unique labels
        unique_labels = np.unique(seg_data[seg_data > 0])
        
        # If highlight_labels specified, only include those in metadata legend
        if highlight_labels is not None:
            labels_for_legend = [l for l in unique_labels if int(l) in highlight_labels]
            logger.info("filtering_legend_labels", 
                       total_labels=len(unique_labels),
                       legend_labels=len(labels_for_legend))
        else:
            labels_for_legend = unique_labels
        
        # Create metadata
        metadata = {
            "labels": {},
            "colormap": {}
        }
        
        # Build metadata only for labels that should appear in legend
        for label_val in labels_for_legend:
            label_val_int = int(label_val)
            label_name = label_map.get(label_val_int, f"Label_{label_val_int}")
            
            metadata["labels"][label_val_int] = label_name
            
            # Assign color based on structure
            # Hippocampus gets bright, distinct colors
            if label_val_int == 17:  # Left Hippocampus
                color = [255, 50, 50]  # Bright Red
                alpha = 255
            elif label_val_int == 53:  # Right Hippocampus
                color = [50, 150, 255]  # Bright Blue
                alpha = 255
            # Other structures get subtle gray tones
            else:
                # Vary gray levels slightly based on label for better visualization
                gray_level = 150 + (label_val_int % 80)
                color = [gray_level, gray_level, gray_level]
                alpha = 100  # More transparent for non-hippocampus
            
            metadata["colormap"][label_val_int] = {
                "r": color[0],
                "g": color[1],
                "b": color[2],
                "a": alpha
            }
        
        # Save compressed NIfTI
        output_nii_path = output_dir / "segmentation.nii.gz"
        nib.save(seg_img, output_nii_path)
        
        # Save metadata
        metadata_path = output_dir / "segmentation_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info("nifti_prepared_for_viewer", 
                   nifti=str(output_nii_path),
                   metadata=str(metadata_path))
        
        return {
            "nifti": str(output_nii_path),
            "metadata": str(metadata_path),
            "label_count": len(unique_labels)
        }
    
    except Exception as e:
        logger.error("nifti_preparation_failed", error=str(e))
        return {}


def extract_hippocampus_segmentation(
    freesurfer_dir: Path,
    job_id: str
) -> Tuple[Path, Path]:
    """
    Extract hippocampus segmentation files from FreeSurfer output.
    
    Args:
        freesurfer_dir: FreeSurfer output directory
        job_id: Job identifier
    
    Returns:
        Tuple of (whole_hippocampus_path, subfields_path)
    """
    logger.info("extracting_hippocampus_segmentation", job_id=job_id)
    
    # Find the FreeSurfer subject directory
    subject_dir = None
    for subdir in ["freesurfer_singularity", "freesurfer_docker", "freesurfer_fallback"]:
        candidate_dir = freesurfer_dir / f"{subdir}_{job_id}"
        if candidate_dir.exists():
            subject_dir = candidate_dir
            logger.info("found_freesurfer_subject_dir", dir=str(subject_dir))
            break

    if not subject_dir:
        logger.warning("no_freesurfer_subject_dir_found", freesurfer_dir=str(freesurfer_dir))
        return None, None

    mri_dir = subject_dir / "mri"
    
    # FreeSurfer whole brain segmentation (contains hippocampus labels)
    # Try multiple fallback paths in order of preference
    aseg_candidates = [
        mri_dir / "aseg.auto.mgz",      # Auto segmentation (preferred)
        mri_dir / "aseg.mgz",            # Standard segmentation
    ]
    
    aseg_path = None
    for candidate in aseg_candidates:
        if candidate.exists():
            aseg_path = candidate
            logger.info("found_aseg_file", path=str(candidate), job_id=job_id)
            break
    
    if not aseg_path:
        # Last resort - look for any aseg file
        import glob
        aseg_files = glob.glob(str(mri_dir / "aseg*.mgz"))
        if aseg_files:
            aseg_path = Path(aseg_files[0])
            logger.info("found_aseg_file_wildcard", path=str(aseg_path), job_id=job_id)

    # FreeSurfer doesn't generate separate hippocampal subfield files
    # The hippocampus labels are embedded in the aseg.auto.mgz file
    # We'll extract hippocampus regions from the main segmentation
    subfields_nii = None  # FreeSurfer doesn't provide detailed subfields
    
    # Convert MGZ to NIfTI if needed
    if aseg_path.exists():
        logger.info("found_freesurfer_aseg_file", path=str(aseg_path))
        aseg_nii = convert_mgz_to_nifti(aseg_path, mri_dir / "aseg_for_viz.nii.gz")
    else:
        logger.warning("freesurfer_aseg_file_not_found",
                      expected=str(aseg_path),
                      searched_dir=str(mri_dir))
        aseg_nii = None
    
    return aseg_nii, subfields_nii


def convert_mgz_to_nifti(mgz_path: Path, output_path: Path) -> Path:
    """
    Convert MGZ file to NIfTI format.

    Args:
        mgz_path: Input MGZ file
        output_path: Output NIfTI path

    Returns:
        Path to converted file
    """
    try:
        img = nib.load(mgz_path)

        # Try to save to the requested location first
        nib.save(img, output_path)
        logger.info("mgz_converted_to_nifti", input=str(mgz_path), output=str(output_path))
        return output_path

    except PermissionError as e:
        # If permission denied, try multiple fallback approaches
        logger.warning("permission_denied_converting_mgz",
                      path=str(output_path),
                      error=str(e))

        # Get current user dynamically for universal compatibility
        import getpass
        import subprocess
        import tempfile
        import shutil

        current_user = getpass.getuser()
        target_dir = output_path.parent

        # Approach 1: Try to fix ownership with current user
        try:
            logger.info("attempting_ownership_fix", user=current_user, directory=str(target_dir))
            subprocess.run(['sudo', 'chown', '-R', f'{current_user}:{current_user}', str(target_dir)],
                         check=True, capture_output=True, timeout=30)

            # Retry the save
            nib.save(img, output_path)
            logger.info("mgz_converted_after_ownership_fix",
                       input=str(mgz_path), output=str(output_path), user=current_user)
            return output_path

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as chown_error:
            logger.warning("sudo_chown_failed",
                          error=str(chown_error),
                          user=current_user,
                          trying_alternative=True)

            # Approach 2: Copy to temporary directory owned by current user
            try:
                with tempfile.NamedTemporaryFile(suffix='.nii.gz', delete=False) as temp_file:
                    temp_path = Path(temp_file.name)

                logger.info("attempting_temp_file_conversion", temp_path=str(temp_path))
                nib.save(img, temp_path)

                # Try to copy back to original location
                try:
                    shutil.copy2(temp_path, output_path)
                    temp_path.unlink()  # Clean up temp file
                    logger.info("mgz_converted_via_temp_file",
                               input=str(mgz_path), output=str(output_path))
                    return output_path
                except (PermissionError, OSError) as copy_error:
                    # If copy back fails, return temp file path
                    logger.warning("copy_back_failed_using_temp_file",
                                 temp_path=str(temp_path), copy_error=str(copy_error))
                    return temp_path

            except Exception as temp_error:
                logger.error("temp_file_conversion_failed",
                           error=str(temp_error),
                           original_error=str(e))

    except Exception as e:
        logger.error("mgz_conversion_failed", error=str(e))

    return None


def combine_hippocampal_subfields(
    left_path: Path,
    right_path: Path,
    output_path: Path
) -> Path:
    """
    Combine left and right hippocampal subfield segmentations.
    
    Args:
        left_path: Left hemisphere segmentation
        right_path: Right hemisphere segmentation
        output_path: Combined output path
    
    Returns:
        Path to combined segmentation
    """
    try:
        left_img = nib.load(left_path)
        right_img = nib.load(right_path)
        
        left_data = left_img.get_fdata()
        right_data = right_img.get_fdata()
        
        # Combine (right labels offset to avoid overlap)
        combined_data = left_data.copy()
        right_mask = right_data > 0
        # Offset right labels by 1000 to distinguish from left
        combined_data[right_mask] = right_data[right_mask] + 1000
        
        # Create new image
        combined_img = nib.Nifti1Image(combined_data, left_img.affine, left_img.header)
        nib.save(combined_img, output_path)
        
        logger.info("hippocampal_subfields_combined", output=str(output_path))
        return output_path
    
    except Exception as e:
        logger.error("subfield_combination_failed", error=str(e))
        return None


# FreeSurfer/FastSurfer label mappings
ASEG_HIPPOCAMPUS_LABELS = {
    # FreeSurfer DKT Atlas + ASEG labels
    0: "Unknown",
    2: "Left-Cerebral-White-Matter",
    3: "Left-Cerebral-Cortex",
    4: "Left-Lateral-Ventricle",
    5: "Left-Inf-Lat-Vent",
    7: "Left-Cerebellum-White-Matter",
    8: "Left-Cerebellum-Cortex",
    10: "Left-Thalamus",
    11: "Left-Caudate",
    12: "Left-Putamen",
    13: "Left-Pallidum",
    14: "3rd-Ventricle",
    15: "4th-Ventricle",
    16: "Brain-Stem",
    17: "Left-Hippocampus",
    18: "Left-Amygdala",
    24: "CSF",
    26: "Left-Accumbens-area",
    28: "Left-VentralDC",
    30: "Left-vessel",
    31: "Left-choroid-plexus",
    41: "Right-Cerebral-White-Matter",
    42: "Right-Cerebral-Cortex",
    43: "Right-Lateral-Ventricle",
    44: "Right-Inf-Lat-Vent",
    46: "Right-Cerebellum-White-Matter",
    47: "Right-Cerebellum-Cortex",
    49: "Right-Thalamus",
    50: "Right-Caudate",
    51: "Right-Putamen",
    52: "Right-Pallidum",
    53: "Right-Hippocampus",
    54: "Right-Amygdala",
    58: "Right-Accumbens-area",
    60: "Right-VentralDC",
    62: "Right-vessel",
    63: "Right-choroid-plexus",
    77: "WM-hypointensities",
    85: "Optic-Chiasm",
    # DKT cortical labels (left hemisphere)
    1002: "ctx-lh-caudalanteriorcingulate",
    1003: "ctx-lh-caudalmiddlefrontal",
    1005: "ctx-lh-cuneus",
    1006: "ctx-lh-entorhinal",
    1007: "ctx-lh-fusiform",
    1008: "ctx-lh-inferiorparietal",
    1009: "ctx-lh-inferiortemporal",
    1010: "ctx-lh-isthmuscingulate",
    1011: "ctx-lh-lateraloccipital",
    1012: "ctx-lh-lateralorbitofrontal",
    1013: "ctx-lh-lingual",
    1014: "ctx-lh-medialorbitofrontal",
    1015: "ctx-lh-middletemporal",
    1016: "ctx-lh-parahippocampal",
    1017: "ctx-lh-paracentral",
    1018: "ctx-lh-parsopercularis",
    1019: "ctx-lh-parsorbitalis",
    1020: "ctx-lh-parstriangularis",
    1021: "ctx-lh-pericalcarine",
    1022: "ctx-lh-postcentral",
    1023: "ctx-lh-posteriorcingulate",
    1024: "ctx-lh-precentral",
    1025: "ctx-lh-precuneus",
    1026: "ctx-lh-rostralanteriorcingulate",
    1027: "ctx-lh-rostralmiddlefrontal",
    1028: "ctx-lh-superiorfrontal",
    1029: "ctx-lh-superiorparietal",
    1030: "ctx-lh-superiortemporal",
    1031: "ctx-lh-supramarginal",
    1034: "ctx-lh-transversetemporal",
    1035: "ctx-lh-insula",
    # DKT cortical labels (right hemisphere)
    2002: "ctx-rh-caudalanteriorcingulate",
    2003: "ctx-rh-caudalmiddlefrontal",
    2005: "ctx-rh-cuneus",
    2006: "ctx-rh-entorhinal",
    2007: "ctx-rh-fusiform",
    2008: "ctx-rh-inferiorparietal",
    2009: "ctx-rh-inferiortemporal",
    2010: "ctx-rh-isthmuscingulate",
    2011: "ctx-rh-lateraloccipital",
    2012: "ctx-rh-lateralorbitofrontal",
    2013: "ctx-rh-lingual",
    2014: "ctx-rh-medialorbitofrontal",
    2015: "ctx-rh-middletemporal",
    2016: "ctx-rh-parahippocampal",
    2017: "ctx-rh-paracentral",
    2018: "ctx-rh-parsopercularis",
    2019: "ctx-rh-parsorbitalis",
    2020: "ctx-rh-parstriangularis",
    2021: "ctx-rh-pericalcarine",
    2022: "ctx-rh-postcentral",
    2023: "ctx-rh-posteriorcingulate",
    2024: "ctx-rh-precentral",
    2025: "ctx-rh-precuneus",
    2026: "ctx-rh-rostralanteriorcingulate",
    2027: "ctx-rh-rostralmiddlefrontal",
    2028: "ctx-rh-superiorfrontal",
    2029: "ctx-rh-superiorparietal",
    2030: "ctx-rh-superiortemporal",
    2031: "ctx-rh-supramarginal",
    2034: "ctx-rh-transversetemporal",
    2035: "ctx-rh-insula",
}

HIPPOCAMPAL_SUBFIELD_LABELS = {
    # Left hemisphere
    203: "CA1",
    204: "CA3",
    205: "CA4_DG",
    206: "subiculum",
    207: "presubiculum",
    208: "fimbria",
    209: "HATA",
    # Right hemisphere (offset by 1000)
    1203: "CA1_right",
    1204: "CA3_right",
    1205: "CA4_DG_right",
    1206: "subiculum_right",
    1207: "presubiculum_right",
    1208: "fimbria_right",
    1209: "HATA_right",
}

