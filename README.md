# NeuroInsight

An open-source platform for running neuroimaging tools from a web interface. Select your data, pick a plugin or workflow, choose where to process, and click Submit — no terminal commands or container expertise required.

A **plugin** wraps a single neuroimaging tool (e.g., FreeSurfer, fMRIPrep) so it can run in a container with one click. A **workflow** chains multiple plugins into a single job with automatic data passing between steps (e.g., fMRIPrep then XCP-D). Both are defined as YAML files -- drop a new one in `plugins/` or `workflows/` to extend the platform.

## Desktop app (end users)

Most users want the **desktop app** — a one-click installer for macOS, Windows,
or Linux. The only prerequisite is **Docker Desktop** (running). On first launch
the app downloads its engine image (~1.8 GB) once, then everything runs locally.

**Install guide:** **[docs/INSTALL.md](docs/INSTALL.md)** — download from
[Releases](https://github.com/phindagijimana/neuroinsight_research/releases),
verify the checksum, drag **`NeuroInsight.app`** to **`/Applications`** (macOS),
start Docker, and launch.

**Stuck?** [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — Docker detection,
SmartScreen, App Translocation, and engine startup.

**Advanced:** remote servers, HPC/SLURM, Pennsieve, and XNAT — see
[docs/USER_GUIDE.md](docs/USER_GUIDE.md).

---

The sections below are for **developers/contributors** running from source.

## Requirements

Install these before running `./research install` (the installer handles all Python/Node packages automatically):

| Requirement | Minimum | Notes |
|---|---|---|
| Python | 3.9+ | If missing, the installer detects your OS and offers to install it for you. |
| Node.js | 18+ | If missing, the installer offers to install it via nvm (no sudo needed). |
| Docker | Compose v2 | Runs infrastructure (PostgreSQL, Redis, MinIO) and all neuroimaging containers. |
| OS | Linux, macOS, or Windows (WSL2) | **Linux or WSL2 recommended.** macOS works but local processing is slower due to Docker's VM layer and Rosetta emulation on Apple Silicon. See [macOS Notes](docs/USER_GUIDE.md#macos-notes). Windows users need WSL2 with Docker Desktop. |
| License files | -- | See [docs/TOOL_LICENSES.md](docs/TOOL_LICENSES.md). Run `./research license` to set up from source. |

**RAM and storage:**

| | App only (orchestration + remote/HPC jobs) | Local processing (Docker) |
|---|---|---|
| RAM | 4 GB | 16 GB+ (FreeSurfer, fMRIPrep); 8 GB for lighter plugins |
| Storage | 2 GB (app + dependencies) | 10-50 GB per plugin image + space for input/output data |

If you only submit jobs to a remote server or HPC, the app itself is lightweight. Local processing requires more resources because the neuroimaging containers run on your machine.

## Quick Start

See **[QUICK_START.md](QUICK_START.md)** for a minimal command reference, or run:

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research install        # install deps, start infra, init DB
./research license        # set up FreeSurfer / MELD license files
./research start          # launch the app
```

Open **http://localhost:3000**.

For connectors (HPC, Pennsieve, XNAT) and deployment options, see **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)**. Plugin and workflow catalog: in-app **Docs** tab (generated from `plugins/` and `workflows/`).

## Key Features

- **Multiple data sources** -- Local files, Remote Server (SSH), HPC filesystem, Pennsieve, or XNAT
- **Multiple compute backends** -- Local Docker, Remote Server (SSH + Docker), or HPC/SLURM (SSH + Singularity)
- **Mix and match** -- Browse data on XNAT, process on HPC; pull from Pennsieve, process locally
- **Real-time monitoring** -- SLURM queue monitor, job progress tracking, and log streaming
- **Plugins** -- Each tool is a single YAML file; drop a new one in `plugins/` to add support for a new tool
- **Workflows** -- Chain multiple plugins into one job with automatic data passing between steps
- **Built-in NIfTI viewer** -- View results with segmentation overlays powered by Niivue

## Security & data

NeuroInsight is designed as a **local, single-user desktop application**. Your
data stays on your machine (or your HPC) — nothing is uploaded to a third-party
service. The engine and all its internal services (database, cache, object
store) bind to `127.0.0.1` only, and the all-in-one container generates unique
credentials per install.

> **Do not expose the backend to the internet.** The local API has no built-in
> authentication because it is meant to listen only on localhost. If you change
> the bind host (e.g. `0.0.0.0`) to reach it from another machine, put it behind
> your own authenticating reverse proxy / VPN — otherwise anyone on the network
> could submit jobs or read results.

Credentials you enter for connectors (Pennsieve, XNAT, SSH/HPC) are stored in
your OS keychain via the desktop Credential Vault, not in the repo. For installer
trust (code signing / notarization), see [docs/SIGNING_AND_TRUST.md](docs/SIGNING_AND_TRUST.md).

## Documentation

See **[docs/README.md](docs/README.md)** for the full index. Quick links:

- [Install (desktop)](docs/INSTALL.md) — start here for end users
- [User Guide](docs/USER_GUIDE.md) — HPC/SLURM, Pennsieve, XNAT, source deployment
- [Tool licenses](docs/TOOL_LICENSES.md) — FreeSurfer / MELD setup
- [Quick Start (developers)](QUICK_START.md) — `./research` from source
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Releasing](docs/RELEASING.md) · [Signing & trust](docs/SIGNING_AND_TRUST.md) — maintainers

## Citing This Software

If you use NeuroInsight in your work, please cite:

```bibtex
@software{neuroinsight_research,
  author       = {Phindagijimana},
  title        = {NeuroInsight: Neuroimaging Processing Platform},
  year         = {2026},
  url          = {https://github.com/phindagijimana/neuroinsight_research},
  version      = {0.1.16}
}
```

Please also cite the individual tools you use (FreeSurfer, fMRIPrep, QSIPrep, etc.) as required by their respective licenses.

## Contact

For questions, comments, or contributions, reach out to **phindagijimana@gmail.com**.

## License

MIT License. Tool-specific licenses: [docs/TOOL_LICENSES.md](docs/TOOL_LICENSES.md).
