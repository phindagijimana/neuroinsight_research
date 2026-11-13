#!/usr/bin/env python3
"""Generate docs/REFERENCES.md from plugin and pipeline YAML definitions.

Usage (from repo root):
    python3 scripts/generate_references_doc.py

Regenerate after adding or changing `references:` or container images in
plugins/*.yaml or pipelines/*.yaml.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
PIPELINES_DIR = ROOT / "pipelines"
OUT_PATH = ROOT / "docs" / "REFERENCES.md"

PLATFORM_SECTION = """\
## Clinical deployment

URMC: NeuroInsight runs production workflows that support Radiology. See
[CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) (scope, limitations, citations).

## NeuroInsight application stack

NeuroInsight (this repository) is the orchestration layer — web UI, job
scheduling, data transfer, and HPC/SSH/Docker backends. It is **not** a
replacement for citing the neuroimaging tools you actually run.

| Component | Role | Citation / license |
|-----------|------|-------------------|
| NeuroInsight | Platform (MIT) | [CITATION.cff](../CITATION.cff), BibTeX below |
| FastAPI, Uvicorn | HTTP API | https://fastapi.tiangolo.com/ |
| Celery, Redis | Background jobs (optional) | Celery project docs |
| PostgreSQL, SQLAlchemy | Job/metadata store | Standard software acknowledgments |
| React, Vite, TypeScript | Desktop/web UI | Standard software acknowledgments |
| Electron | Desktop shell | https://www.electronjs.org/ |
| Docker / Apptainer-Singularity | Container execution | Cite **container images** in plugin YAML |
| Paramiko | SSH remote execution | Paramiko docs |
| SLURM | HPC batch scheduler | Schultz et al., 2003 (SLURM) if your site requires it |
| MinIO (optional) | S3-compatible staging | MinIO docs |
| Pennsieve connector | `pennsieve2`, AWS Cognito | https://docs.pennsieve.io/ — cite Pennsieve if you publish data there |
| XNAT connector | REST adapter | https://xnat.org/ — cite XNAT if used for archiving |

Tool **license files** (FreeSurfer, MELD, etc.) are separate from literature:
see [TOOL_LICENSES.md](TOOL_LICENSES.md).
"""

CITING_SECTION = """\
## Citing NeuroInsight

If you use this platform in a publication, cite the software:

Developed by **Philbert Ndagijimana** with **URMC researchers and neurologists**.
Technical overview: [ENGINEERING.md](ENGINEERING.md).

```bibtex
@software{neuroinsight,
  author       = {Ndagijimana, Philbert and URMC collaborators},
  title        = {NeuroInsight: Neuroimaging Pipeline Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  version      = {VERSION},
  note         = {Developed in collaboration with URMC researchers and neurologists}
}
```

