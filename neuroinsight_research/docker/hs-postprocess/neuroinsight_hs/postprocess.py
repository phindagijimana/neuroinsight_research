"""HS Detection Postprocessor.

Reads FreeSurfer volumetric outputs, computes hippocampal asymmetry index,
classifies lateralization, generates QC overlays, PDF report, and Niivue
viewer manifest.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np


def parse_aseg_stats(stats_path: str) -> dict:
    """Parse FreeSurfer aseg.stats file and return {label_id: volume_mm3}."""
    volumes = {}
    with open(stats_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    label_id = int(parts[1])
                    vol_mm3 = float(parts[3])
                    volumes[label_id] = vol_mm3
                except (ValueError, IndexError):
                    continue
    return volumes


def compute_asymmetry_index(left_vol: float, right_vol: float) -> float:
    """Compute AI = (L - R) / (L + R)."""
    total = left_vol + right_vol
    if total == 0:
        return 0.0
    return (left_vol - right_vol) / total


def classify_hs(ai: float, left_th: float, right_th: float) -> str:
    """Classify HS based on asymmetry index and thresholds."""
    if ai < left_th:
        return "Left HS (Right-dominant)"
    elif ai > right_th:
        return "Right HS (Left-dominant)"
    else:
        return "No HS (Balanced)"


def _select_slices_evenly(slice_counts, left_label_counts, right_label_counts,
                          thresh_frac=0.05, n_slices=10):
    """Method A: evenly space n_slices across the hippocampal extent.

    Finds where hippocampus starts/ends (>5 % of peak) and samples uniformly.
    Falls back to top-N by count (Method B) if extent is too narrow.
    """
    max_count = slice_counts.max()
    if max_count == 0:
        return np.array([], dtype=int)

    threshold = thresh_frac * max_count
    above = np.where(slice_counts > threshold)[0]
    if len(above) == 0:
        return np.array([], dtype=int)

    hippo_start = above[0]
    hippo_end = above[-1]
    hippo_range = hippo_end - hippo_start

    if hippo_range >= n_slices:
        indices = []
        for i in range(n_slices):
            frac = i / (n_slices - 1)
            idx = int(round(hippo_start + frac * hippo_range))
            indices.append(idx)
        return np.array(indices, dtype=int)

    sorted_slices = above[np.argsort(slice_counts[above])[::-1]]
    selected = np.sort(sorted_slices[:n_slices])
    return selected


def generate_qc_images(
    brain_path: str,
    aseg_path: str,
    subject_id: str,
    output_dir: str,
    left_label: int,
    right_label: int,
    orientation: str = "coronal",
    slice_axis: int = 2,
    top_n: int = 10,
    thresh_frac: float = 0.05,
    overlay_opacity: float = 0.55,
):
    """Generate separate anatomical and overlay PNGs for each QC slice.

    Slice selection uses Method A (evenly spaced across hippocampal extent)
    with Method B fallback (top-N by voxel count).  For coronal views L/R
    anatomical markers are added.  Orientation transforms handle FreeSurfer
    conformed (LIA) space.

    In LIA space, axis 2 (A-P) must be used for true coronal slicing.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy import ndimage

    LEFT_COLOR_U8 = np.array([79, 228, 196], dtype=np.uint8)   # #4ECDC4
    RIGHT_COLOR_U8 = np.array([255, 107, 107], dtype=np.uint8) # #FF6B6B
    CONTOUR_WIDTH = 2
    FILL_ALPHA = 180
    CONTOUR_ALPHA = 255

    try:
        brain_img = nib.load(brain_path)
        aseg_img = nib.load(aseg_path)
    except Exception as e:
        print(f"WARNING: Could not load images for QC: {e}", file=sys.stderr)
        return []

    brain_data = brain_img.get_fdata()
    aseg_data = aseg_img.get_fdata()

    orient_codes = nib.orientations.aff2axcodes(brain_img.affine)
    is_lia = orient_codes == ('L', 'I', 'A')
    print(f"Volume orientation: {''.join(orient_codes)}")

    other_axes = tuple(i for i in range(3) if i != slice_axis)
    hippo_mask = np.isin(aseg_data, [left_label, right_label])
    slice_counts = hippo_mask.sum(axis=other_axes)

    left_mask_3d = (aseg_data == left_label)
    right_mask_3d = (aseg_data == right_label)
    left_counts = left_mask_3d.sum(axis=other_axes)
    right_counts = right_mask_3d.sum(axis=other_axes)

    selected = _select_slices_evenly(
        slice_counts, left_counts, right_counts,
        thresh_frac=thresh_frac, n_slices=top_n,
    )

    if len(selected) == 0:
        print("WARNING: No hippocampal slices found for QC", file=sys.stderr)
        return []

    print(f"Selected {len(selected)} slices (Method A evenly-spaced): "
          f"{selected[0]}-{selected[-1]}")

    output_paths = []
    os.makedirs(output_dir, exist_ok=True)

    for idx, sl in enumerate(selected):
        slicing = [slice(None)] * 3
        slicing[slice_axis] = sl
        brain_slice = brain_data[tuple(slicing)]
        aseg_slice = aseg_data[tuple(slicing)]

        if orientation == "coronal" and np.all(is_lia):
            # LIA axis-2 slice: rows=R→L, cols=S→I
            # .T  → rows=S→I (superior at top), cols=R→L
            # fliplr → cols=L→R (neurological convention: L on left)
            brain_slice = np.fliplr(brain_slice.T)
            aseg_slice = np.fliplr(aseg_slice.T)
        elif orientation == "coronal":
            brain_slice = brain_slice.T
            aseg_slice = aseg_slice.T
        elif orientation == "axial":
            brain_slice = brain_slice.T
            aseg_slice = aseg_slice.T
        else:
            brain_slice = brain_slice.T
            aseg_slice = aseg_slice.T

        # --- Anatomical PNG ---
        fig, ax = plt.subplots(1, 1, figsize=(8, 8), facecolor="black")
        ax.imshow(brain_slice, cmap="gray", aspect="equal", origin="upper")
        ax.set_title(f"{subject_id} | {orientation} slice {sl}",
                     color="white", fontsize=11, pad=8)
        ax.axis("off")

        if orientation == "coronal":
            h_img, w_img = brain_slice.shape
            ax.text(w_img * 0.02, h_img * 0.97, "L",
                    color="white", fontsize=14, fontweight="bold",
                    ha="left", va="bottom")
            ax.text(w_img * 0.98, h_img * 0.97, "R",
                    color="white", fontsize=14, fontweight="bold",
                    ha="right", va="bottom")

        anat_path = os.path.join(
            output_dir, f"anatomical_slice_{idx:02d}.png")
        fig.savefig(anat_path, bbox_inches="tight", dpi=150, facecolor="black")
        plt.close(fig)

        # --- Overlay PNG (RGBA, transparent background) ---
        h, w = aseg_slice.shape
        overlay_rgba = np.zeros((h, w, 4), dtype=np.uint8)

        left_mask = (aseg_slice == left_label)
        right_mask = (aseg_slice == right_label)

        for mask, color_u8 in [(left_mask, LEFT_COLOR_U8),
                                (right_mask, RIGHT_COLOR_U8)]:
            if not mask.any():
                continue
            overlay_rgba[mask, :3] = color_u8
            overlay_rgba[mask, 3] = FILL_ALPHA
            eroded = ndimage.binary_erosion(mask, iterations=CONTOUR_WIDTH)
            contour = mask & ~eroded
            overlay_rgba[contour, :3] = color_u8
            overlay_rgba[contour, 3] = CONTOUR_ALPHA

        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        fig.patch.set_alpha(0.0)
        ax.imshow(overlay_rgba, aspect="equal", origin="upper")
        ax.axis("off")

        overlay_path = os.path.join(
            output_dir, f"hippocampus_overlay_slice_{idx:02d}.png")
        fig.savefig(overlay_path, bbox_inches="tight", dpi=150,
                    transparent=True)
        plt.close(fig)

        output_paths.append((anat_path, overlay_path))

    return output_paths


