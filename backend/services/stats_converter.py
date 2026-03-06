"""
Stats-to-CSV converter for all NeuroInsight plugins and workflows.

Shared module used by:
  1. Plugin bundle extraction (post-job CSV generation on HPC)
  2. Dashboard API endpoint (on-the-fly fallback for older jobs)

Each converter reads raw stats files and returns a list of CSVSheet objects,
each containing a name, headers, and rows that can be written as CSV.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Data structures                                                             #
# --------------------------------------------------------------------------- #

@dataclass
class CSVSheet:
    """One logical CSV file with display metadata."""
    name: str
    filename: str
    description: str
    headers: list[str]
    rows: list[list[Any]]
    category: str = "general"

    def to_csv_string(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.headers)
        writer.writerows(self.rows)
        return buf.getvalue()

    def preview(self, max_rows: int = 25) -> dict:
        return {
            "name": self.name,
            "filename": self.filename,
            "description": self.description,
            "category": self.category,
            "headers": self.headers,
            "rows": self.rows[:max_rows],
            "total_rows": len(self.rows),
            "truncated": len(self.rows) > max_rows,
        }


# --------------------------------------------------------------------------- #
#  Pipeline-name to converter mapping                                          #
# --------------------------------------------------------------------------- #

PIPELINE_CONVERTERS: dict[str, str] = {
    "freesurfer recon-all": "freesurfer_recon",
    "freesurfer_recon": "freesurfer_recon",
    "fastsurfer": "fastsurfer",
    "freesurfer volumetric (autorecon1 + autorecon2-volonly)": "freesurfer_volonly",
    "freesurfer_autorecon_volonly": "freesurfer_volonly",
    "freesurfer longitudinal (cross->base->long)": "freesurfer_longitudinal",
    "freesurfer_longitudinal": "freesurfer_longitudinal",
    "freesurfer longitudinal stats utility": "freesurfer_longitudinal_stats",
    "freesurfer_longitudinal_stats": "freesurfer_longitudinal_stats",
    "freesurfer segmentha_t1": "segmentha_t1",
    "segmentha_t1": "segmentha_t1",
    "freesurfer segmentha_t2": "segmentha_t2",
    "segmentha_t2": "segmentha_t2",
    "hs detection postprocess (utility)": "hs_postprocess",
    "hs_postprocess": "hs_postprocess",
    "meld graph": "meld_graph",
    "meld_graph": "meld_graph",
    "fmriprep": "fmriprep",
    "xcp-d": "xcpd",
    "xcpd": "xcpd",
    "qsiprep": "qsiprep",
    "qsirecon": "qsirecon",
    "tsc segmentation (tsccnn3d)": "tsc_segmentation_tsccnn3d",
    "tsc_segmentation_tsccnn3d": "tsc_segmentation_tsccnn3d",
}

WORKFLOW_STEPS: dict[str, list[str]] = {
    "cortical lesion detection": ["freesurfer_recon", "meld_graph"],
    "cortical_lesion_detection": ["freesurfer_recon", "meld_graph"],
    "hs detection": ["freesurfer_volonly", "hs_postprocess"],
    "hs_detection": ["freesurfer_volonly", "hs_postprocess"],
    "hippocampal subfields t1": ["freesurfer_recon", "segmentha_t1"],
    "hippo_subfields_t1": ["freesurfer_recon", "segmentha_t1"],
    "hippocampal subfields t2": ["freesurfer_recon", "segmentha_t2"],
    "hippo_subfields_t2": ["freesurfer_recon", "segmentha_t2"],
    "freesurfer longitudinal full": ["freesurfer_longitudinal"],
    "freesurfer_longitudinal_full": ["freesurfer_longitudinal"],
    "fmri full": ["fmriprep", "xcpd"],
    "fmri_full": ["fmriprep", "xcpd"],
    "diffusion full": ["qsiprep", "qsirecon"],
    "diffusion_full": ["qsiprep", "qsirecon"],
    "tuberous sclerosis detection": ["tsc_segmentation_tsccnn3d"],
    "tuberous_sclerosis_detection": ["tsc_segmentation_tsccnn3d"],
}


def get_converter_id(pipeline_name: str) -> str | None:
    key = pipeline_name.strip().lower()
    return PIPELINE_CONVERTERS.get(key)


def get_workflow_steps(pipeline_name: str) -> list[str] | None:
    key = pipeline_name.strip().lower()
    return WORKFLOW_STEPS.get(key)


# --------------------------------------------------------------------------- #
#  Generic FreeSurfer .stats parser                                            #
# --------------------------------------------------------------------------- #

def _parse_stats_text(text: str) -> tuple[dict[str, Any], list[str], list[list[Any]]]:
    """Parse a FreeSurfer .stats file into (measures_dict, headers, table_rows)."""
    measures: dict[str, Any] = {}
    headers: list[str] = []
    rows: list[list[Any]] = []
    col_headers: list[str] = []

    for line in text.splitlines():
        if line.startswith("# Measure"):
            parts = [p.strip() for p in line[len("# Measure"):].split(",")]
            if len(parts) >= 4:
                name = parts[1]
                try:
                    measures[name] = float(parts[3])
                except (ValueError, IndexError):
                    measures[name] = parts[3] if len(parts) > 3 else ""
                if len(parts) >= 5:
                    measures[f"{name}_unit"] = parts[4].strip()
        elif line.startswith("# ColHeaders"):
            col_headers = line.split()[2:]
            headers = list(col_headers)
        elif not line.startswith("#") and line.strip() and col_headers:
            cols = line.split()
            if len(cols) == len(col_headers):
                row: list[Any] = []
                for v in cols:
                    try:
                        row.append(float(v))
                    except ValueError:
                        row.append(v)
                rows.append(row)

    return measures, headers, rows


def _parse_hippo_volumes_text(text: str) -> list[tuple[str, float]]:
    """Parse a FreeSurfer hippoSfVolumes text file into (subfield, volume) pairs."""
    entries: list[tuple[str, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            try:
                entries.append((parts[0], float(parts[1])))
            except ValueError:
                continue
    return entries


def _parse_tsv_text(text: str) -> tuple[list[str], list[list[Any]]]:
    """Parse a TSV file into (headers, rows)."""
    lines = text.strip().splitlines()
    if not lines:
        return [], []
    headers = lines[0].split("\t")
    rows: list[list[Any]] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split("\t")
        row: list[Any] = []
        for v in cols:
            v = v.strip()
            if v in ("n/a", "N/A", ""):
                row.append(None)
            else:
                try:
                    row.append(float(v))
                except ValueError:
                    row.append(v)
        rows.append(row)
    return headers, rows


# --------------------------------------------------------------------------- #
#  File-reading abstraction (local or remote)                                  #
# --------------------------------------------------------------------------- #

@dataclass
class FileProvider:
    """Abstraction for reading files from local or remote (SSH) locations."""
    local_dir: Any | None = None
    remote_dir: str | None = None
    ssh: Any | None = None
    _file_cache: dict[str, str] = field(default_factory=dict)
    _file_list: list[str] | None = None

    def list_files(self) -> list[str]:
        if self._file_list is not None:
            return self._file_list

        if self.local_dir:
            from pathlib import Path
            root = Path(self.local_dir)
            self._file_list = [
                str(f.relative_to(root))
                for f in root.rglob("*") if f.is_file()
            ]
        elif self.remote_dir and self.ssh:
            cmd = (
                f"find {self.remote_dir!r} -type f "
                f"-not -path '*/_inputs/*' -printf '%P\\n' 2>/dev/null"
            )
            exit_code, stdout, _ = self.ssh.execute(cmd, timeout=30)
            self._file_list = [
                l.strip() for l in stdout.strip().split("\n")
                if l.strip()
            ] if exit_code == 0 else []
        else:
            self._file_list = []
        return self._file_list

    def find_files(self, *patterns: str) -> list[str]:
        all_files = self.list_files()
        results = []
        for f in all_files:
            fname = PurePosixPath(f).name.lower()
            fpath = f.lower()
            for pat in patterns:
                pat_lower = pat.lower()
                if pat_lower.startswith("*"):
                    if fname.endswith(pat_lower[1:]):
                        results.append(f)
                        break
                elif pat_lower in fname or pat_lower in fpath:
                    results.append(f)
                    break
        return results

    def read_text(self, rel_path: str) -> str | None:
        if rel_path in self._file_cache:
            return self._file_cache[rel_path]

        content: str | None = None
        if self.local_dir:
            from pathlib import Path
            p = Path(self.local_dir) / rel_path
            if p.exists():
                content = p.read_text(errors="replace")
        elif self.remote_dir and self.ssh:
            full_path = f"{self.remote_dir}/{rel_path}"
            try:
                exit_code, stdout, _ = self.ssh.execute(
                    f"cat {full_path!r}", timeout=15,
                )
                if exit_code == 0:
                    content = stdout
            except Exception:
                pass

        if content is not None:
            self._file_cache[rel_path] = content
        return content

    def batch_read(self, rel_paths: list[str]) -> dict[str, str]:
        """Read multiple files in one operation (batched for SSH)."""
        if not rel_paths:
            return {}

        uncached = [p for p in rel_paths if p not in self._file_cache]

        if self.local_dir:
            from pathlib import Path
            root = Path(self.local_dir)
            for rp in uncached:
                fpath = root / rp
                if fpath.exists():
                    self._file_cache[rp] = fpath.read_text(errors="replace")

        elif self.remote_dir and self.ssh and uncached:
            _DELIM = "===NEUROINSIGHT_CSV_BOUNDARY==="
            full_paths = [f"{self.remote_dir}/{p}" for p in uncached]
            paths_str = " ".join(f'"{p}"' for p in full_paths)
            cmd = (
                f"for f in {paths_str}; do "
                f"echo '{_DELIM}'\"$f\"; cat \"$f\" 2>/dev/null; "
                f"done"
            )
            exit_code, stdout, _ = self.ssh.execute(cmd, timeout=60)
            if exit_code == 0 and stdout.strip():
                chunks = stdout.split(_DELIM)
                for chunk in chunks:
                    if not chunk.strip():
                        continue
                    lines = chunk.strip().split("\n", 1)
                    file_path = lines[0].strip()
                    content = lines[1] if len(lines) > 1 else ""
                    rel = file_path.replace(self.remote_dir + "/", "", 1)
                    self._file_cache[rel] = content

        return {p: self._file_cache[p] for p in rel_paths if p in self._file_cache}


# --------------------------------------------------------------------------- #
#  Per-plugin converters                                                       #
# --------------------------------------------------------------------------- #

def convert_freesurfer_recon(fp: FileProvider) -> list[CSVSheet]:
    """FreeSurfer recon-all: aseg, aparc (DK + Destrieux), wmparc, BA_exvivo."""
    sheets: list[CSVSheet] = []

    stats_files = fp.find_files(
        "aseg.stats", "lh.aparc.stats", "rh.aparc.stats",
        "lh.aparc.a2009s.stats", "rh.aparc.a2009s.stats",
        "wmparc.stats",
        "lh.BA_exvivo.stats", "rh.BA_exvivo.stats",
    )
    contents = fp.batch_read(stats_files)

    # --- brain_volumes_summary.csv (from aseg.stats Measure lines) ---
    aseg_files = [f for f in stats_files if f.lower().endswith("aseg.stats")]
    if aseg_files:
        text = contents.get(aseg_files[0], "")
        if text:
            measures, headers, table_rows = _parse_stats_text(text)
            measure_rows = []
            for key, val in measures.items():
                if key.endswith("_unit"):
                    continue
                unit = measures.get(f"{key}_unit", "mm^3")
                measure_rows.append([key, val, unit])
            if measure_rows:
                sheets.append(CSVSheet(
                    name="Brain Volumes Summary",
                    filename="brain_volumes_summary.csv",
                    description="Global brain volume measures from aseg.stats",
                    headers=["Measure", "Value", "Unit"],
                    rows=measure_rows,
                    category="volumetric",
                ))

            if table_rows and headers:
                sheets.append(CSVSheet(
                    name="Subcortical Volumes",
                    filename="subcortical_volumes.csv",
                    description="Volume and intensity stats for subcortical structures",
                    headers=headers,
                    rows=table_rows,
                    category="volumetric",
                ))

    # --- cortical_parcellation_DK.csv (lh + rh aparc.stats merged) ---
    sheets.extend(_merge_hemispheric_stats(
        contents, stats_files,
        "lh.aparc.stats", "rh.aparc.stats",
        "Cortical Parcellation (Desikan-Killiany)",
        "cortical_parcellation_DK.csv",
        "Cortical region surface area, volume, and thickness (DK atlas)",
        "cortical",
    ))

    # --- cortical_parcellation_Destrieux.csv ---
    sheets.extend(_merge_hemispheric_stats(
        contents, stats_files,
        "lh.aparc.a2009s.stats", "rh.aparc.a2009s.stats",
        "Cortical Parcellation (Destrieux)",
        "cortical_parcellation_Destrieux.csv",
        "Cortical region stats from the Destrieux (a2009s) atlas",
        "cortical",
    ))

    # --- white_matter_parcellation.csv ---
    wmparc_files = [f for f in stats_files if f.lower().endswith("wmparc.stats")]
    if wmparc_files:
        text = contents.get(wmparc_files[0], "")
        if text:
            _, headers, table_rows = _parse_stats_text(text)
            if table_rows and headers:
                sheets.append(CSVSheet(
                    name="White Matter Parcellation",
                    filename="white_matter_parcellation.csv",
                    description="White matter volumes per cortical region",
                    headers=headers,
                    rows=table_rows,
                    category="volumetric",
                ))

    # --- brodmann_areas.csv ---
    sheets.extend(_merge_hemispheric_stats(
        contents, stats_files,
        "lh.BA_exvivo.stats", "rh.BA_exvivo.stats",
        "Brodmann Areas",
        "brodmann_areas.csv",
        "Brodmann area thickness and volume estimates",
        "cortical",
    ))

    return sheets


def convert_fastsurfer(fp: FileProvider) -> list[CSVSheet]:
    """FastSurfer: aseg + aparc DK (subset of recon-all outputs)."""
    sheets: list[CSVSheet] = []

    stats_files = fp.find_files(
        "aseg.stats", "lh.aparc.stats", "rh.aparc.stats",
    )
    contents = fp.batch_read(stats_files)

    aseg_files = [f for f in stats_files if f.lower().endswith("aseg.stats")]
    if aseg_files:
        text = contents.get(aseg_files[0], "")
        if text:
            measures, headers, table_rows = _parse_stats_text(text)
            measure_rows = []
            for key, val in measures.items():
                if key.endswith("_unit"):
                    continue
                unit = measures.get(f"{key}_unit", "mm^3")
                measure_rows.append([key, val, unit])
            if measure_rows:
                sheets.append(CSVSheet(
                    name="Brain Volumes Summary",
                    filename="brain_volumes_summary.csv",
                    description="Global brain volume measures from FastSurfer aseg.stats",
                    headers=["Measure", "Value", "Unit"],
                    rows=measure_rows,
                    category="volumetric",
                ))
            if table_rows and headers:
                sheets.append(CSVSheet(
                    name="Subcortical Volumes",
                    filename="subcortical_volumes.csv",
                    description="FastSurfer subcortical structure volumes",
                    headers=headers,
                    rows=table_rows,
                    category="volumetric",
                ))

    sheets.extend(_merge_hemispheric_stats(
        contents, stats_files,
        "lh.aparc.stats", "rh.aparc.stats",
        "Cortical Parcellation (Desikan-Killiany)",
        "cortical_parcellation_DK.csv",
        "FastSurfer cortical region stats (DK atlas)",
        "cortical",
    ))

    return sheets


def convert_freesurfer_volonly(fp: FileProvider) -> list[CSVSheet]:
    """FreeSurfer Volumetric: aseg.stats only (no surfaces)."""
    sheets: list[CSVSheet] = []

    stats_files = fp.find_files("aseg.stats")
    contents = fp.batch_read(stats_files)

    if stats_files:
        text = contents.get(stats_files[0], "")
        if text:
            measures, headers, table_rows = _parse_stats_text(text)
            measure_rows = []
            for key, val in measures.items():
                if key.endswith("_unit"):
                    continue
                unit = measures.get(f"{key}_unit", "mm^3")
                measure_rows.append([key, val, unit])
            if measure_rows:
                sheets.append(CSVSheet(
                    name="Brain Volumes Summary",
                    filename="brain_volumes_summary.csv",
                    description="Global brain volume measures (volumetric-only pipeline)",
                    headers=["Measure", "Value", "Unit"],
                    rows=measure_rows,
                    category="volumetric",
                ))
            if table_rows and headers:
                sheets.append(CSVSheet(
                    name="Subcortical Volumes",
                    filename="subcortical_volumes.csv",
                    description="Subcortical structure volumes (volumetric-only pipeline)",
                    headers=headers,
                    rows=table_rows,
                    category="volumetric",
                ))

    return sheets


def convert_freesurfer_longitudinal(fp: FileProvider) -> list[CSVSheet]:
    """FreeSurfer Longitudinal: per-timepoint aseg + aparc with change tracking."""
    sheets: list[CSVSheet] = []
    all_files = fp.list_files()

    # Identify longitudinal directories: pattern like *.long.*
    tp_aseg_files = [
        f for f in all_files
        if "long" in f.lower() and f.lower().endswith("aseg.stats")
    ]
    if not tp_aseg_files:
        tp_aseg_files = [f for f in all_files if f.lower().endswith("aseg.stats")]

    if not tp_aseg_files:
        return sheets

    contents = fp.batch_read(tp_aseg_files)

    # --- longitudinal_subcortical_volumes.csv ---
    combined_headers: list[str] = []
    combined_rows: list[list[Any]] = []
    baseline_vols: dict[str, float] = {}

    for i, aseg_path in enumerate(sorted(tp_aseg_files)):
        parts = PurePosixPath(aseg_path).parts
        tp_id = parts[0] if len(parts) > 2 else f"timepoint_{i + 1}"

        text = contents.get(aseg_path, "")
        if not text:
            continue
        _, headers, table_rows = _parse_stats_text(text)
        if not headers or not table_rows:
            continue

        if not combined_headers:
            combined_headers = ["Timepoint"] + headers

        vol_col_idx = None
        name_col_idx = 0
        for ci, h in enumerate(headers):
            if h.lower() in ("volume_mm3", "volume"):
                vol_col_idx = ci
                break

        for row in table_rows:
            combined_rows.append([tp_id] + row)
            if i == 0 and vol_col_idx is not None:
                name = str(row[name_col_idx])
                try:
                    baseline_vols[name] = float(row[vol_col_idx])
                except (ValueError, IndexError):
                    pass

    if combined_rows:
        sheets.append(CSVSheet(
            name="Longitudinal Subcortical Volumes",
            filename="longitudinal_subcortical_volumes.csv",
            description="Subcortical volumes across timepoints",
            headers=combined_headers,
            rows=combined_rows,
            category="longitudinal",
        ))

    # --- longitudinal_change_summary.csv ---
    if baseline_vols and len(tp_aseg_files) > 1:
        last_text = contents.get(sorted(tp_aseg_files)[-1], "")
        if last_text:
            _, headers, last_rows = _parse_stats_text(last_text)
            vol_col_idx = None
            for ci, h in enumerate(headers):
                if h.lower() in ("volume_mm3", "volume"):
                    vol_col_idx = ci
                    break
            if vol_col_idx is not None:
                change_rows: list[list[Any]] = []
                for row in last_rows:
                    name = str(row[0])
                    if name in baseline_vols and baseline_vols[name] > 0:
                        try:
                            latest = float(row[vol_col_idx])
                            pct = ((latest - baseline_vols[name]) / baseline_vols[name]) * 100
                            change_rows.append([
                                name,
                                round(baseline_vols[name], 2),
                                round(latest, 2),
                                round(latest - baseline_vols[name], 2),
                                round(pct, 3),
                            ])
                        except (ValueError, TypeError):
                            continue
                if change_rows:
                    sheets.append(CSVSheet(
                        name="Longitudinal Change Summary",
                        filename="longitudinal_change_summary.csv",
                        description="Percent volume change from baseline to latest timepoint",
                        headers=["Structure", "Baseline_mm3", "Latest_mm3", "Change_mm3", "Pct_Change"],
                        rows=change_rows,
                        category="longitudinal",
                    ))

    # --- longitudinal cortical thickness ---
    tp_aparc_files = [
        f for f in all_files
        if f.lower().endswith(("lh.aparc.stats", "rh.aparc.stats"))
    ]
    if tp_aparc_files:
        lh_files = sorted(f for f in tp_aparc_files if "lh.aparc" in f.lower())
        rh_files = sorted(f for f in tp_aparc_files if "rh.aparc" in f.lower())
        aparc_contents = fp.batch_read(tp_aparc_files)

        thick_headers = ["Timepoint", "Region", "Hemisphere", "ThickAvg_mm", "SurfArea_mm2", "GrayVol_mm3"]
        thick_rows: list[list[Any]] = []

        for hemi_label, file_list in [("lh", lh_files), ("rh", rh_files)]:
            for i, fpath in enumerate(file_list):
                parts = PurePosixPath(fpath).parts
                tp_id = parts[0] if len(parts) > 2 else f"timepoint_{i + 1}"
                text = aparc_contents.get(fpath, "")
                if not text:
                    continue
                _, headers, rows = _parse_stats_text(text)
                if not headers or not rows:
                    continue

                h_map = {h.lower(): idx for idx, h in enumerate(headers)}
                name_idx = h_map.get("structurename", h_map.get("structname", 0))
                thick_idx = h_map.get("thickavg")
                area_idx = h_map.get("surfarea")
                vol_idx = h_map.get("grayvol")

                for row in rows:
                    thick_rows.append([
                        tp_id,
                        row[name_idx] if name_idx < len(row) else "",
                        hemi_label,
                        row[thick_idx] if thick_idx is not None and thick_idx < len(row) else "",
                        row[area_idx] if area_idx is not None and area_idx < len(row) else "",
                        row[vol_idx] if vol_idx is not None and vol_idx < len(row) else "",
                    ])

        if thick_rows:
            sheets.append(CSVSheet(
                name="Longitudinal Cortical Thickness",
                filename="longitudinal_cortical_thickness.csv",
                description="Cortical thickness and volume across timepoints",
                headers=thick_headers,
                rows=thick_rows,
                category="longitudinal",
            ))

    return sheets


def convert_freesurfer_longitudinal_stats(fp: FileProvider) -> list[CSVSheet]:
    """Longitudinal Stats Utility: extracted per-timepoint aseg + summary JSON."""
    return convert_freesurfer_longitudinal(fp)


def convert_segmentha_t1(fp: FileProvider) -> list[CSVSheet]:
    """SegmentHA_T1: hippocampal subfield volumes from T1."""
    return _convert_hippo_subfields(fp, "T1", "hippoSfVolumes-T1")


def convert_segmentha_t2(fp: FileProvider) -> list[CSVSheet]:
    """SegmentHA_T2: hippocampal subfield volumes from T1+T2."""
    return _convert_hippo_subfields(fp, "T1T2", "hippoSfVolumes-T1T2")


def _convert_hippo_subfields(
    fp: FileProvider, label: str, pattern: str,
) -> list[CSVSheet]:
    hippo_files = fp.find_files(f"lh.{pattern}", f"rh.{pattern}")
    if not hippo_files:
        return []

    contents = fp.batch_read(hippo_files)
    rows: list[list[Any]] = []

    for hemi in ("lh", "rh"):
        hemi_file = next(
            (f for f in hippo_files if PurePosixPath(f).name.lower().startswith(f"{hemi}.")),
            None,
        )
        if not hemi_file:
            continue
        text = contents.get(hemi_file, "")
        if not text:
            continue
        entries = _parse_hippo_volumes_text(text)
        for subfield, vol in entries:
            rows.append([subfield, hemi, round(vol, 4)])

    if not rows:
        return []

    return [CSVSheet(
        name=f"Hippocampal Subfields ({label})",
        filename=f"hippocampal_subfields_{label}.csv",
        description=f"Hippocampal subfield volumes estimated from {label} images",
        headers=["Subfield", "Hemisphere", "Volume_mm3"],
        rows=rows,
        category="hippocampal",
    )]


def convert_hs_postprocess(fp: FileProvider) -> list[CSVSheet]:
    """HS Detection Postprocess: hippocampal sclerosis metrics."""
    metric_files = fp.find_files("hs_metrics.json")
    if not metric_files:
        return []

    contents = fp.batch_read(metric_files)
    text = contents.get(metric_files[0], "")
    if not text:
        return []

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    rows: list[list[Any]] = []
    unit_map = {
        "volume": "mm^3", "asymmetry": "ratio", "z_score": "z",
        "lateralization": "", "classification": "",
    }

    for key, val in data.items():
        if isinstance(val, dict):
            for sub_key, sub_val in val.items():
                full_key = f"{key}_{sub_key}"
                unit = _guess_unit(full_key, unit_map)
                interp = _interpret_hs_metric(full_key, sub_val)
                rows.append([full_key, sub_val, unit, interp])
        else:
            unit = _guess_unit(key, unit_map)
            interp = _interpret_hs_metric(key, val)
            rows.append([key, val, unit, interp])

    if not rows:
        return []

    return [CSVSheet(
        name="HS Detection Results",
        filename="hs_detection_results.csv",
        description="Hippocampal sclerosis detection metrics and classification",
        headers=["Metric", "Value", "Unit", "Interpretation"],
        rows=rows,
        category="clinical",
    )]


def _guess_unit(key: str, unit_map: dict[str, str]) -> str:
    key_l = key.lower()
    for pattern, unit in unit_map.items():
        if pattern in key_l:
            return unit
    return ""


def _interpret_hs_metric(key: str, val: Any) -> str:
    key_l = key.lower()
    if "asymmetry" in key_l and isinstance(val, (int, float)):
        if abs(val) < 0.05:
            return "Symmetric"
        return "Left > Right" if val > 0 else "Right > Left"
    if "z_score" in key_l and isinstance(val, (int, float)):
        if abs(val) > 2.0:
            return "Abnormal"
        if abs(val) > 1.5:
            return "Borderline"
        return "Normal"
    if "classification" in key_l:
        return str(val)
    return ""


def convert_meld_graph(fp: FileProvider) -> list[CSVSheet]:
    """MELD Graph: lesion prediction metrics."""
    metric_files = fp.find_files("metrics.json", "predictions")
    if not metric_files:
        return []

    json_files = [f for f in metric_files if f.lower().endswith(".json")]
    if not json_files:
        return []

    contents = fp.batch_read(json_files)
    rows: list[list[Any]] = []

    for jf in json_files:
        text = contents.get(jf, "")
        if not text:
            continue
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    rows.append([
                        item.get("cluster_id", ""),
                        item.get("hemisphere", ""),
                        item.get("num_vertices", ""),
                        item.get("area_mm2", ""),
                        item.get("prediction_score", item.get("score", "")),
                        item.get("location", ""),
                        item.get("classification", item.get("label", "")),
                    ])
        elif isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, dict):
                    rows.append([
                        val.get("cluster_id", key),
                        val.get("hemisphere", ""),
                        val.get("num_vertices", ""),
                        val.get("area_mm2", ""),
                        val.get("prediction_score", val.get("score", "")),
                        val.get("location", ""),
                        val.get("classification", val.get("label", "")),
                    ])
                else:
                    rows.append([key, "", "", "", val, "", ""])

    if not rows:
        return []

    return [CSVSheet(
        name="MELD Predictions",
        filename="meld_predictions.csv",
        description="Cortical lesion predictions from MELD Graph",
        headers=["Cluster_ID", "Hemisphere", "Num_Vertices", "Area_mm2",
                 "Prediction_Score", "Location", "Classification"],
        rows=rows,
        category="clinical",
    )]


def convert_tsc_segmentation_tsccnn3d(fp: FileProvider) -> list[CSVSheet]:
    """TSC Segmentation: parse tuber burden metrics from volume_results.txt."""
    metric_files = fp.find_files("volume_results.txt")
    if not metric_files:
        return []

    contents = fp.batch_read(metric_files)
    text = contents.get(metric_files[0], "") or ""
    if not text.strip():
        return []

    rows: list[list[Any]] = []
    for ln in (line.strip() for line in text.splitlines()):
        if not ln:
            continue

        if ":" in ln:
            key, raw_val = [p.strip() for p in ln.split(":", 1)]
        elif "=" in ln:
            key, raw_val = [p.strip() for p in ln.split("=", 1)]
        elif "," in ln:
            parts = [p.strip() for p in ln.split(",", 1)]
            if len(parts) != 2:
                continue
            key, raw_val = parts
        else:
            continue

        m = re.match(r"^\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*(.*)$", raw_val)
        if not m:
            continue
        try:
            value: Any = float(m.group(1))
        except ValueError:
            continue
        unit = (m.group(2) or "").strip()

        rows.append([key, value, unit])

    if not rows:
        return []

    # Some runs write the same summary block twice; keep first occurrence only.
    deduped_rows: list[list[Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for row in rows:
        key = (row[0], row[1], row[2])
        if key in seen:
            continue
        seen.add(key)
        deduped_rows.append(row)

    return [CSVSheet(
        name="TSC Segmentation Metrics",
        filename="tsc_segmentation_metrics.csv",
        description="TSCCNN3D tuber burden metrics parsed from volume_results.txt",
        headers=["Metric", "Value", "Unit"],
        rows=deduped_rows,
        category="epilepsy",
    )]


def convert_fmriprep(fp: FileProvider) -> list[CSVSheet]:
    """fMRIPrep: motion and confound summaries from confounds_timeseries.tsv."""
    sheets: list[CSVSheet] = []
    confound_files = fp.find_files("confounds_timeseries.tsv")
    if not confound_files:
        return sheets

    contents = fp.batch_read(confound_files)

    KEY_CONFOUNDS = [
        "framewise_displacement", "dvars", "std_dvars",
        "trans_x", "trans_y", "trans_z",
        "rot_x", "rot_y", "rot_z",
        "csf", "white_matter", "global_signal",
    ]

    # --- fmriprep_motion_summary.csv (1 row per run) ---
    motion_rows: list[list[Any]] = []
    confound_summary_data: dict[str, list[float]] = {}

    for run_idx, cf_path in enumerate(sorted(confound_files)):
        text = contents.get(cf_path, "")
        if not text:
            continue

        run_name = _extract_run_label(cf_path, run_idx)
        headers, rows = _parse_tsv_text(text)
        if not headers or not rows:
            continue

        h_map = {h.lower(): i for i, h in enumerate(headers)}

        fd_vals = _extract_column(rows, h_map.get("framewise_displacement"))
        dvars_vals = _extract_column(rows, h_map.get("dvars"))

        fd_mean = _safe_mean(fd_vals)
        fd_max = _safe_max(fd_vals)
        fd_median = _safe_median(fd_vals)
        dvars_mean = _safe_mean(dvars_vals)
        dvars_max = _safe_max(dvars_vals)
        n_vols = len(rows)
        pct_outlier = (sum(1 for v in fd_vals if v > 0.5) / len(fd_vals) * 100) if fd_vals else 0

        motion_rows.append([
            run_name,
            _r(fd_mean), _r(fd_max), _r(fd_median),
            _r(dvars_mean), _r(dvars_max),
            _r(pct_outlier), n_vols,
        ])

        for confound in KEY_CONFOUNDS:
            idx = h_map.get(confound)
            vals = _extract_column(rows, idx)
            if vals:
                confound_summary_data.setdefault(confound, []).extend(vals)

    if motion_rows:
        sheets.append(CSVSheet(
            name="fMRIPrep Motion Summary",
            filename="fmriprep_motion_summary.csv",
            description="Per-run motion quality metrics",
            headers=["Run", "FD_mean", "FD_max", "FD_median",
                     "DVARS_mean", "DVARS_max", "Pct_Outlier_Volumes", "N_Volumes"],
            rows=motion_rows,
            category="quality",
        ))

    # --- fmriprep_confounds_summary.csv ---
    if confound_summary_data:
        summary_rows: list[list[Any]] = []
        for confound, vals in confound_summary_data.items():
            summary_rows.append([
                confound,
                _r(_safe_mean(vals)), _r(_safe_std(vals)),
                _r(min(vals)), _r(max(vals)), _r(_safe_median(vals)),
            ])
        sheets.append(CSVSheet(
            name="fMRIPrep Confounds Summary",
            filename="fmriprep_confounds_summary.csv",
            description="Statistical summary of key confound regressors",
            headers=["Confound", "Mean", "Std", "Min", "Max", "Median"],
            rows=summary_rows,
            category="quality",
        ))

    return sheets


def convert_xcpd(fp: FileProvider) -> list[CSVSheet]:
    """XCP-D: functional connectivity matrices and parcellated timeseries."""
    sheets: list[CSVSheet] = []

    conn_files = fp.find_files("connectivity", "correlations")
    conn_files = [f for f in conn_files if f.lower().endswith((".tsv", ".csv"))]
    ts_files = fp.find_files("timeseries")
    ts_files = [f for f in ts_files if f.lower().endswith((".tsv", ".csv"))]

    # --- functional_connectivity_matrix.csv ---
    if conn_files:
        contents = fp.batch_read(conn_files[:1])
        text = contents.get(conn_files[0], "")
        if text:
            sep = "," if conn_files[0].lower().endswith(".csv") else "\t"
            lines = text.strip().splitlines()
            if lines:
                headers = lines[0].split(sep)
                rows: list[list[Any]] = []
                for line in lines[1:]:
                    cols = line.split(sep)
                    row: list[Any] = []
                    for v in cols:
                        v = v.strip()
                        try:
                            row.append(round(float(v), 6))
                        except ValueError:
                            row.append(v)
                    rows.append(row)
                if rows:
                    sheets.append(CSVSheet(
                        name="Functional Connectivity Matrix",
                        filename="functional_connectivity_matrix.csv",
                        description="ROI-to-ROI functional connectivity (Fisher-Z)",
                        headers=headers,
                        rows=rows,
                        category="connectivity",
                    ))

    # --- parcellated_timeseries_summary.csv ---
    if ts_files:
        contents = fp.batch_read(ts_files[:1])
        text = contents.get(ts_files[0], "")
        if text:
            headers_ts, rows_ts = _parse_tsv_text(text)
            if headers_ts and rows_ts:
                summary_rows: list[list[Any]] = []
                for ci, roi_name in enumerate(headers_ts):
                    vals = _extract_column(rows_ts, ci)
                    if vals:
                        mean_v = _safe_mean(vals)
                        std_v = _safe_std(vals)
                        snr = (mean_v / std_v) if std_v > 0 else 0
                        summary_rows.append([
                            roi_name,
                            _r(mean_v), _r(std_v),
                            _r(min(vals)), _r(max(vals)),
                            _r(snr),
                        ])
                if summary_rows:
                    sheets.append(CSVSheet(
                        name="Parcellated Timeseries Summary",
                        filename="parcellated_timeseries_summary.csv",
                        description="Per-ROI BOLD signal summary statistics",
                        headers=["ROI", "Mean", "Std", "Min", "Max", "SNR"],
                        rows=summary_rows,
                        category="connectivity",
                    ))

    return sheets


def convert_qsiprep(fp: FileProvider) -> list[CSVSheet]:
    """QSIPrep: diffusion motion/confound summary."""
    confound_files = fp.find_files("confounds")
    confound_files = [f for f in confound_files if f.lower().endswith((".tsv", ".csv"))]
    if not confound_files:
        return []

    contents = fp.batch_read(confound_files)
    motion_rows: list[list[Any]] = []

    for run_idx, cf_path in enumerate(sorted(confound_files)):
        text = contents.get(cf_path, "")
        if not text:
            continue

        run_name = _extract_run_label(cf_path, run_idx)
        headers, rows = _parse_tsv_text(text)
        if not headers or not rows:
            continue

        h_map = {h.lower(): i for i, h in enumerate(headers)}
        fd_vals = _extract_column(rows, h_map.get("framewise_displacement"))

        fd_mean = _safe_mean(fd_vals)
        fd_max = _safe_max(fd_vals)
        n_vols = len(rows)
        pct_outlier = (sum(1 for v in fd_vals if v > 0.5) / len(fd_vals) * 100) if fd_vals else 0

        motion_rows.append([
            run_name, _r(fd_mean), _r(fd_max), _r(pct_outlier), n_vols,
        ])

    if not motion_rows:
        return []

    return [CSVSheet(
        name="Diffusion Motion Summary",
        filename="diffusion_motion_summary.csv",
        description="Per-run DWI motion quality metrics",
        headers=["Run", "FD_mean", "FD_max", "Pct_Outlier_Volumes", "N_Volumes"],
        rows=motion_rows,
        category="quality",
    )]


def convert_qsirecon(fp: FileProvider) -> list[CSVSheet]:
    """QSIRecon: structural connectivity matrix."""
    conn_files = fp.find_files("connectome")
    conn_files = [f for f in conn_files if f.lower().endswith((".csv", ".tsv"))]
    if not conn_files:
        return []

    contents = fp.batch_read(conn_files[:1])
    text = contents.get(conn_files[0], "")
    if not text:
        return []

    sep = "," if conn_files[0].lower().endswith(".csv") else "\t"
    lines = text.strip().splitlines()
    if not lines:
        return []

    headers = lines[0].split(sep)
    rows: list[list[Any]] = []
    for line in lines[1:]:
        cols = line.split(sep)
        row: list[Any] = []
        for v in cols:
            v = v.strip()
            try:
                row.append(round(float(v), 4))
            except ValueError:
                row.append(v)
        rows.append(row)

    if not rows:
        return []

    return [CSVSheet(
        name="Structural Connectivity Matrix",
        filename="structural_connectivity_matrix.csv",
        description="Structural connectome (streamline counts or mean FA)",
        headers=headers,
        rows=rows,
        category="connectivity",
    )]


# --------------------------------------------------------------------------- #
#  Hemispheric merge helper                                                    #
# --------------------------------------------------------------------------- #

def _merge_hemispheric_stats(
    contents: dict[str, str],
    file_list: list[str],
    lh_suffix: str,
    rh_suffix: str,
    sheet_name: str,
    filename: str,
    description: str,
    category: str,
) -> list[CSVSheet]:
    """Merge left/right hemisphere .stats files into a single CSV with a Hemisphere column."""
    lh_file = next(
        (f for f in file_list if f.lower().endswith(lh_suffix.lower())),
        None,
    )
    rh_file = next(
        (f for f in file_list if f.lower().endswith(rh_suffix.lower())),
        None,
    )

    if not lh_file and not rh_file:
        return []

    merged_headers: list[str] = []
    merged_rows: list[list[Any]] = []

    for hemi_label, fpath in [("lh", lh_file), ("rh", rh_file)]:
        if not fpath:
            continue
        text = contents.get(fpath, "")
        if not text:
            continue
        _, headers, table_rows = _parse_stats_text(text)
        if not headers or not table_rows:
            continue

        if not merged_headers:
            name_col = headers[0]
            merged_headers = [name_col, "Hemisphere"] + headers[1:]

        for row in table_rows:
            merged_rows.append([row[0], hemi_label] + row[1:])

    if not merged_rows:
        return []

    return [CSVSheet(
        name=sheet_name,
        filename=filename,
        description=description,
        headers=merged_headers,
        rows=merged_rows,
        category=category,
    )]


# --------------------------------------------------------------------------- #
#  Numeric helpers                                                             #
# --------------------------------------------------------------------------- #

def _extract_column(rows: list[list[Any]], col_idx: int | None) -> list[float]:
    if col_idx is None:
        return []
    vals: list[float] = []
    for row in rows:
        if col_idx < len(row) and row[col_idx] is not None:
            try:
                v = float(row[col_idx])
                if not math.isnan(v):
                    vals.append(v)
            except (ValueError, TypeError):
                continue
    return vals


def _extract_run_label(path: str, idx: int) -> str:
    match = re.search(r"run-(\w+)", path, re.IGNORECASE)
    if match:
        return f"run-{match.group(1)}"
    match = re.search(r"task-(\w+)", path, re.IGNORECASE)
    if match:
        return f"task-{match.group(1)}"
    return f"run_{idx + 1}"


def _r(val: float | None, digits: int = 4) -> Any:
    if val is None:
        return ""
    return round(val, digits)


def _safe_mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def _safe_median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def _safe_max(vals: list[float]) -> float | None:
    return max(vals) if vals else None


def _safe_std(vals: list[float]) -> float | None:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


# --------------------------------------------------------------------------- #
#  Main entry point                                                            #
# --------------------------------------------------------------------------- #

CONVERTER_REGISTRY: dict[str, Any] = {
    "freesurfer_recon": convert_freesurfer_recon,
    "fastsurfer": convert_fastsurfer,
    "freesurfer_volonly": convert_freesurfer_volonly,
    "freesurfer_longitudinal": convert_freesurfer_longitudinal,
    "freesurfer_longitudinal_stats": convert_freesurfer_longitudinal_stats,
    "segmentha_t1": convert_segmentha_t1,
    "segmentha_t2": convert_segmentha_t2,
    "hs_postprocess": convert_hs_postprocess,
    "meld_graph": convert_meld_graph,
    "tsc_segmentation_tsccnn3d": convert_tsc_segmentation_tsccnn3d,
    "fmriprep": convert_fmriprep,
    "xcpd": convert_xcpd,
    "qsiprep": convert_qsiprep,
    "qsirecon": convert_qsirecon,
}


def generate_stats_csvs(
    pipeline_name: str,
    fp: FileProvider,
) -> list[CSVSheet]:
    """
    Generate all applicable CSVs for a given pipeline.

    For workflow pipelines, runs converters for each component step and
    de-duplicates by filename (later steps win on conflicts).
    """
    sheets: list[CSVSheet] = []

    # Check if it's a workflow first
    wf_steps = get_workflow_steps(pipeline_name)
    if wf_steps:
        seen_filenames: set[str] = set()
        for step_id in wf_steps:
            converter = CONVERTER_REGISTRY.get(step_id)
            if converter:
                try:
                    step_sheets = converter(fp)
                    for s in step_sheets:
                        if s.filename not in seen_filenames:
                            sheets.append(s)
                            seen_filenames.add(s.filename)
                except Exception as e:
                    logger.warning("Converter %s failed: %s", step_id, e)
        return sheets

    # Single plugin
    converter_id = get_converter_id(pipeline_name)
    if converter_id:
        converter = CONVERTER_REGISTRY.get(converter_id)
        if converter:
            try:
                sheets = converter(fp)
            except Exception as e:
                logger.warning("Converter %s failed: %s", converter_id, e)
    else:
        # Unknown pipeline -- try all FreeSurfer-like converters as a heuristic
        for fallback_id in ("freesurfer_recon", "fastsurfer", "freesurfer_volonly"):
            converter = CONVERTER_REGISTRY.get(fallback_id)
            if converter:
                try:
                    result = converter(fp)
                    if result:
                        sheets = result
                        break
                except Exception:
                    continue

    return sheets
