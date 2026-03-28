"""
Downsampled EEG preview for the web viewer (MNE).

Reads a short window from disk, returns JSON-safe arrays for time series + 2D layout.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _read_raw(path: Path):
    try:
        import mne
    except ImportError as e:
        raise RuntimeError("mne is not installed") from e

    p = str(path)
    lower = p.lower()
    if lower.endswith(".vhdr"):
        return mne.io.read_raw_brainvision(p, preload=False, verbose="ERROR")
    if lower.endswith(".edf"):
        return mne.io.read_raw_edf(p, preload=False, verbose="ERROR")
    if lower.endswith(".bdf"):
        return mne.io.read_raw_bdf(p, preload=False, verbose="ERROR")
    if lower.endswith(".fif") or lower.endswith(".fif.gz"):
        return mne.io.read_raw_fif(p, preload=False, verbose="ERROR")
    raise ValueError(
        "Unsupported EEG extension (use .edf, .bdf, .vhdr, .fif / .fif.gz)"
    )


def _channel_positions(info, ch_names: list[str]) -> list[dict[str, Any]]:
    """2D layout coordinates in [-0.5, 0.5]-ish space for SVG topomap."""
    try:
        import mne
        from mne.channels import make_standard_montage
        from mne.channels.layout import make_eeg_layout
    except ImportError:
        return []

    try:
        montage = info.get_montage()
        if montage is None:
            montage = make_standard_montage("standard_1020")
        info2 = info.copy()
        info2.set_montage(montage, on_missing="ignore")
        layout = make_eeg_layout(info2, radius=0.35, width=0.3)
    except Exception as e:
        logger.debug("EEG layout failed: %s", e)
        return []

    name_to_xy: dict[str, tuple[float, float]] = {}
    for i, name in enumerate(layout.names):
        if i < len(layout.pos):
            row = layout.pos[i]
            name_to_xy[name] = (float(row[0]), float(row[1]))

    out: list[dict[str, Any]] = []
    for name in ch_names:
        if name in name_to_xy:
            x, y = name_to_xy[name]
            out.append({"name": name, "x": x, "y": y})
    return out


def build_eeg_preview(
    local_path: Path,
    *,
    duration_s: float = 5.0,
    n_time_points: int = 600,
    max_channels: int = 32,
    time_offset_s: float = 0.0,
) -> dict[str, Any]:
    """
    Load a time window starting at ``time_offset_s`` for up to ``duration_s``,
    pick EEG-like channels, downsample.

    ``times`` in the response are **absolute** seconds from the start of the
    original recording (so the client can pan/zoom along the full file).

    Returns dict with times, ch_names, waveforms (list of lists), positions,
    total_duration_s, time_offset_s.
    """
    raw = _read_raw(local_path)

    try:
        import mne
    except ImportError as e:
        raise RuntimeError("mne is not installed") from e

    picks = mne.pick_types(raw.info, meg=False, eeg=True, exclude=[])
    if len(picks) == 0:
        picks = np.arange(min(max_channels, len(raw.ch_names)), dtype=int)
    else:
        picks = picks[:max_channels]

    raw.pick(picks)

    sfreq = float(raw.info["sfreq"])
    n_times_hdr = int(raw.n_times)
    total_duration_s = (n_times_hdr / sfreq) if n_times_hdr > 0 and sfreq > 0 else 0.0

    t_off = max(0.0, float(time_offset_s))
    if total_duration_s > 0.0:
        t_off = min(t_off, max(0.0, total_duration_s - 1.0 / max(sfreq, 1.0)))

    dur_req = max(float(duration_s), 0.5 / max(sfreq, 1.0))
    remaining = max(0.0, total_duration_s - t_off)
    dur = min(dur_req, remaining) if remaining > 0 else min(dur_req, max(total_duration_s, 0.001))
    if dur <= 0.0:
        dur = min(dur_req, max(total_duration_s, 0.001))

    raw.crop(tmin=t_off, tmax=t_off + dur)
    raw.load_data()

    data = raw.get_data()
    # MNE times are relative to crop start; shift to absolute file time.
    times = raw.times.astype(float) + t_off
    ch_names = list(raw.ch_names)

    n = data.shape[1]
    if n > n_time_points:
        idx = np.linspace(0, n - 1, n_time_points).astype(np.int64)
        data = data[:, idx]
        times = times[idx]

    positions = _channel_positions(raw, ch_names)

    waveforms = [[float(x) for x in row] for row in data]

    return {
        "sfreq": sfreq,
        "duration_s": float(dur),
        "time_offset_s": float(t_off),
        "total_duration_s": float(total_duration_s),
        "times": [float(t) for t in times],
        "ch_names": ch_names,
        "waveforms": waveforms,
        "positions": positions,
        "source_file": local_path.name,
    }
