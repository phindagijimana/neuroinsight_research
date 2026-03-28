#!/usr/bin/env python3
"""
Print key paths in the MNE "sample" dataset after download.

Usage (from repo root):
  python3 eeg/scripts/print_mne_sample_layout.py

Requires: mne, network on first run (dataset ~1.5 GB).

Use this to locate registered EEG/MEG, MRI, BEM, and FreeSurfer surfaces
for evaluating a real source-localization → NIR bundle export.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    try:
        import mne
    except ImportError:
        print("Install MNE: pip install mne", file=sys.stderr)
        return 1

    # data_path() is the MNE-sample-data root (contains MEG/, subjects/, …).
    path = Path(mne.datasets.sample.data_path(download=True))
    sub = path / "subjects" / "sample"
    meg = path / "MEG" / "sample"

    print("MNE sample data_path:", path)
    print()
    print("Raw (MEG + EEG):")
    for p in sorted(meg.glob("*.fif")):
        if "raw" in p.name.lower():
            print(" ", p)
    print()
    print("MRI (FreeSurfer subject):")
    for rel in ("mri/T1.mgz", "surf/lh.pial", "surf/rh.pial", "bem/sample-5120-5120-5120-bem.fif"):
        p = sub / rel
        print(" ", p, "OK" if p.is_file() else "MISSING")
    print()
    print("Typical inverse tutorial inputs (may need to be computed):")
    for pat in ("*fwd.fif", "*cov.fif", "*inv.fif"):
        for p in meg.glob(pat):
            print(" ", p)
    print()
    print("Next: follow MNE inverse tutorials; export cortical STC to NIR NPZ + manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
