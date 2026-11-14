# NeuroInsight documentation

**Developed by Philbert Ndagijimana** with **URMC researchers and neurologists**.

**Web site (MkDocs):** run `pip install -r requirements-docs.txt && mkdocs serve`,
or host on [Read the Docs](https://readthedocs.org) — see [BUILDING_DOCS.md](BUILDING_DOCS.md).
Landing page: [index.md](index.md) · How it works: [HOW_IT_WORKS.md](HOW_IT_WORKS.md) ·
Build: [BUILDING_DOCS.md](BUILDING_DOCS.md).

## Start here

| You are… | Read |
|----------|------|
| **Documentation website** | **[index.md](index.md)** · **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)** (`mkdocs serve`) |
| **What the product is** | **[PRODUCT.md](PRODUCT.md)** |
| **Supported platforms / limits** | **[COMPATIBILITY.md](COMPATIBILITY.md)** |
| **Engineer / technical reviewer** | **[ENGINEERING.md](ENGINEERING.md)** |
| **Installing the desktop app** | [INSTALL.md](INSTALL.md) |
| **Using HPC, Pennsieve, XNAT** | [USER_GUIDE.md](USER_GUIDE.md) — start with **10-minute path** |
| **URMC use cases (Radiology & Neurology)** | **[USE_CASES.md](USE_CASES.md)** |
| **Clinical deployment context (URMC)** | [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) |
| **TRACK-TBI cohort / DoD report** | [TRACK_TBI.md](TRACK_TBI.md) |

## All guides

### Engineering & operations

| Doc | Purpose |
|-----|---------|
| [ENGINEERING.md](ENGINEERING.md) | Architecture, repo map, run, test — **primary engineer onboarding** |
| [../QUICK_START.md](../QUICK_START.md) | `./research` command cheat sheet |
| [TRANSFER.md](TRANSFER.md) | Transfer matrix, large files, env vars |
| [USER_GUIDE.md](USER_GUIDE.md) | Connectors, SLURM, remote server, source deploy |
| [HPC_PIPELINE_SUBMISSION_GUIDE.md](HPC_PIPELINE_SUBMISSION_GUIDE.md) | Input layouts per workflow |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common failures |

### Product & trust

| Doc | Purpose |
|-----|---------|
| [PRODUCT.md](PRODUCT.md) | Scope, support model, supported vs experimental |
| [COMPATIBILITY.md](COMPATIBILITY.md) | OS, SLURM, Pennsieve/arch matrix |
| [RELEASE_NOTES_v0.1.25.md](RELEASE_NOTES_v0.1.25.md) | Latest release summary |
| [INSTALL.md](INSTALL.md) | Download, verify, first launch |
| [DESKTOP_UPDATES.md](DESKTOP_UPDATES.md) | Auto-update, engine refresh |
| [USE_CASES.md](USE_CASES.md) | URMC Radiology & Neurology workflows (AI + classical) |
| [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) | URMC deployment context |
| [REFERENCES.md](REFERENCES.md) | Citations (regenerate via `scripts/generate_references_doc.py`) |
| [TOOL_LICENSES.md](TOOL_LICENSES.md) | FreeSurfer / MELD files |

### Maintainers

| Doc | Purpose |
|-----|---------|
| [MAINTAINER.md](MAINTAINER.md) | What is public site vs repo-only vs `local/` |
| [BUILDING_DOCS.md](BUILDING_DOCS.md) | MkDocs / Read the Docs |
| [RELEASING.md](RELEASING.md) | Version tags, GHCR image, desktop release |
| [SIGNING_AND_TRUST.md](SIGNING_AND_TRUST.md) | Code signing, checksums |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../desktop/README.md](../desktop/README.md) | Electron build |

Connector registration scripts: `adapters/scripts/` (not end-user facing).
