"""
Report generation API for creating PDF reports with dashboard data and visualizations.

This module provides endpoints for generating comprehensive PDF reports that include
all dashboard content plus coronal visualizations for specified slices.
"""

import io
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

try:
    from PIL import Image as PILImage
    try:
        from PIL import Image as PILImageModule
        # Try to import Resampling (PIL >= 9.1.0) or use ANTIALIAS
        try:
            Resampling = PILImageModule.Resampling
        except AttributeError:
            Resampling = PILImageModule
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
        print("Warning: PIL/Pillow not available. Image combination will not work.")
except ImportError:
    PIL_AVAILABLE = False
    Resampling = None
    print("Warning: PIL/Pillow not available. Image combination will not work.")

from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.logging import get_logger
from backend.models import Job
from backend.models.job import JobStatus
from backend.services import JobService, MetricService

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not available. PDF generation will not work.")

# Note: requests no longer needed for report generation - images read directly from filesystem

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{job_id}/pdf")
async def generate_pdf_report(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Generate a comprehensive PDF report for a completed job.

    Includes:
    - Patient information
    - Processing metadata
    - Hippocampal volume metrics
    - Asymmetry analysis
    - Coronal visualizations with anatomical images and hippocampal overlays
      (slices corresponding to viewer positions 3, 4, 5, 6)

    Args:
        job_id: Job identifier

    Returns:
        PDF file as streaming response
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available. Please install reportlab: pip install reportlab"
        )

    # Note: Images are now read directly from filesystem, no external requests needed

    # Validate job exists and is completed
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job.status}). Reports can only be generated for completed jobs."
        )

    # Get metrics
    metrics = MetricService.get_metrics_by_job(db, job_id)
    if not metrics:
        raise HTTPException(status_code=400, detail="No metrics available for this job")

    try:
        # Generate PDF
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        # Define custom colors matching dashboard theme
        # Custom NeuroInsight blue: #003d7a = RGB(0, 61, 122)
        dashboard_blue = colors.Color(0/255, 61/255, 122/255)

        # Create left-aligned heading style for table titles to match table content
        table_title_style = ParagraphStyle(
            'TableTitle',
            parent=styles['Heading2'],
            alignment=0,  # 0 = LEFT, 1 = CENTER, 2 = RIGHT
        )

        story = []

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=1,  # Center
        )
        story.append(Paragraph("NeuroInsight Hippocampal Analysis Report", title_style))
        story.append(Spacer(1, 12))

        # Report metadata
        metadata_style = ParagraphStyle(
            'Metadata',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=1,
        )
        report_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        story.append(Paragraph(f"Generated: {report_date}", metadata_style))
        story.append(Paragraph(f"Job ID: {job_id}", metadata_style))
        story.append(Spacer(1, 24))

        # Patient Information
        story.append(Paragraph("Patient Information", table_title_style))
        story.append(Spacer(1, 12))

        # Format age/sex similar to UI dashboard
        age_sex = f"{job.patient_age if job.patient_age else 'N/A'} / {job.patient_sex or 'N/A'}"
        
        patient_data = [
            ["Item", "Information"],  # Header row
            ["Patient ID", job.patient_id or job.id],  # Show job ID if patient_id not set
            ["Age / Sex", age_sex],
            ["Scan Date", job.created_at.strftime("%Y-%m-%d") if job.created_at else "N/A"],
            ["Scanner", job.scanner_info or "N/A"],
        ]
        
        # Add Notes row if notes exist and aren't just the default upload message
        if job.notes and job.notes != "Uploaded as nii.gz file." and not job.notes.startswith("Uploaded as"):
            # Clean up notes: remove "| Uploaded as..." suffix
            clean_notes = job.notes.split(" | Uploaded as")[0].strip()
            if clean_notes:  # Only add if there's actual content after cleanup
                patient_data.append(["Notes", clean_notes])

        patient_table = Table(patient_data, colWidths=[2.5*inch, 4.5*inch])
        patient_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), dashboard_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, dashboard_blue),
        ]))
        story.append(patient_table)
        story.append(Spacer(1, 24))

        # Hippocampal Volume
        story.append(Paragraph("Hippocampal Volume", table_title_style))
        story.append(Spacer(1, 12))

        # Calculate totals
        left_total = sum(m.left_volume for m in metrics if hasattr(m, 'left_volume'))
        right_total = sum(m.right_volume for m in metrics if hasattr(m, 'right_volume'))

        volume_data = [
            ["Left Hippocampal Volume", "Right Hippocampal Volume"],
            [f"{left_total:.2f} mm³", f"{right_total:.2f} mm³"],
        ]

        volume_table = Table(volume_data, colWidths=[3.5*inch, 3.5*inch])
        volume_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), dashboard_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, dashboard_blue),
        ]))
        story.append(volume_table)
        story.append(Spacer(1, 24))

        # Interpretation
        story.append(Paragraph("Interpretation", table_title_style))
        story.append(Spacer(1, 12))

        # Calculate asymmetry index and laterization
        asymmetry_index = ((left_total - right_total) / (left_total + right_total)) if (left_total + right_total) > 0 else 0

        # Determine laterization based on HS thresholds (same as dashboard)
        LEFT_HS_THRESHOLD = -0.070839747728063
        RIGHT_HS_THRESHOLD = 0.046915816971433

        ai_decimal = asymmetry_index  # No conversion needed
        if ai_decimal > RIGHT_HS_THRESHOLD:
            classification = 'Left-dominant (Right HS suspected)'
        elif ai_decimal < LEFT_HS_THRESHOLD:
            classification = 'Right-dominant (Left HS suspected)'
        else:
            classification = 'Balanced (No HS)'

        # Add threshold information as bullet points
        thresholds_info = f"""Thresholds:

• Left HS (Right-dominant) if AI < {LEFT_HS_THRESHOLD:.12f}
• Right HS (Left-dominant) if AI > {RIGHT_HS_THRESHOLD:.12f}
• No HS (Balanced) otherwise."""

        laterization = f"{classification}\n\n{thresholds_info}"

        # Create a properly formatted paragraph for the laterization cell
        laterization_paragraph = Paragraph(laterization.replace('\n', '<br/>'), styles['Normal'])

        interpretation_data = [
            ["Asymmetry Index", "Laterization"],
            [f"{asymmetry_index:.3f}\n\nFormula: (L-R)/(L+R)", laterization_paragraph],
        ]

        interpretation_table = Table(interpretation_data, colWidths=[3.5*inch, 3.5*inch])
        interpretation_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), dashboard_blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('VALIGN', (0, 1), (-1, 1), 'TOP'),
            ('ALIGN', (1, 1), (1, 1), 'LEFT'),  # Left-align the laterization column
            ('GRID', (0, 0), (-1, -1), 1, dashboard_blue),
        ]))
        story.append(interpretation_table)
        story.append(Spacer(1, 24))

        # Coronal Visualizations Section
        story.append(Paragraph("Coronal Visualizations", styles['Heading2']))
        story.append(Spacer(1, 12))

        viz_note = Paragraph(
            "The following images show coronal slices with anatomical T1-weighted background and hippocampal segmentation overlays "
            "(30% opacity) combined. Images are rotated 180 degrees for optimal report viewing. Slices 3, 4, 5, and 6 are displayed "
            "in a 2x2 grid to provide comprehensive visualization of the hippocampal regions.",
            styles['Normal']
        )
        story.append(viz_note)
        story.append(Spacer(1, 6))

        # Orientation and color legend for report
        orientation_style = ParagraphStyle(
            'OrientationLegend',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#333333'),
            alignment=0,
            leftIndent=0,
            rightIndent=0,
        )
        orientation_legend = Paragraph(
            "<b>L/R markers</b> indicate patient orientation (radiological view): left side of image = patient's left, right side = patient's right. "
            "<b>Color coding:</b> Blue = left hippocampus, Red = right hippocampus.",
            orientation_style
        )
        story.append(orientation_legend)
        story.append(Spacer(1, 12))

        # Add coronal visualizations for slices 3, 4, 5, 6 in 2x2 grid
        # Use viewer positions 3, 4, 5, 6 which correspond to file indices 3, 4, 5, 6
        # Use the same slices that viewer shows (positions 3,4,5,6)
        coronal_slices = [3, 4, 5, 6]  # Viewer positions we want to show

        # Composite anatomical + overlay images with 15% opacity for hippocampus
        from pathlib import Path
        import numpy as np

        # Collect images for 2x2 grid
        images_data = []
        logger.info(f"Creating anatomical + overlay composites for coronal slices: {coronal_slices}")

        # Paths to existing images - use job's result_path from database
        base_viz_path = Path(job.result_path) / "visualizations" / "overlays" / "coronal"

        for slice_idx in coronal_slices:
            try:
                slice_id = f"slice_{slice_idx:02d}"

                # Load anatomical image
                anatomical_filename = f"anatomical_{slice_id}.png"
                anatomical_path = base_viz_path / anatomical_filename

                # Load overlay image (hippocampus segmentation)
                overlay_filename = f"hippocampus_overlay_{slice_id}.png"
                overlay_path = base_viz_path / overlay_filename

                if anatomical_path.exists() and overlay_path.exists():
                    # Load both images
                    anatomical_img = PILImage.open(anatomical_path)
                    overlay_img = PILImage.open(overlay_path)

                    logger.info(f"Loaded anatomical + overlay for slice {slice_idx}: anatomical {anatomical_img.size}, overlay {overlay_img.mode}")

                    # Ensure both images are in RGBA mode for compositing
                    if anatomical_img.mode != 'RGBA':
                        anatomical_img = anatomical_img.convert('RGBA')
                    if overlay_img.mode != 'RGBA':
                        overlay_img = overlay_img.convert('RGBA')

                    # Ensure same dimensions - resize anatomical to match overlay (higher resolution)
                    if anatomical_img.size != overlay_img.size:
                        logger.warning(f"Dimension mismatch for slice {slice_idx}: anatomical {anatomical_img.size}, overlay {overlay_img.size}")
                        # Resize anatomical to match overlay (overlay has hippocampus segmentation at correct resolution)
                        anatomical_img = anatomical_img.resize(overlay_img.size, PILImage.LANCZOS)

                    # Composite with 15% opacity for hippocampus overlays
                    # Convert to numpy arrays for pixel-level control
                    anatomical_array = np.array(anatomical_img)
                    overlay_array = np.array(overlay_img)

                    # Apply 180-degree rotation to coronal slices for report display
                    anatomical_img = anatomical_img.rotate(180)
                    overlay_img = overlay_img.rotate(180)
                    logger.info(f"Applied 180-degree rotation to coronal slice {slice_idx} for report")

                    # Convert back to arrays after rotation
                    anatomical_array = np.array(anatomical_img)
                    overlay_array = np.array(overlay_img)

                    logger.info(f"After rotation - anatomical shape: {anatomical_array.shape}, overlay shape: {overlay_array.shape}")
                    logger.info(f"Anatomical alpha range: {anatomical_array[:,:,3].min()}-{anatomical_array[:,:,3].max()}")
                    logger.info(f"Overlay alpha range: {overlay_array[:,:,3].min()}-{overlay_array[:,:,3].max()}")

                    # Apply 30% opacity to overlay pixels (where alpha > 0)
                    # This provides clear hippocampal visualization in reports
                    opacity = 0.30

                    # Create composite: anatomical + (overlay * opacity)
                    composite_array = anatomical_array.copy()

                    # Where overlay has content (alpha > 0), blend with anatomical
                    overlay_mask = overlay_array[:, :, 3] > 0  # Non-transparent overlay pixels
                    overlay_pixels = np.sum(overlay_mask)

                    logger.info(f"Compositing {overlay_pixels} overlay pixels with {opacity*100}% opacity")

                    # Blend overlay with anatomical using 30% opacity
                    composite_array[overlay_mask] = (
                        opacity * overlay_array[overlay_mask] +
                        (1 - opacity) * anatomical_array[overlay_mask]
                    ).astype(np.uint8)

                    logger.info(f"After compositing - composite alpha range: {composite_array[:,:,3].min()}-{composite_array[:,:,3].max()}")

                    # Convert back to PIL Image
                    composite_img = PILImage.fromarray(composite_array, 'RGBA')

                    # Convert to RGB for PDF
                    if composite_img.mode != 'RGB':
                        composite_img = composite_img.convert('RGB')

                    # Convert to ReportLab Image
                    composite_buffer = io.BytesIO()
                    composite_img.save(composite_buffer, format='PNG')
                    buffer_size = composite_buffer.tell()
                    composite_buffer.seek(0)

                    logger.info(f"Created composite for slice {slice_idx}: {buffer_size} bytes")

                    # Calculate aspect ratio and fit to table cell while maintaining proportions
                    img_width, img_height = composite_img.size
                    cell_width = 3.0*inch  # Fit within table cell
                    cell_height = 2.2*inch

                    # Calculate scaling to fit
                    width_ratio = cell_width / img_width
                    height_ratio = cell_height / img_height
                    scale = min(width_ratio, height_ratio)

                    display_width = img_width * scale
                    display_height = img_height * scale

                    logger.info(f"Image scaling: original {img_width}x{img_height}, display {display_width:.1f}x{display_height:.1f} points")

                    img = Image(composite_buffer, width=display_width, height=display_height)
                    logger.info(f"Created ReportLab Image for slice {slice_idx}")

                    # Add title above image (slice_idx is the file index, display as viewer position)
                    display_slice_num = slice_idx + 3  # File 3→Viewer pos 3, File 4→Viewer pos 4, etc.
                    title_para = Paragraph(f"Slice {display_slice_num}<br/><font size=8>(Coronal View)</font>",
                                         ParagraphStyle('SliceTitle',
                                                       parent=styles['Normal'],
                                                       fontSize=10,
                                                       alignment=1,
                                                       spaceAfter=6))
                    images_data.append([title_para, img])

                else:
                    logger.error(f"Images not found for slice {slice_idx}: anatomical={anatomical_path.exists()}, overlay={overlay_path.exists()}")
                    # Add placeholder for missing images
                    display_slice_num = slice_idx + 3
                    placeholder = Paragraph(f"Slice {display_slice_num}<br/>Images not found",
                                          ParagraphStyle('Placeholder',
                                                        parent=styles['Normal'],
                                                        fontSize=9,
                                                        alignment=1,
                                                        textColor=colors.gray))
                    images_data.append([Paragraph(f"Slice {display_slice_num}", ParagraphStyle('SliceTitle', parent=styles['Normal'], fontSize=10, alignment=1, spaceAfter=6)), placeholder])

            except Exception as e:
                logger.error(f"Error creating composite for slice {slice_idx}: {e}")
                # Add error placeholder
                display_slice_num = slice_idx + 3
                error_placeholder = Paragraph(f"Slice {display_slice_num}<br/>Error creating composite",
                                             ParagraphStyle('ErrorPlaceholder',
                                                           parent=styles['Normal'],
                                                           fontSize=9,
                                                           alignment=1,
                                                           textColor=colors.gray))
                images_data.append([Paragraph(f"Slice {display_slice_num}", ParagraphStyle('SliceTitle', parent=styles['Normal'], fontSize=10, alignment=1, spaceAfter=6)), error_placeholder])

            except Exception as e:
                logger.error(f"Error adding coronal slice {slice_idx}: {e}")
                # Add error placeholder
                display_slice_num = slice_idx + 3
                error_placeholder = Paragraph(f"Slice {display_slice_num}<br/>Error loading",
                                            ParagraphStyle('ErrorPlaceholder',
                                                          parent=styles['Normal'],
                                                          fontSize=9,
                                                          alignment=1,
                                                          textColor=colors.red))
                images_data.append([Paragraph(f"Slice {display_slice_num}", ParagraphStyle('SliceTitle', parent=styles['Normal'], fontSize=10, alignment=1, spaceAfter=6)), error_placeholder])

        logger.info(f"Collected {len(images_data)} image entries for PDF")

        # Create 2x2 grid table
        if images_data:
            # L/R orientation row (patient left/right, radiological view)
            l_style = ParagraphStyle('Llabel', parent=styles['Normal'], fontSize=10, alignment=0, textColor=colors.HexColor('#003d7a'))
            r_style = ParagraphStyle('Rlabel', parent=styles['Normal'], fontSize=10, alignment=2, textColor=colors.HexColor('#003d7a'))
            lr_row = Table(
                [[Paragraph("<b>L</b>", l_style), Paragraph("<b>R</b>", r_style)]],
                colWidths=[3.5*inch, 3.5*inch], rowHeights=[0.2*inch]
            )
            lr_row.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(lr_row)
            story.append(Spacer(1, 4))

            # Arrange as 2x2 grid: [3, 4] in first row, [5, 6] in second row
            # images_data[0] = slice 3, images_data[1] = slice 4, etc.
            grid_data = [
                [images_data[0][1], images_data[1][1]],  # Row 1: slices 3, 4
                [images_data[2][1], images_data[3][1]]   # Row 2: slices 5, 6
            ]

            # Create table with proper spacing
            img_table = Table(grid_data, colWidths=[3.5*inch, 3.5*inch], rowHeights=[2.5*inch, 2.5*inch])
            img_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))

            story.append(img_table)
            story.append(Spacer(1, 12))

            # Add caption for the entire grid
            grid_caption = Paragraph(
                "Figure: Coronal slices 3, 4 (top row) and 5, 6 (bottom row) showing T1-weighted anatomical images with hippocampal segmentation overlays at 30% opacity (rotated 180 degrees for optimal viewing).",
                ParagraphStyle('GridCaption', parent=styles['Normal'], fontSize=9, textColor=colors.gray, alignment=1)
            )
            story.append(grid_caption)
            story.append(Spacer(1, 18))

        # Build PDF
        doc.build(story)

        # Return PDF as downloadable file
        pdf_buffer.seek(0)
        filename = f"neuroinsight_report_{job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_buffer.getvalue()),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"PDF generation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF report: {str(e)}"
        )
