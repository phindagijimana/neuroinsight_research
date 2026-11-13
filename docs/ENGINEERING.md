# NeuroInsight — engineering overview

**For experienced engineers** evaluating or extending this repository.

## About

**NeuroInsight** is a neuroimaging orchestration platform: a web UI and desktop app
that move data (**Transfer**), submit containerized pipelines (**Jobs**), and
monitor execution on **local Docker**, **remote SSH + Docker**, or **HPC / SLURM +
Apptainer**.

It was **developed by Philbert Ndagijimana** in **collaboration with researchers and
neurologists at the University of Rochester Medical Center (URMC)**, where the
platform runs workflows that **support Radiology and related clinical services**
(structural MRI, lesion detection, hippocampal sclerosis, multimodal epilepsy
pipelines). See [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) for scope and
limitations — orchestration only; interpretation stays with clinicians.

| | |
|---|---|
| **License** | MIT (this repo); third-party tools have their own licenses — [TOOL_LICENSES.md](TOOL_LICENSES.md) |
| **Version** | `VERSION` at repo root (also engine/desktop package.json via `scripts/bump_version.py`) |
| **Releases** | [GitHub Releases](https://github.com/phindagijimana/neuroinsight_research/releases) — desktop installer + `ghcr.io/phindagijimana/nir-allinone:v<version>` |

## Architecture (one page)

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/ (React + Vite)  ←→  backend/ (FastAPI)           │
│       │                              │                       │
│       │                    plugin_registry + workflows YAML │
│       │                              │                       │
│       │              execution/: local_docker, remote_docker,│
│       │                        slurm_backend, celery_tasks    │
│       │                              │                       │
│       │              connectors/: pennsieve, xnat, ssh      │
│       │              core/: transfer_manager, transfer_io   │
└───────┼──────────────────────────────┼───────────────────────┘
        │                              │
  desktop/app/ (Electron)         Docker / SSH / SLURM
  optional shell                  neuroimaging containers
```

- **Plugins** — one tool each: `plugins/*.yaml` (image, inputs, SLURM hints, `references`).
- **Workflows** — chained steps: `workflows/*.yaml`.
- **Desktop** — Electron host; bundles or pulls the all-in-one engine image; does not
  replace the backend API contract (`desktop/README.md`).

**Security default:** API on `127.0.0.1`, no multi-user auth — see README § Security.

## Repository map

| Path | Responsibility |
|------|----------------|
| `backend/main.py` | FastAPI app, routes, job submission |
| `backend/core/plugin_registry.py` | Load / validate plugins |
| `backend/core/transfer_manager.py` | Transfer route orchestration |
| `backend/execution/slurm_backend.py` | HPC: SSH, `sbatch`, Singularity |
| `backend/execution/remote_docker_backend.py` | Remote Docker over SSH |
| `backend/connectors/` | Pennsieve, XNAT, platform sessions |
| `frontend/src/` | Transfer, Jobs, Docs, viewer |
| `desktop/app/` | Electron main, engine lifecycle, SSH broker |
| `docker/` | All-in-one engine image build context |
| `tests/` | Backend pytest suite (CI on `main`) |
| `eeg/` | EEG plugin design notes (deep dive) |

## Run from source

**Prerequisites:** Python 3.9+, Node 18+, Docker Compose v2, 8 GB+ RAM.

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research install    # deps, PostgreSQL/Redis/MinIO, DB init
./research license    # FreeSurfer / MELD if needed
./research start      # → http://localhost:3000
```

**Hot reload (development):**

```bash
./research-dev start  # separate API/frontend ports; see script header
```

**Tests (matches CI):**

```bash
pip install -r requirements.txt pytest httpx pytest-cov
PYTHONPATH=. python -m pytest tests/ -v --tb=short
```

**Shutdown:** `./research stop` · **Health:** `./research health`

Full command list: [../QUICK_START.md](../QUICK_START.md).

## Typical engineer tasks

| Task | Where to start |
|------|----------------|
| HPC / SLURM behavior | `backend/execution/slurm_backend.py`, [USER_GUIDE.md](USER_GUIDE.md) § HPC |
| Large file transfer | [TRANSFER.md](TRANSFER.md), `backend/core/transfer_io.py` |
| Add or change a pipeline | New YAML in `plugins/` or `workflows/`; in-app **Docs** tab; run `./research` preflight if available |
| Pipeline citations | `references:` in YAML → `python3 scripts/generate_references_doc.py` → [REFERENCES.md](REFERENCES.md) |
| Desktop / release | [RELEASING.md](RELEASING.md), [../desktop/README.md](../desktop/README.md) |

## Documentation index

All docs: **[docs/README.md](README.md)**. **MkDocs site:** [BUILDING_DOCS.md](BUILDING_DOCS.md) (`mkdocs serve`).

| Audience | Start here |
|----------|------------|
| **Product scope & support** | [PRODUCT.md](PRODUCT.md) |
| **Compatibility matrix** | [COMPATIBILITY.md](COMPATIBILITY.md) |
| **Engineers (this doc)** | [ENGINEERING.md](ENGINEERING.md) |
| **Clinical / URMC context** | [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) |
| **End-user install** | [INSTALL.md](INSTALL.md) |
| **Connectors & deployment** | [USER_GUIDE.md](USER_GUIDE.md) |
| **Methods / bibliography** | [REFERENCES.md](REFERENCES.md) |

## Citation

```bibtex
@software{neuroinsight,
  author       = {Ndagijimana, Philbert and URMC collaborators},
  title        = {NeuroInsight: Neuroimaging Pipeline Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  note         = {Developed in collaboration with URMC researchers and neurologists}
}
```

Also cite each neuroimaging tool you execute — [REFERENCES.md](REFERENCES.md).

## Contact

**Philbert Ndagijimana** — phindagijimana@gmail.com
