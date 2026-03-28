"""
Versioned on-disk bundle for linked EEG + cortical source viewing.

Demo assets use a UV sphere mesh and synthetic vertex time series aligned with
the compact EEG preview window (duration_s × n_time_points).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "nir_multimodal_manifest.json"
DEMO_CORTEX_REL = "source/demo_cortex.npz"

_SCHEMA_VERSION = 1


def _uv_sphere_mesh(
    *, radius: float = 0.11, n_lon: int = 28, n_lat: int = 14
) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices (V,3) float32, faces (F,3) int32). y is up (head)."""
    verts: list[list[float]] = []
    verts.append([0.0, radius, 0.0])
    for j in range(1, n_lat):
        phi = np.pi * j / n_lat
        sp = float(radius * np.sin(phi))
        y = float(radius * np.cos(phi))
        for i in range(n_lon):
            th = 2.0 * np.pi * i / n_lon
            verts.append([sp * np.cos(th), y, sp * np.sin(th)])
    verts.append([0.0, -radius, 0.0])
    v_np = np.asarray(verts, dtype=np.float32)
    north = 0
    south = v_np.shape[0] - 1
    base = 1
    faces: list[list[int]] = []
    for i in range(n_lon):
        a = base + i
        b = base + (i + 1) % n_lon
        faces.append([north, b, a])
    for j in range(n_lat - 2):
        row0 = base + j * n_lon
        row1 = row0 + n_lon
        for i in range(n_lon):
            a = row0 + i
            b = row0 + (i + 1) % n_lon
            c = row1 + i
            d = row1 + (i + 1) % n_lon
            faces.append([a, c, b])
            faces.append([b, c, d])
    last_row = base + (n_lat - 2) * n_lon
    for i in range(n_lon):
        a = last_row + i
        b = last_row + (i + 1) % n_lon
        faces.append([a, south, b])
    f_np = np.asarray(faces, dtype=np.int32)
    return v_np, f_np


def _synthetic_vertex_series(
    vertices: np.ndarray,
    *,
    sfreq: float,
    duration_s: float,
    n_time_points: int,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Smooth random walk + band-limited sin on each vertex; shape (V, T)."""
    rng = np.random.default_rng(seed)
    n_raw = max(2, int(sfreq * duration_s))
    t_raw = np.arange(n_raw, dtype=np.float64) / sfreq
    idx = np.linspace(0, n_raw - 1, n_time_points).astype(np.int64)
    t_out = t_raw[idx]

    y = vertices[:, 1] / (np.linalg.norm(vertices, axis=1) + 1e-9)
    th = np.arctan2(vertices[:, 2], vertices[:, 0])
    n_v = vertices.shape[0]
    walk = np.cumsum(rng.standard_normal((n_v, n_raw)) * 0.04, axis=1)
    walk -= np.mean(walk, axis=1, keepdims=True)
    carrier = np.sin(th)[:, None] * np.sin(2.0 * np.pi * 10.0 * t_raw)[None, :]
    global_env = 0.5 + 0.5 * np.sin(2.0 * np.pi * 0.8 * t_raw)
    raw = walk + 0.35 * carrier * global_env
    data = raw[:, idx].astype(np.float32)
    return data, t_out.astype(np.float64)


def write_demo_cortex_bundle(
    job_dir: Path,
    *,
    eeg_rel: str,
    mri_rel: str,
    sfreq: float = 250.0,
    duration_s: float = 4.0,
    n_time_points: int = 400,
) -> dict[str, Any]:
    """
    Write ``source/demo_cortex.npz`` and ``nir_multimodal_manifest.json`` under job_dir.

    Returns the manifest dict (also written to disk).
    """
    job_dir = Path(job_dir)
    src_dir = job_dir / "source"
    src_dir.mkdir(parents=True, exist_ok=True)
    npz_path = job_dir / DEMO_CORTEX_REL

    verts, faces = _uv_sphere_mesh()
    data, times = _synthetic_vertex_series(
        verts,
        sfreq=sfreq,
        duration_s=duration_s,
        n_time_points=n_time_points,
    )
    np.savez_compressed(
        str(npz_path),
        vertices=verts,
        faces=faces,
        data=data,
        times=times,
    )

    manifest: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "eeg_file": eeg_rel,
        "mri_ref": mri_rel,
        "cortex_npz": DEMO_CORTEX_REL,
        "space": "demo_head_normalized",
        "source_units": "normalized_demo",
        "inverse_method": "synthetic_sphere_demo",
        "time_alignment": {
            "duration_s": duration_s,
            "n_time_points": n_time_points,
            "note": "Matches EegViewerPanel compact eeg_preview request.",
        },
        "vertex_count": int(verts.shape[0]),
        "n_times": int(data.shape[1]),
        "qc": {
            "status": "demo",
            "message": "Toy cortical mesh; not patient-specific or clinical grade.",
        },
        "linkage": {
            "eeg_file": eeg_rel,
            "mri_ref": mri_rel,
            "registration": (
                "Demo only: no patient coregistration. EEG drives a synthetic cortical time series; "
                "the mesh is not fitted to the MRI volume below."
            ),
            "signal_to_source": (
                "Signal View time index maps to the same downsampled time grid as vertex amplitudes "
                f"({duration_s}s × {n_time_points} samples)."
            ),
            "source_to_anatomy": (
                "Niivue shows the MRI named in mri_ref for anatomical context. Real pipelines would "
                "use the same subject’s cortical surface from segmentation (here: placeholder sphere)."
            ),
        },
    }
    (job_dir / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote multimodal demo bundle under %s", job_dir)
    return manifest


def load_manifest_dict(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)
