# NeuroInsight documentation

**Developed by Philbert Ndagijimana** with **URMC researchers and neurologists**.
NeuroInsight orchestrates neuroimaging pipelines; at URMC it supports **Radiology**
workflows — see [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md).

## Start here

| You are… | Read |
|----------|------|
| **Engineer / technical reviewer** | **[ENGINEERING.md](ENGINEERING.md)** |
| **Installing the desktop app** | [INSTALL.md](INSTALL.md) |
| **Using HPC, Pennsieve, XNAT** | [USER_GUIDE.md](USER_GUIDE.md) |
| **Clinical deployment context (URMC)** | [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) |

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
| [INSTALL.md](INSTALL.md) | Download, verify, first launch |
| [DESKTOP_UPDATES.md](DESKTOP_UPDATES.md) | Auto-update, engine refresh |
| [CLINICAL_SUPPORT.md](CLINICAL_SUPPORT.md) | URMC Radiology support workflows |
| [REFERENCES.md](REFERENCES.md) | Citations (regenerate via `scripts/generate_references_doc.py`) |
| [TOOL_LICENSES.md](TOOL_LICENSES.md) | FreeSurfer / MELD files |

### Maintainers

| Doc | Purpose |
|-----|---------|
| [RELEASING.md](RELEASING.md) | Version tags, GHCR image, desktop release |
| [SIGNING_AND_TRUST.md](SIGNING_AND_TRUST.md) | Code signing, checksums |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../desktop/README.md](../desktop/README.md) | Electron build |

Connector registration scripts: `adapters/scripts/` (not end-user facing).