def _draw_table(ax, headers, rows, col_widths, y_start, row_height,
                header_color="#1B3A5C", border_color="#1B3A5C"):
    """Draw a styled table with navy header on an axes (in figure coords)."""
    import matplotlib.pyplot as plt
    fig = ax.figure
    x_left = 0.08
    total_w = sum(col_widths)

    # Header row
    x = x_left
    for ci, (hdr, cw) in enumerate(zip(headers, col_widths)):
        rect = plt.Rectangle((x, y_start), cw, row_height,
                              transform=fig.transFigure, clip_on=False,
                              facecolor=header_color, edgecolor=border_color,
                              linewidth=0.8)
        fig.patches.append(rect)
        fig.text(x + cw / 2, y_start + row_height / 2, hdr,
                 ha="center", va="center", fontsize=10,
                 fontweight="bold", color="white",
                 transform=fig.transFigure)
        x += cw

    # Data rows
    for ri, row_data in enumerate(rows):
        y = y_start - (ri + 1) * row_height
        x = x_left
        for ci, (cell, cw) in enumerate(zip(row_data, col_widths)):
            rect = plt.Rectangle((x, y), cw, row_height,
                                  transform=fig.transFigure, clip_on=False,
                                  facecolor="white", edgecolor=border_color,
                                  linewidth=0.5)
            fig.patches.append(rect)
            if isinstance(cell, tuple):
                txt, props = cell
            else:
                txt, props = cell, {}
            fig.text(x + cw / 2, y + row_height / 2, txt,
                     ha=props.get("ha", "center"),
                     va="center", fontsize=props.get("fontsize", 10),
                     color=props.get("color", "black"),
                     fontweight=props.get("fontweight", "normal"),
                     transform=fig.transFigure)
            x += cw