Also cite **each pipeline plugin you ran** (sections below) and any licenses
required by those tools.
"""


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _container_image(data: dict[str, Any]) -> str | None:
    container = data.get("container")
    if isinstance(container, dict):
        image = container.get("image")
        if image:
            return str(image)
    legacy = data.get("container_image")
    if legacy:
        return str(legacy)
    return None


def _collect_entries(directory: Path, kind: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not directory.is_dir():
        return entries
    for path in sorted(directory.glob("*.yaml")):
        data = _load_yaml(path)
        entry_id = data.get("id") or path.stem
        refs = data.get("references") or []
        if not isinstance(refs, list):
            refs = []
        refs = [str(r).strip() for r in refs if r]
        entries.append(
            {
                "kind": kind,
                "id": str(entry_id),
                "name": str(data.get("name") or entry_id),
                "domain": str(data.get("domain") or "other"),
                "version": data.get("version"),
                "image": _container_image(data),
                "references": refs,
                "source": path.relative_to(ROOT).as_posix(),
            }
        )
    return entries


def _format_plugin_block(entry: dict[str, Any]) -> str:
    lines = [
        f"#### {entry['name']} (`{entry['id']}`)",
        "",
        f"- **Definition:** `{entry['source']}`",
    ]
    if entry.get("version"):
        lines.append(f"- **Plugin version:** {entry['version']}")
    if entry.get("image"):
        lines.append(f"- **Container image:** `{entry['image']}`")
    lines.append("")
    if entry["references"]:
        lines.append("**References:**")
        lines.append("")
        for ref in entry["references"]:
            if ref.startswith("http://") or ref.startswith("https://"):
                lines.append(f"- {ref}")
            else:
                lines.append(f"- {ref}")
    else:
        lines.append(
            "**References:** *(none in YAML)* — cite the underlying method "
            "for the container image above and any upstream tools (e.g. "
            "FreeSurfer, MNE-Python, fMRIPrep)."
        )
    lines.append("")
    return "\n".join(lines)


def build_markdown(version: str) -> str:
    plugins = _collect_entries(PLUGINS_DIR, "plugin")
    pipelines = _collect_entries(PIPELINES_DIR, "pipeline")

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in plugins:
        by_domain[p["domain"]].append(p)

    priority = (
        "structural_mri",
        "functional_mri",
        "diffusion_mri",
        "eeg",
        "eeg_imaging",
    )
    ordered_domains: list[str] = [d for d in priority if d in by_domain]
    for d in sorted(by_domain.keys()):
        if d not in ordered_domains:
            ordered_domains.append(d)

    parts: list[str] = [
        "# References and citations",
        "",
        "Literature and links for **NeuroInsight** and the **pipelines/plugins** "
        "shipped in this repository.",
        "",
        f"> **Generated** by `python3 scripts/generate_references_doc.py` "
        f"(NeuroInsight v{version}). Edit YAML `references:` fields and re-run "
        "the script instead of editing plugin tables below by hand.",
        "",
        CITING_SECTION.replace("{VERSION}", version),
        "",
        "## Plugins by domain",
        "",
        "Use this section in **Methods**: cite NeuroInsight plus every plugin "
        "you executed.",
        "",
    ]

    missing_refs: list[str] = []
    all_refs: set[str] = set()

    for domain in ordered_domains:
        parts.append(f"### Domain: `{domain}`")
        parts.append("")
        parts.append("")
        for entry in sorted(by_domain[domain], key=lambda e: e["name"].lower()):
            parts.append(_format_plugin_block(entry))
            if not entry["references"]:
                missing_refs.append(entry["id"])
            all_refs.update(entry["references"])

    if pipelines:
        parts.append("## Legacy pipeline definitions (`pipelines/`)")
        parts.append("")
        parts.append(
            "These YAML files define older monolithic pipeline specs. "
            "Prefer plugin citations when you run jobs via the plugin registry."
        )
        parts.append("")
        for entry in pipelines:
            parts.append(_format_plugin_block(entry))
            all_refs.update(entry["references"])

    if missing_refs:
        parts.append("## Plugins missing `references:` in YAML")
        parts.append("")
        parts.append(
            "Consider adding citations to the plugin file (shown in the in-app "
            "**Docs** page). Current gaps:"
        )
        parts.append("")
        for pid in sorted(missing_refs):
            parts.append(f"- `{pid}`")
        parts.append("")

    if all_refs:
        parts.append("## Deduplicated bibliography (from YAML)")
        parts.append("")
        parts.append(
            "Alphabetical list of all `references:` strings across plugins "
            "and pipelines (may include duplicates across tools, e.g. "
            "FreeSurfer cited by several plugins)."
        )
        parts.append("")
        for ref in sorted(all_refs, key=str.lower):
            parts.append(f"- {ref}")
        parts.append("")

    parts.append(PLATFORM_SECTION)
    parts.append("")
    return "\n".join(parts)


def main() -> int:
    version_path = ROOT / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "unknown"
    OUT_PATH.write_text(build_markdown(version), encoding="utf-8")
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
