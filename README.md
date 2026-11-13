# NeuroInsight

Neuroimaging **orchestration platform**: Transfer data, submit containerized
**plugins** and **workflows**, monitor jobs on local Docker, remote SSH, or HPC/SLURM
— from a browser or desktop app.

**Developed by Philbert Ndagijimana** in **collaboration with researchers and
neurologists at the University of Rochester Medical Center (URMC)**. At URMC,
NeuroInsight runs workflows that **support Radiology** (structural MRI, lesion
detection, hippocampal sclerosis, multimodal epilepsy pipelines). Details:
**[docs/CLINICAL_SUPPORT.md](docs/CLINICAL_SUPPORT.md)**.

| Reader | Start here |
|--------|------------|
| **Experienced engineer** | **[docs/ENGINEERING.md](docs/ENGINEERING.md)** — architecture, repo map, run, test |
| **Desktop end user** | **[docs/INSTALL.md](docs/INSTALL.md)** |
| **Full doc index** | **[docs/README.md](docs/README.md)** |

Extensions are **YAML**: one file per tool in `plugins/`, chains in `workflows/`.

---

## Run from source

Python 3.9+, Node 18+, Docker Compose v2. See **[QUICK_START.md](QUICK_START.md)**.

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research install && ./research license && ./research start
```

Open **http://localhost:3000**. Dev mode: `./research-dev start`.

---

## Desktop app

Installers: [Releases](https://github.com/phindagijimana/neuroinsight_research/releases).
Requires **Docker Desktop** (running). First launch pulls the engine image (~1.8 GB).
Updates: **[docs/DESKTOP_UPDATES.md](docs/DESKTOP_UPDATES.md)** ·
Issues: **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

---

## Features

- **Transfer** — Local, Remote, HPC, Pennsieve, XNAT ([TRANSFER.md](docs/TRANSFER.md))
- **Jobs** — compute-only submission; browse paths on the selected backend
- **Backends** — local Docker, remote Docker (SSH), SLURM + Apptainer
- **Monitoring** — logs, progress, SLURM queue
- **Viewer** — NIfTI + overlays (Niivue)

Connectors and HPC setup: **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**.

---

## Security

Single-user, **localhost-first** (`127.0.0.1`). No built-in API auth — do not
expose the backend to the internet without your own proxy/VPN. Credentials use OS
keychain (desktop) or local config. **[docs/SIGNING_AND_TRUST.md](docs/SIGNING_AND_TRUST.md)** (installers).

---

## Citation

```bibtex
@software{neuroinsight,
  author       = {Ndagijimana, Philbert and URMC collaborators},
  title        = {NeuroInsight: Neuroimaging Pipeline Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  version      = {0.1.25},
  note         = {Developed in collaboration with URMC researchers and neurologists}
}
```

Pipeline literature: **[docs/REFERENCES.md](docs/REFERENCES.md)** ·
[CITATION.cff](CITATION.cff).

---

## Contact & license

**Philbert Ndagijimana** — phindagijimana@gmail.com

MIT License. Tool licenses (FreeSurfer, MELD, …): **[docs/TOOL_LICENSES.md](docs/TOOL_LICENSES.md)**.