def generate_report_pdf(
    brain_path: str,
    aseg_path: str,
    subject_id: str,
    metrics: dict,
    output_path: str,
    left_label: int,
    right_label: int,
    orientation: str = "coronal",
    slice_axis: int = 2,
    n_slices: int = 10,
    thresh_frac: float = 0.05,
    overlay_opacity: float = 0.55,
    report_pick: list = None,
    title: str = "NeuroInsight Hippocampal Analysis\nReport",
):
    """Generate a clinical-style PDF report matching the NeuroInsight design.

    Page 1: Title, generated date, job ID, hippocampal volumes table,
            interpretation table with AI, lateralization, and thresholds.
    Page 2: Coronal visualizations heading, description text, 2x2 image
            grid of selected slices, and figure caption.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from scipy import ndimage
    from datetime import datetime, timezone

    LEFT_COLOR = np.array([0.31, 0.89, 0.77])
    RIGHT_COLOR = np.array([1.0, 0.42, 0.42])
    CONTOUR_WIDTH = 2
    NAVY = "#1B3A5C"

    if report_pick is None:
        report_pick = [3, 4, 5, 6]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # output_path = .../job_id/bundle/reports/hs_report.pdf → 3 levels up
    job_id = os.path.basename(
        os.path.dirname(os.path.dirname(os.path.dirname(output_path)))
    )
    if len(job_id) > 8:
        job_id_short = job_id[:8]
    else:
        job_id_short = job_id
    generated_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    try:
        brain_img = nib.load(brain_path)
        aseg_img = nib.load(aseg_path)
        brain_data = brain_img.get_fdata()
        aseg_data = aseg_img.get_fdata()
        has_images = True
    except Exception as e:
        print(f"WARNING: Could not load images for report: {e}", file=sys.stderr)
        has_images = False

    with PdfPages(output_path) as pdf:
        # ── PAGE 1: Metrics ──
        fig = plt.figure(figsize=(8.5, 11), facecolor="white")
        ax_bg = fig.add_axes([0, 0, 1, 1])
        ax_bg.set_xlim(0, 1)
        ax_bg.set_ylim(0, 1)
        ax_bg.axis("off")

        fig.text(0.5, 0.92, title,
                 ha="center", va="center", fontsize=22, fontweight="bold",
                 color="black", linespacing=1.3)
        fig.text(0.5, 0.86, f"Generated: {generated_ts}",
                 ha="center", va="center", fontsize=10, color="gray")
        fig.text(0.5, 0.845, f"Job ID: {job_id_short}",
                 ha="center", va="center", fontsize=10, color="gray")

        # Hippocampal Volume table
        fig.text(0.08, 0.79, "Hippocampal Volume",
                 ha="left", va="center", fontsize=14, fontweight="bold",
                 color="black")

        left_vol = metrics["volumes_mm3"]["left"]
        right_vol = metrics["volumes_mm3"]["right"]
        col_w = [0.42, 0.42]
        _draw_table(ax_bg, ["Left Hippocampal Volume", "Right Hippocampal Volume"],
                    [[f"{left_vol:.2f} mm\u00B3", f"{right_vol:.2f} mm\u00B3"]],
                    col_w, y_start=0.74, row_height=0.035)

        # Interpretation table
        fig.text(0.08, 0.63, "Interpretation",
                 ha="left", va="center", fontsize=14, fontweight="bold",
                 color="black")

        ai_val = metrics["asymmetry_index"]
        classification = metrics["classification"]
        left_th = metrics["thresholds"]["left_hs"]
        right_th = metrics["thresholds"]["right_hs"]

        _draw_table(ax_bg, ["Asymmetry Index", "Lateralization"],
                    [],
                    col_w, y_start=0.58, row_height=0.035)

        # AI + Lateralization data cells (multi-line, custom layout)
        rh = 0.035
        y_data = 0.58 - rh
        cell_h = rh * 4
        x_left = 0.08

        for ci, cw in enumerate(col_w):
            x = x_left + sum(col_w[:ci])
            rect = plt.Rectangle((x, y_data - cell_h + rh), cw, cell_h,
                                  transform=fig.transFigure, clip_on=False,
                                  facecolor="white", edgecolor=NAVY,
                                  linewidth=0.5)
            fig.patches.append(rect)

        # Left column: AI value + formula
        fig.text(x_left + col_w[0] / 2, y_data - 0.01,
                 f"{ai_val:.6f}", ha="center", va="center",
                 fontsize=11, color="black")
        fig.text(x_left + col_w[0] / 2, y_data - 0.06,
                 "Formula: (L\u2212R)/(L+R)", ha="center", va="center",
                 fontsize=9, color="gray")

        # Right column: classification + thresholds
        x_right = x_left + col_w[0]
        fig.text(x_right + col_w[1] / 2, y_data - 0.005,
                 classification, ha="center", va="center",
                 fontsize=11,
                 color="red" if "HS" in classification and "No" not in classification else "black")
        fig.text(x_right + col_w[1] / 2, y_data - 0.035,
                 "Thresholds:", ha="center", va="center",
                 fontsize=9, color="black")
        fig.text(x_right + col_w[1] / 2, y_data - 0.06,
                 f"\u2022 Left HS (Right-dominant) if AI < {left_th:.12f}",
                 ha="center", va="center", fontsize=7, color="black")
        fig.text(x_right + col_w[1] / 2, y_data - 0.08,
                 f"\u2022 Right HS (Left-dominant) if AI > {right_th:.12f}",
                 ha="center", va="center", fontsize=7, color="black")
        fig.text(x_right + col_w[1] / 2, y_data - 0.10,
                 "\u2022 No HS (Balanced) otherwise.",
                 ha="center", va="center", fontsize=7, color="black")

        # Page number
        fig.text(0.5, 0.02, "-- 1 of 2 --",
                 ha="center", va="center", fontsize=8, color="gray")

        pdf.savefig(fig, facecolor="white")
        plt.close(fig)

        if not has_images:
            return

        # ── PAGE 2: Coronal Visualizations ──
        orient_codes = nib.orientations.aff2axcodes(brain_img.affine)
        is_lia = orient_codes == ('L', 'I', 'A')

        other_axes = tuple(i for i in range(3) if i != slice_axis)
        hippo_mask = np.isin(aseg_data, [left_label, right_label])
        slice_counts = hippo_mask.sum(axis=other_axes)
        left_mask_3d = (aseg_data == left_label)
        right_mask_3d = (aseg_data == right_label)
        left_counts = left_mask_3d.sum(axis=other_axes)
        right_counts = right_mask_3d.sum(axis=other_axes)

        all_selected = _select_slices_evenly(
            slice_counts, left_counts, right_counts,
            thresh_frac=thresh_frac, n_slices=n_slices,
        )
        if len(all_selected) == 0:
            print("WARNING: No hippocampal slices for report", file=sys.stderr)
            return

        report_slices = []
        for idx_1based in report_pick:
            idx_0based = idx_1based - 1
            if 0 <= idx_0based < len(all_selected):
                report_slices.append(all_selected[idx_0based])
        if not report_slices:
            report_slices = all_selected[:4].tolist()

        print(f"Report: picked slices {report_pick} \u2192 volume indices {report_slices}")

        pick_str = ", ".join(str(p) for p in report_pick)

        fig = plt.figure(figsize=(8.5, 11), facecolor="white")

        fig.text(0.08, 0.94, "Coronal Visualizations",
                 ha="left", va="center", fontsize=16, fontweight="bold",
                 color=NAVY)

        desc = (
            f"The following images show coronal slices with anatomical "
            f"T1-weighted background and\nhippocampal segmentation overlays "
            f"({int(overlay_opacity * 100)}% opacity) combined. "
            f"Slices {pick_str} are displayed in a\n"
            f"2\u00D72 grid to provide comprehensive visualization of "
            f"the hippocampal regions."
        )
        fig.text(0.08, 0.895, desc,
                 ha="left", va="center", fontsize=9, color="black",
                 linespacing=1.5)

        # 2x2 grid of images
        img_margin_x = 0.10
        img_margin_top = 0.15
        img_gap_x = 0.04
        img_gap_y = 0.04
        img_w = (1.0 - 2 * img_margin_x - img_gap_x) / 2
        img_h = 0.32

        positions = [
            (img_margin_x, 1.0 - img_margin_top - img_h),
            (img_margin_x + img_w + img_gap_x, 1.0 - img_margin_top - img_h),
            (img_margin_x, 1.0 - img_margin_top - 2 * img_h - img_gap_y),
            (img_margin_x + img_w + img_gap_x, 1.0 - img_margin_top - 2 * img_h - img_gap_y),
        ]

        for i, sl in enumerate(report_slices):
            if i >= 4:
                break
            px, py = positions[i]
            ax = fig.add_axes([px, py, img_w, img_h])
            ax.set_facecolor("black")

            slicing = [slice(None)] * 3
            slicing[slice_axis] = sl
            brain_slice = brain_data[tuple(slicing)]
            aseg_slice = aseg_data[tuple(slicing)]

            if orientation == "coronal" and np.all(is_lia):
                brain_slice = np.fliplr(brain_slice.T)
                aseg_slice = np.fliplr(aseg_slice.T)
            else:
                brain_slice = brain_slice.T
                aseg_slice = aseg_slice.T

            brain_norm = brain_slice.astype(float)
            bmax = brain_norm.max()
            if bmax > 0:
                brain_norm /= bmax

            rgb = np.stack([brain_norm] * 3, axis=-1)

            l_mask = (aseg_slice == left_label)
            r_mask = (aseg_slice == right_label)

            for mask, color in [(l_mask, LEFT_COLOR), (r_mask, RIGHT_COLOR)]:
                if not mask.any():
                    continue
                for c in range(3):
                    rgb[:, :, c] = np.where(
                        mask,
                        rgb[:, :, c] * (1 - overlay_opacity) + color[c] * overlay_opacity,
                        rgb[:, :, c],
                    )
                eroded = ndimage.binary_erosion(mask, iterations=CONTOUR_WIDTH)
                contour = mask & ~eroded
                for c in range(3):
                    rgb[:, :, c] = np.where(contour, color[c], rgb[:, :, c])

            rgb = np.clip(rgb, 0, 1)
            ax.imshow(rgb, aspect="equal", origin="upper")
            ax.axis("off")

            if orientation == "coronal":
                h_img, w_img = brain_slice.shape
                ax.text(w_img * 0.02, h_img * 0.97, "L",
                        color="white", fontsize=12, fontweight="bold",
                        ha="left", va="bottom")
                ax.text(w_img * 0.98, h_img * 0.97, "R",
                        color="white", fontsize=12, fontweight="bold",
                        ha="right", va="bottom")

        # Figure caption
        cap_picks = report_pick[:len(report_slices)]
        top_str = ", ".join(str(p) for p in cap_picks[:2])
        bot_str = ", ".join(str(p) for p in cap_picks[2:])
        caption = (
            f"Figure: Coronal slices {top_str} (top row) and "
            f"{bot_str} (bottom row) showing T1-weighted anatomical images "
            f"with\nhippocampal segmentation overlays at "
            f"{int(overlay_opacity * 100)}% opacity."
        )
        fig.text(0.5, 0.08, caption,
                 ha="center", va="center", fontsize=8, color="gray",
                 linespacing=1.4)

        fig.text(0.5, 0.02, "-- 2 of 2 --",
                 ha="center", va="center", fontsize=8, color="gray")

        pdf.savefig(fig, facecolor="white")
        plt.close(fig)


def generate_niivue_manifest(
    subject_id: str,
    bundle_root: str,
    overlay_opacity: float = 0.35,
    orientation: str = "coronal",
    report_slices: list = None,
):
    """Generate Niivue viewer manifest JSON."""
    if report_slices is None:
        report_slices = [3, 4, 5, 6]

    manifest = {
        "viewer_type": "niivue",
        "subject_id": subject_id,
        "volumes": [
            {
                "id": "t1w",
                "role": "underlay",
                "path": f"volumes/{subject_id}/T1.nii.gz",
                "is_label": False,
                "opacity": 1.0,
                "label_map": None,
            },
            {
                "id": "hippo_labels",
                "role": "overlay",
                "path": f"labels/{subject_id}/hippo_labels.nii.gz",
                "is_label": True,
                "opacity": overlay_opacity,
                "label_map": {
                    "17": {"name": "Left-Hippocampus", "color": "#FF6B6B"},
                    "53": {"name": "Right-Hippocampus", "color": "#4ECDC4"},
                },
            },
        ],
        "defaults": {
            "orientation": orientation,
            "overlay_opacity": overlay_opacity,
            "report_slices": report_slices,
        },
        "qc_sets": [
            {
                "id": "hs_qc",
                "label": "Hippocampal QC Overlays",
                "path": "qc/hs/",
            }
        ],
    }

    viewer_dir = os.path.join(bundle_root, "viewer")
    os.makedirs(viewer_dir, exist_ok=True)
    out_path = os.path.join(viewer_dir, "niivue_viewer.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return out_path


def convert_volumes_for_bundle(
    subjects_dir: str,
    subject_id: str,
    bundle_root: str,
    left_label: int,
    right_label: int,
):
    """Convert FreeSurfer volumes to NIfTI and create hippocampal label volume."""
    brain_mgz = os.path.join(subjects_dir, subject_id, "mri", "brain.mgz")
    aseg_mgz = os.path.join(subjects_dir, subject_id, "mri", "aseg.auto.mgz")

    vol_dir = os.path.join(bundle_root, "volumes", subject_id)
    label_dir = os.path.join(bundle_root, "labels", subject_id)
    os.makedirs(vol_dir, exist_ok=True)
    os.makedirs(label_dir, exist_ok=True)

    t1_out = os.path.join(vol_dir, "T1.nii.gz")
    hippo_out = os.path.join(label_dir, "hippo_labels.nii.gz")

    if os.path.exists(brain_mgz):
        try:
            img = nib.load(brain_mgz)
            nib.save(nib.Nifti1Image(img.get_fdata(), img.affine, img.header), t1_out)
            print(f"Converted brain.mgz -> {t1_out}")
        except Exception as e:
            print(f"WARNING: Failed to convert brain.mgz: {e}", file=sys.stderr)
    else:
        print(f"WARNING: brain.mgz not found at {brain_mgz}", file=sys.stderr)

    if os.path.exists(aseg_mgz):
        try:
            aseg_img = nib.load(aseg_mgz)
            aseg_data = np.asarray(aseg_img.get_fdata(), dtype=np.int16)
            hippo_data = np.zeros_like(aseg_data)
            hippo_data[aseg_data == left_label] = left_label
            hippo_data[aseg_data == right_label] = right_label
            nib.save(nib.Nifti1Image(hippo_data, aseg_img.affine, aseg_img.header), hippo_out)
            print(f"Extracted hippocampal labels -> {hippo_out}")
        except Exception as e:
            print(f"WARNING: Failed to extract hippo labels: {e}", file=sys.stderr)
    else:
        print(f"WARNING: aseg.auto.mgz not found at {aseg_mgz}", file=sys.stderr)

    return t1_out, hippo_out


def main():
    parser = argparse.ArgumentParser(description="HS Detection Postprocessor")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--subjects-dir", required=True)
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--left-label", type=int, default=17)
    parser.add_argument("--right-label", type=int, default=53)
    parser.add_argument("--ai-left-th", type=float, default=-0.070839747728063)
    parser.add_argument("--ai-right-th", type=float, default=0.046915816971433)
    parser.add_argument("--qc-orientation", default="coronal")
    parser.add_argument("--qc-slice-axis", type=int, default=2)
    parser.add_argument("--qc-top10", type=int, default=10)
    parser.add_argument("--qc-thresh-frac", type=float, default=0.05)
    parser.add_argument("--pdf-opacity", type=float, default=0.55)
    parser.add_argument("--report-pick", default="3,4,5,6")
    parser.add_argument("--report-title", default="NeuroInsight Hippocampal Analysis Report")
    parser.add_argument("--niivue-opacity", type=float, default=0.35)
    parser.add_argument("--niivue-orientation", default="coronal")
    args = parser.parse_args()

    print(f"=== HS Detection Postprocess ===")
    print(f"Subject: {args.subject_id}")
    print(f"SUBJECTS_DIR: {args.subjects_dir}")
    print(f"Bundle root: {args.bundle_root}")

    # 1. Parse aseg.stats
    stats_path = os.path.join(
        args.subjects_dir, args.subject_id, "stats", "aseg.stats"
    )
    if not os.path.exists(stats_path):
        print(f"ERROR: aseg.stats not found at {stats_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading aseg.stats from: {stats_path}")
    volumes = parse_aseg_stats(stats_path)

    left_vol = volumes.get(args.left_label, 0.0)
    right_vol = volumes.get(args.right_label, 0.0)
    print(f"Left Hippocampus (label {args.left_label}): {left_vol:.1f} mm³")
    print(f"Right Hippocampus (label {args.right_label}): {right_vol:.1f} mm³")

    if left_vol == 0 and right_vol == 0:
        print("WARNING: Both hippocampal volumes are zero!", file=sys.stderr)

    # 2. Compute asymmetry index
    ai = compute_asymmetry_index(left_vol, right_vol)
    print(f"Asymmetry Index (L-R)/(L+R): {ai:.6f}")

    # 3. Classify
    classification = classify_hs(ai, args.ai_left_th, args.ai_right_th)
    print(f"Classification: {classification}")

    # 4. Write hs_metrics.json
    metrics = {
        "subject_id": args.subject_id,
        "volumes_mm3": {"left": left_vol, "right": right_vol},
        "asymmetry_index": ai,
        "thresholds": {
            "left_hs": args.ai_left_th,
            "right_hs": args.ai_right_th,
        },
        "classification": classification,
    }

    metrics_dir = os.path.join(args.bundle_root, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    metrics_path = os.path.join(metrics_dir, "hs_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Wrote metrics: {metrics_path}")

    # 5. Convert volumes for bundle & viewer
    brain_mgz = os.path.join(args.subjects_dir, args.subject_id, "mri", "brain.mgz")
    aseg_mgz = os.path.join(args.subjects_dir, args.subject_id, "mri", "aseg.auto.mgz")

    t1_nii, hippo_nii = convert_volumes_for_bundle(
        args.subjects_dir, args.subject_id, args.bundle_root,
        args.left_label, args.right_label,
    )

    # 6. Generate QC overlay images
    qc_dir = os.path.join(args.bundle_root, "qc", "hs")
    qc_paths = generate_qc_images(
        brain_path=brain_mgz,
        aseg_path=aseg_mgz,
        subject_id=args.subject_id,
        output_dir=qc_dir,
        left_label=args.left_label,
        right_label=args.right_label,
        orientation=args.qc_orientation,
        slice_axis=args.qc_slice_axis,
        top_n=args.qc_top10,
        thresh_frac=args.qc_thresh_frac,
        overlay_opacity=args.pdf_opacity,
    )
    print(f"Generated {len(qc_paths)} QC overlay images")

    # 7. Generate PDF report (picks slices from the same evenly-spaced set)
    report_pick = [int(x.strip()) for x in args.report_pick.split(",")]
    report_path = os.path.join(args.bundle_root, "reports", "hs_report.pdf")
    generate_report_pdf(
        brain_path=brain_mgz,
        aseg_path=aseg_mgz,
        subject_id=args.subject_id,
        metrics=metrics,
        output_path=report_path,
        left_label=args.left_label,
        right_label=args.right_label,
        orientation=args.qc_orientation,
        slice_axis=args.qc_slice_axis,
        n_slices=args.qc_top10,
        thresh_frac=args.qc_thresh_frac,
        overlay_opacity=args.pdf_opacity,
        report_pick=report_pick,
        title=args.report_title,
    )
    print(f"Generated report: {report_path}")

    # 8. Generate Niivue viewer manifest
    viewer_path = generate_niivue_manifest(
        subject_id=args.subject_id,
        bundle_root=args.bundle_root,
        overlay_opacity=args.niivue_opacity,
        orientation=args.niivue_orientation,
        report_slices=[3, 4, 5, 6],
    )
    print(f"Generated Niivue manifest: {viewer_path}")

    print("=== HS Detection Postprocess complete ===")


if __name__ == "__main__":
    main()
