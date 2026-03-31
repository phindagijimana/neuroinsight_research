#!/usr/bin/env python3
"""
Stage one BDSP-style BIDS EEG + BIND-style MRI subject into a single folder for
``multimodal_epilepsy_biomarker`` (``eeg/raw/`` + ``T1w.nii.gz`` in one directory).

**HPC workflow — connect first**

1. **SSH to your HPC login node** (the same environment where lab NFS paths like
   ``/mnt/nfs/Gugger_Lab/...`` exist). This script will **not** see those paths from
   your laptop or from the NIR web server unless they are mounted there too.
2. ``cd`` to a clone of NeuroInsight_Research_Tool (or copy this script over) and run
   the commands below. Output should live under a path **compute nodes can read**
   (e.g. your home under ``.../Documents/NeuroInsight_Research``).
3. **Then** connect the NIR UI to HPC (SSH tunnel + Jobs page **HPC** / **Activate SLURM
   Backend**; see ``docs/HPC_PIPELINE_SUBMISSION_GUIDE.md``) and submit the staged
   folder as the multimodal workflow input.

Examples::

  # Auto-pick first subject that exists in both trees (BIND_Data/<id> + bids/sub-<id>)
  python3 eeg/scripts/stage_bdsp_bind_multimodal.py \\
    --bids-root /mnt/nfs/Gugger_Lab/BDSP_EEG/bids \\
    --bind-parent /mnt/nfs/Gugger_Lab/BIND_Data \\
    --out /mnt/nfs/home/urmc-sh.rochester.edu/pndagiji/Documents/NeuroInsight_Research/multimodal_I0001

  # Pin one ID (BIND folder name must match, BIDS must have sub-<ID>)
  python3 eeg/scripts/stage_bdsp_bind_multimodal.py \\
    --bids-root .../bids --bind-parent .../BIND_Data --subject I0001 --out .../multimodal_I0001

  # If BIDS uses a different subject label than the BIND folder name:
  python3 eeg/scripts/stage_bdsp_bind_multimodal.py \\
    --bids-root .../bids --bind-dir .../BIND_Data/I0001 \\
    --bids-subject sub-NDARABC123 --out .../run1

If ``bids/participants.tsv`` contains a column that maps to BIND IDs (e.g. ``bind_id``),
use ``--participants-bind-column bind_id`` so the script can resolve pairs.

**Staging mode (default):** Files are **copied** into ``--out`` so the run folder is
self-contained and Singularity bind mounts (single ``input_dir``) see real files under
``eeg/raw/``. Use ``--symlink`` only for quick local tests (symlinks often break in
containers).
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path


EEG_SUFFIXES = (".edf", ".bdf", ".fif", ".vhdr", ".eeg", ".vmrk")


def _find_t1_nifti(bind_dir: Path) -> Path | None:
    """Prefer T1w.nii.gz; else first plausible *T1*.nii.gz under bind_dir."""
    for pat in ("T1w.nii.gz", "T1w.nii"):
        for p in bind_dir.rglob(pat):
            if p.is_file():
                return p
    for p in sorted(bind_dir.rglob("*.nii.gz")):
        n = p.name.lower()
        if "t1" in n and "lesion" not in n and "label" not in n:
            return p
    for p in sorted(bind_dir.rglob("*.nii")):
        n = p.name.lower()
        if "t1" in n and "lesion" not in n:
            return p
    return None


def _find_eeg_raw(bids_root: Path, bids_subject: str) -> Path | None:
    """First continuous EEG file under bids_root/sub-<sub>/..."""
    sub = bids_root / bids_subject
    if not sub.is_dir():
        return None
    for root, _, files in os.walk(sub):
        for fn in sorted(files):
            if fn.lower().endswith(EEG_SUFFIXES):
                p = Path(root) / fn
                if p.is_file():
                    return p
    return None


def _load_participants_map(
    bids_root: Path, column: str
) -> dict[str, str]:
    """Return map: bids_subject -> bind_id from participants.tsv."""
    participants = bids_root / "participants.tsv"
    if not participants.is_file():
        return {}
    out: dict[str, str] = {}
    with participants.open(newline="", encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    for row in rows:
        pid = row.get("participant_id") or row.get("participant_id".upper())
        if not pid:
            continue
        if not pid.startswith("sub-"):
            pid = f"sub-{pid}"
        if column in row and row[column] and str(row[column]).strip():
            out[pid] = str(row[column]).strip()
    return out


def _iter_bind_ids(bind_parent: Path) -> list[str]:
    if not bind_parent.is_dir():
        return []
    return sorted(
        p.name
        for p in bind_parent.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bids-root", required=True, type=Path, help="BDSP BIDS root (dataset root)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument(
        "--bind-parent",
        type=Path,
        help="Parent of per-subject MRI folders (e.g. .../BIND_Data with I0001, I0002, ...)",
    )
    g.add_argument(
        "--bind-dir",
        type=Path,
        help="Single subject MRI directory (e.g. .../BIND_Data/I0001)",
    )
    ap.add_argument(
        "--subject",
        help="BIND folder name / ID (e.g. I0001). Matched to BIDS sub-<subject> unless --bids-subject is set.",
    )
    ap.add_argument(
        "--bids-subject",
        help="Explicit BIDS subject folder name (e.g. sub-01 or sub-NDAR...). Overrides sub-<subject>.",
    )
    ap.add_argument(
        "--participants-bind-column",
        metavar="COL",
        help="If set, read bids/participants.tsv and match BIDS rows to BIND folder names via this column.",
    )
    ap.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output staging directory (created). Will contain eeg/raw/ and T1w.nii.gz",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions only; do not create output",
    )
    ap.add_argument(
        "--symlink",
        action="store_true",
        help="Symlink EEG + T1 instead of copying (can break under SLURM/Singularity).",
    )
    ap.add_argument(
        "--list-matches",
        action="store_true",
        help="Print BIND IDs that have both a T1 under BIND and EEG under bids/sub-<id>; exit 0",
    )
    args = ap.parse_args()

    bids_root = args.bids_root.expanduser().resolve()
    if not bids_root.is_dir():
        print(f"ERROR: bids-root not found: {bids_root}", file=sys.stderr)
        return 1

    bind_dir: Path | None = None
    bind_id: str | None = None
    bids_subject: str | None = args.bids_subject

    if args.bind_dir:
        bind_dir = args.bind_dir.expanduser().resolve()
        if not bind_dir.is_dir():
            print(f"ERROR: bind-dir not found: {bind_dir}", file=sys.stderr)
            return 1
        bind_id = bind_dir.name
    elif args.bind_parent:
        if args.subject:
            bind_dir = (args.bind_parent / args.subject).resolve()
            bind_id = args.subject
        elif args.list_matches or not args.subject:
            # list mode or auto-pick
            pass
    else:
        print("ERROR: provide --bind-parent or --bind-dir", file=sys.stderr)
        return 1

    pmap: dict[str, str] = {}
    if args.participants_bind_column:
        pmap = _load_participants_map(bids_root, args.participants_bind_column)
        if not pmap:
            print(
                "WARN: no mapping from participants.tsv or column missing",
                file=sys.stderr,
            )

    if args.list_matches:
        if not args.bind_parent:
            print("ERROR: --list-matches requires --bind-parent", file=sys.stderr)
            return 1
        print("BIND_ID\tBIDS_SUBJECT\tT1\tEEG")
        for bid in _iter_bind_ids(args.bind_parent):
            t1 = _find_t1_nifti(args.bind_parent / bid)
            if not t1:
                continue
            # Try direct sub-<bid>
            bs = f"sub-{bid}"
            eeg = _find_eeg_raw(bids_root, bs)
            if eeg:
                print(f"{bid}\t{bs}\t{t1}\t{eeg}")
                continue
            # Try participants map: bids subject -> bind id
            for bsub, mapped in pmap.items():
                if mapped == bid:
                    eeg = _find_eeg_raw(bids_root, bsub)
                    if eeg:
                        print(f"{bid}\t{bsub}\t{t1}\t{eeg}")
        return 0

    if bind_dir is None and args.bind_parent and args.subject:
        bind_dir = (args.bind_parent / args.subject).resolve()
        bind_id = args.subject

    if bind_dir is None and args.bind_parent and not args.subject:
        # Auto: first pair from list-matches logic
        for bid in _iter_bind_ids(args.bind_parent):
            t1 = _find_t1_nifti(args.bind_parent / bid)
            if not t1:
                continue
            bs = f"sub-{bid}"
            eeg = _find_eeg_raw(bids_root, bs)
            if eeg:
                bind_dir = args.bind_parent / bid
                bind_id = bid
                bids_subject = bs
                break
            for bsub, mapped in pmap.items():
                if mapped == bid:
                    eeg = _find_eeg_raw(bids_root, bsub)
                    if eeg:
                        bind_dir = args.bind_parent / bid
                        bind_id = bid
                        bids_subject = bsub
                        break
            if bind_dir:
                break
        if not bind_dir:
            print(
                "ERROR: could not auto-find any subject with T1 in BIND and EEG in BIDS. "
                "Try --list-matches, or set --subject / --bids-subject, or --participants-bind-column.",
                file=sys.stderr,
            )
            return 1

    assert bind_dir is not None
    if not bind_dir.is_dir():
        print(f"ERROR: MRI directory not found: {bind_dir}", file=sys.stderr)
        return 1

    t1 = _find_t1_nifti(bind_dir)
    if not t1:
        print(f"ERROR: no T1 NIfTI found under {bind_dir}", file=sys.stderr)
        return 1

    if bids_subject:
        bs = bids_subject if bids_subject.startswith("sub-") else f"sub-{bids_subject}"
    elif bind_id:
        bs = f"sub-{bind_id}"
    else:
        bs = f"sub-{bind_dir.name}"

    eeg = _find_eeg_raw(bids_root, bs)
    if not eeg:
        print(
            f"ERROR: no EEG file under {bids_root / bs}. "
            "Try --bids-subject or --participants-bind-column.",
            file=sys.stderr,
        )
        return 1

    out = args.out.expanduser().resolve()
    eeg_raw = out / "eeg" / "raw"
    t1_link = out / "T1w.nii.gz"

    mode = "symlink" if args.symlink else "copy"
    print("Staging (%s):" % mode)
    print("  BIDS root:     ", bids_root)
    print("  BIDS subject:  ", bs)
    print("  EEG (source):  ", eeg)
    print("  T1 (source):   ", t1)
    print("  Output:        ", out)
    print("  eeg/raw dest:  ", eeg_raw / eeg.name)
    print("  T1w dest:      ", t1_link)

    if args.dry_run:
        return 0

    out.mkdir(parents=True, exist_ok=True)
    eeg_raw.mkdir(parents=True, exist_ok=True)

    def rel_or_abs(target: Path, link: Path) -> str:
        try:
            return os.path.relpath(target, start=link.parent)
        except ValueError:
            return str(target)

    eeg_dest = eeg_raw / eeg.name
    if eeg_dest.exists() or eeg_dest.is_symlink():
        eeg_dest.unlink()

    if args.symlink:
        os.symlink(rel_or_abs(eeg, eeg_dest), eeg_dest)
    else:
        shutil.copy2(eeg, eeg_dest)

    if t1_link.exists() or t1_link.is_symlink():
        t1_link.unlink()
    t1_alt = out / "T1w.nii"
    if t1_alt.exists() or t1_alt.is_symlink():
        t1_alt.unlink()

    if str(t1).endswith(".nii.gz") or t1.name.endswith(".nii.gz"):
        if args.symlink:
            os.symlink(rel_or_abs(t1, t1_link), t1_link)
        else:
            shutil.copy2(t1, t1_link)
    else:
        if args.symlink:
            os.symlink(rel_or_abs(t1, t1_alt), t1_alt)
        else:
            shutil.copy2(t1, t1_alt)
        print(
            "WARN: T1 is not .nii.gz; wrote T1w.nii. "
            "Convert to T1w.nii.gz if mri_segmentation rejects it.",
            file=sys.stderr,
        )

    print("Done. Submit this folder as input_dir for multimodal_epilepsy_biomarker (directory mode).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
