# NeuroInsight — User Guide

Reference guide for deploying and using NeuroInsight. **New desktop users:** start with **[INSTALL.md](INSTALL.md)** (short, step-by-step). Use this guide for advanced setup, connectors, and HPC.

## Contents

- [Docker (source / Linux servers)](#docker-source--linux-servers)
- [macOS notes](#macos-notes)
- [Local vs remote deployment](#local-vs-remote-deployment)
- [Deployment from source](#deployment-from-source)
- [Terminology](#terminology)
- [Transfer, Jobs, and compute](#transfer-jobs-and-compute)
- [Remote Server vs HPC](#remote-server-vs-hpc)
- [Large file transfers](#large-file-transfers) — full matrix in **[TRANSFER.md](TRANSFER.md)**
- [Plugins and workflows](#plugins-and-workflows)
- [Connecting to a remote server](#connecting-to-a-remote-server)
- [Connecting to Pennsieve](#connecting-to-pennsieve)
- [Connecting to HPC (SLURM)](#connecting-to-hpc-slurm-cluster)
- [Connecting to XNAT](#connecting-to-xnat)
- [Support](#support)

## Prerequisites

**Desktop app:** Docker Desktop (running), ~20 GB disk, 8 GB+ RAM — see [INSTALL.md](INSTALL.md).

**From source / development:**

- Docker and Docker Compose
- Python 3.10+
- Node.js 18+
- 16 GB+ RAM (32 GB recommended for local processing)
- SSH key-based authentication (for remote/HPC connections)

## Desktop app

Install, verify, and first launch: **[INSTALL.md](INSTALL.md)**. Problems:
**[TROUBLESHOOTING.md](TROUBLESHOOTING.md)**.

To run the web UI without the desktop installer, use [Deployment from source](#deployment-from-source) below.

## Docker (source / Linux servers)

**Desktop users:** install **Docker Desktop** — see [INSTALL.md](INSTALL.md) §1.

For **Linux servers** or source deployments without Docker Desktop:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER   # then log out and back in
docker compose version
```

On **Windows (WSL2)** for source installs: enable WSL integration in Docker Desktop
Settings → Resources → WSL Integration.

---

## macOS Notes

> **Recommendation:** Use **Linux** as the primary production host platform for NeuroInsight.
> macOS is supported, but it is best used as an orchestration host (submitting jobs to remote servers or HPC) rather than for heavy local processing.

### Production Readiness by Host OS

- Linux: Recommended production host platform. Ready for production if you accept pull-on-demand behavior and maintain disk hygiene.
- macOS: Supported for production orchestration, with remote/HPC execution strongly preferred.

NeuroInsight runs on macOS for both orchestration and local processing. There are a few differences from Linux to be aware of.

### Docker Desktop Resource Limits

Docker on macOS runs containers inside a lightweight Linux VM, not natively. By default Docker Desktop allocates limited resources to this VM. For local neuroimaging processing you must increase them:

1. Open **Docker Desktop > Settings > Resources**
2. Set **Memory** to at least **16 GB** (FreeSurfer and fMRIPrep need this; 8 GB is enough for lighter plugins)
3. Set **CPUs** to at least **4** (more is better for parallel processing)
4. Set **Disk image size** to at least **64 GB** (neuroimaging container images are large)
5. Click **Apply & Restart**

If you only use NeuroInsight as an orchestration layer (submitting jobs to a remote server or HPC), the default Docker Desktop resources are fine since only PostgreSQL, Redis, and MinIO run locally.

### Apple Silicon (M1/M2/M3/M4)

Most neuroimaging Docker images (FreeSurfer, fMRIPrep, QSIPrep, etc.) are built for `linux/amd64`. On Apple Silicon Macs they run under Rosetta 2 emulation, which Docker Desktop enables automatically. This works but has two implications:

- **Performance**: Expect 20-40% slower processing compared to native `amd64` hardware. For large datasets, consider offloading processing to a remote Linux server or HPC.
- **Compatibility**: Rare edge cases may fail under emulation. If a container crashes unexpectedly, check whether an `arm64`-native image is available from the tool's maintainers.

No configuration changes are needed -- Docker Desktop handles Rosetta emulation transparently.

### File System Performance

Docker Desktop on macOS uses a virtualized file system bridge between the host and containers. This is slower than native Linux Docker, especially for I/O-heavy workflows that read/write many small files (e.g., FreeSurfer surface reconstruction). Tips:

- Keep input data **inside Docker volumes** rather than bind-mounting large host directories.
- For heavy local processing, a Linux machine (or VM) will be noticeably faster.
- Orchestration-only use (remote/HPC processing) is not affected.

### Homebrew Dependencies

macOS does not ship `python3` or `node` by default on all versions. If they are missing, install via [Homebrew](https://brew.sh):

```bash
brew install python@3.11 node
```

The NeuroInsight installer handles all Python packages (via venv) and Node packages (via npm) automatically after these are available.

---

## Local vs Remote Deployment

NeuroInsight can run on your own machine (laptop, workstation) or on a remote server (AWS EC2, institutional VM, etc.). Where you deploy it changes how you access the UI and how the app reaches other systems.

### Quick Reference

| | Running locally (laptop/workstation) | Running on a remote server (EC2, cloud VM) |
|---|---|---|
| **Access the UI** | `http://localhost:3000` in your browser | SSH into the server with `-L 3000:localhost:3000`, then open `http://localhost:3000` on your laptop |
| **SSH key location** | `~/.ssh/id_ed25519` on your laptop | `~/.ssh/id_ed25519` on the remote server |
| **Connect to HPC** | Direct SSH if on the same network; VPN if off-campus | Reverse tunnel (`-R 2222:hpc-login:22`) from a VPN-connected machine, then use `localhost:2222` in the UI |
| **Connect to Remote Server** | Direct SSH to hostname:22 | Same as HPC -- direct if reachable, reverse tunnel if behind a firewall |
| **Connect to Pennsieve** | Direct (public API, no tunnel needed) | Direct (public API, no tunnel needed) |
| **Connect to XNAT** | Direct if on the same network; SSH local forward (`-L 8443:xnat:443`) if behind a firewall | SSH local forward from the server through an intermediary (e.g., HPC login node) to XNAT |
| **Local Docker processing** | Works directly -- Docker runs on your machine | Works directly -- Docker runs on the server |

### Running on your laptop or workstation

This is the simplest setup. You open `http://localhost:3000` in your browser and all connections go out from your machine. If the HPC or XNAT server is on the same campus network (or you are connected via VPN), you can use their real hostnames directly.

### Running on a remote server (e.g., AWS EC2)

When NeuroInsight runs on an EC2 instance or similar, two things change:

1. **Accessing the UI**: You SSH into the server and forward port 3000 to your laptop so you can open the app in your browser:

```bash
ssh -i ~/.ssh/your-key.pem -L 3000:localhost:3000 ubuntu@your-server-ip
```

2. **Reaching firewalled systems (HPC, XNAT)**: The EC2 instance cannot reach campus-internal systems directly. You bridge the gap from a machine that has VPN/network access (typically your laptop):

```bash
# From your laptop (VPN connected), in the same SSH session:
ssh -i ~/.ssh/your-key.pem \
    -L 3000:localhost:3000 \
    -R 2222:hpc-login.university.edu:22 \
    ubuntu@your-server-ip
```

This single command does three things: forwards the UI to your browser (`-L 3000`), and creates a reverse tunnel so the server can reach the HPC (`-R 2222`). In the NeuroInsight UI, enter `localhost` / port `2222` for the HPC connection.

For XNAT behind a firewall, set up a local forward on the server through the HPC login node (see the XNAT section below for the exact command).

**Pennsieve** always works without tunnels because its API (`api.pennsieve.io`) is on the public internet.

### SSH key setup

Regardless of deployment, the SSH key must be on the machine running NeuroInsight (not your laptop, unless that is the NeuroInsight machine). If NeuroInsight is on EC2, generate or copy the key there, and add the public key to your HPC account. See the HPC section below for step-by-step instructions.

---

## Deployment from source

**CLI (recommended):** see **[QUICK_START.md](../QUICK_START.md)** for `./research install`, `start`, and `stop`.

**Tool licenses:** [TOOL_LICENSES.md](TOOL_LICENSES.md).

### Docker Compose (alternative)

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
cp .env.example .env   # set POSTGRES_PASSWORD, SECRET_KEY, etc.
docker compose up -d
```

Open `http://localhost:3000`. For dev hot-reload: `./research-dev start` (see QUICK_START).

### Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback for dev |
| `SECRET_KEY` | Session signing key (change in production) | Dev placeholder |
| `API_HOST` / `API_PORT` | Backend listen address | `0.0.0.0` / `3003` |
| `VITE_API_URL` | Frontend API target (for production builds) | `http://localhost:3000` |

See `.env.example` for the full list of options including HPC, storage, and Redis settings.

---

## Terminology

If you are new to research computing, here are the key terms used in this guide.

| Term | What it means |
|------|---------------|
| **SSH** | Secure Shell -- a way to securely log in to another computer over the network, like a remote desktop but text-based. |
| **SSH key** | A digital credential file stored on your computer that proves your identity to a remote server, replacing the need to type a password each time. You generate a key pair: a private key (stays on your machine, never shared) and a public key (copied to the server). |
| **Hostname** | The network name of a computer, similar to a website address. Example: `hpc-login.bu.edu`. |
| **Port** | A numbered channel on a computer for network communication. SSH uses port 22 by default. Think of the hostname as a building address and the port as a specific room number inside. |
| **VPN** | Virtual Private Network -- software that makes your computer appear to be on a university or company network even when you are off-site. Required to reach servers that are not exposed to the public internet. |
| **Firewall** | A security barrier that blocks unauthorized network connections. University HPCs and XNAT servers are often behind firewalls, meaning outside computers cannot reach them directly. |
| **SSH tunnel** | A technique that forwards network traffic through an SSH connection to bypass firewalls. It creates a secure "pipe" from one machine to another, allowing you to reach a server you cannot access directly. |
| **Docker** | Software that packages applications into self-contained units called containers. NeuroInsight uses Docker to run neuroimaging tools without requiring you to install them manually. |
| **HPC** | High-Performance Computing cluster -- a shared set of powerful computers managed by a university or institution. Researchers submit processing jobs to the cluster and the scheduler distributes the work. |
| **SLURM** | The job scheduler used on most HPC clusters. When you submit a job, SLURM places it in a queue and runs it when resources (CPU, memory, GPU) become available. |
| **Partition** | A group of compute nodes on an HPC cluster designated for certain types of work (e.g., `general`, `gpu`, `short`). You select a partition when submitting a job. |
| **Login node** | The computer you SSH into when connecting to an HPC cluster. It is used for submitting jobs and transferring files, not for heavy computation. |
| **Remote Server** | In the NeuroInsight UI, any **SSH-accessible Linux machine** where jobs run via **Docker** — not cloud-specific. Typical examples: a lab workstation, a department VM, or a cloud instance (AWS EC2, GCP Compute Engine, Azure VM). When connected, the banner may show **Remote Server (Docker)** to distinguish it from HPC/SLURM mode on the same SSH host. |
| **Singularity / Apptainer** | Container software designed for HPC environments. It serves the same purpose as Docker but is allowed on shared clusters where Docker is not (for security reasons). Apptainer is the newer name for Singularity. |
| **API key** | A credential (like a username and password combined into one token) used to authenticate with a web service programmatically. Pennsieve uses API keys for access. |
| **SSL certificate** | A digital certificate that verifies a website's identity and enables encrypted (HTTPS) connections. When you connect through an SSH tunnel, the certificate check may fail because the certificate was issued for the real hostname, not `localhost`. |

---

## Transfer, Jobs, and compute

NeuroInsight splits **data movement** and **pipeline execution**:

| Page | Role |
|------|------|
| **Transfer** | Copy files between Local, Remote Server, HPC, Pennsieve, and XNAT (dual-pane UI, queue, history). See **[TRANSFER.md](TRANSFER.md)**. |
| **Jobs** | Run pipelines on paths that **already exist** on the chosen compute backend (compute-only — no Pennsieve/XNAT wizard). |

**Processing always uses files on the compute side.** Pipelines do not read Pennsieve or XNAT in place — use **Transfer** to stage data first, then submit from **Jobs**.

### Typical workflow

1. **Transfer** — move data where you want to compute (e.g. Pennsieve → HPC scratch, XNAT → local disk).
2. **Jobs** — choose **Compute** (Local / Remote / HPC), browse **Subject path** on that backend, pick pipeline, submit.
3. **Transfer** (optional) — move results back (e.g. HPC outputs → Pennsieve).

After a transfer completes, use **Open in Jobs** to prefill path and compute backend.

### Where data can live (via Transfer)

| Location | Access |
|----------|--------|
| **Local** | This machine's filesystem |
| **Remote Server** | SSH-accessible Linux host (lab VM, cloud instance, workstation) |
| **HPC** | Cluster filesystem (scratch, project space) |
| **Pennsieve** | Cloud datasets — connect and browse in a Transfer pane |
| **XNAT** | Institutional archive — connect and browse in a Transfer pane |

### Compute backends (Jobs page)

| Backend | Description | Requirements |
|---------|-------------|--------------|
| **Local Docker** | Process on the NeuroInsight host | Docker installed |
| **Remote Server** | SSH + Docker on a remote Linux machine | SSH access, Docker on remote host |
| **HPC/SLURM** | Submit to a SLURM cluster | SSH access, SLURM, Singularity/Apptainer |

### Remote Server vs HPC

Both use **SSH**; on many setups the same hostname works — NeuroInsight switches mode when you change the **Compute** tab.

| | **Remote Server** | **HPC / SLURM** |
|---|-------------------|-----------------|
| **Typical machine** | Lab workstation, department Linux server, single cloud VM | University **cluster** with a job scheduler |
| **How jobs run** | Docker on that host | SLURM + Singularity/Apptainer on compute nodes |
| **UI when active** | Connected · **Remote Server (Docker)** | Connected · **HPC (SLURM)** |
| **When to choose it** | One Linux box you control with Docker | Shared cluster; Docker usually **not** allowed on compute nodes |

Common setups:

- **Local data, local compute** — files already on disk; Jobs → Compute **Local**, browse, submit.
- **HPC data, HPC compute** — BIDS on scratch; Transfer optional; Jobs → Compute **HPC**, browse cluster path, submit.
- **Pennsieve → HPC** — **Transfer** Pennsieve → HPC, then **Jobs** on HPC path.
- **XNAT → local** — **Transfer** XNAT → Local, then **Jobs** with Local compute.

### Large file transfers

NeuroInsight Transfer handles **multi-GB and 300GB+** datasets with per-file timeouts, resume, and re-run skip. **Full route matrix, env vars, and limits:** **[TRANSFER.md](TRANSFER.md)**.

Summary:

- **Pennsieve → HPC** — direct `curl` on the cluster (preferred for huge data).
- **All routes** — file-by-file batching; default **24 h timeout per file**.
- **Re-run** the same Transfer to the same destination — completed files skipped, partials resume.
- **Tune** via `NIR_TRANSFER_*` in `.env.example`.

**Practices for very large moves:**

- Prefer **Pennsieve → HPC** (or HPC ↔ HPC) over routing through your laptop.
- Transfer **folders** on Pennsieve — the backend expands to files and preserves paths.
- Use **HPC scratch or project space** with enough quota; watch cluster retention policies.
- For XNAT, large moves may use the indirect path (via NeuroInsight) when the archive is behind a tunnel — plan extra time and disk on the orchestrator host.

If manual recovery is needed on a cluster, use `curl -C -` or `rsync` to the same destination path, then submit from Jobs using that path.

### EEG workflows: layout and channels

EEG-related workflows (for example basic detection, source localization, and multimodal epilepsy biomarker) expect a **staging directory** as input with continuous EEG under **`eeg/raw/`** by default (formats such as EDF, FIF, BrainVision, BDF). You do **not** need a full BIDS dataset unless you choose to organize or convert data that way separately.

**Default path:** preprocessing applies **name-based heuristics** so common auxiliary traces (for example EKG, EOG, EMG) are not treated as scalp EEG. For many clinical exports this is **enough**, provided you **quickly verify** that channel **labels and roles** match the recording (wrong labels break both heuristics and any optional sidecar).

**Optional:** place **`metadata/channels.tsv`** next to your EEG (BIDS-style `name` and `type` columns) to set channel types **explicitly** when file headers are unreliable, for multi-site consistency, or for stricter reproducibility. See `eeg/EEG.md` and the HPC pipeline guide for staging details.

---

## Plugins and Workflows

In the **Docs** tab you can browse the available tools:

- **Plugin** — a single neuroimaging tool running in one container. Use it for an
  individual processing step or when you want full control.
- **Workflow** — a sequence of plugins that work together; dependencies are
  managed automatically. Recommended for complete analysis pipelines.

Some **utility plugins are hidden** in the catalog but run inside workflows for
specialized tasks. For the Tuberous Sclerosis Detection workflow these are:

| Hidden plugin | What it does |
|---|---|
| TSC Data Preparation | Validates and standardizes T1/T2/FLAIR inputs into a workflow-ready layout. |
| TSC Skull Stripping (SynthStrip) | Brain extraction and mask generation for downstream steps. |
| TSC T2 Super-Resolution (NiftyMIC) | Combines axial/coronal T2 when available; otherwise single-T2 passthrough. |
| TSC Registration (ANTs) | Bias correction, resampling, and registration into MNI space. |
| TSC Tuber Segmentation (TSCCNN3D) | CNN-based tuber segmentation and tuber-burden quantification. |

---

## Connecting to a Remote Server

**Remote Server** in the Jobs and Transfer tabs means: connect over SSH and run pipelines in **Docker on that Linux host**. It applies to lab workstations, on-prem VMs, and cloud instances alike — the label does not mean “AWS only.” See [Remote Server vs HPC](#remote-server-vs-hpc) if you are unsure whether to use Remote Server or HPC/SLURM.

NeuroInsight can run neuroimaging jobs on any SSH-accessible Linux machine with Docker installed. This is useful for offloading processing to a more powerful server, a cloud VM (AWS, GCP, Azure), or a lab workstation.

### Example Scenario

Dr. Reyes runs NeuroInsight on her laptop (8 GB RAM), but FreeSurfer and fMRIPrep need far more memory. Her lab has a shared Linux workstation (`brainlab-ws01.med.stanford.edu`) with 128 GB RAM, 32 CPU cores, and Docker installed. She wants to keep browsing and uploading files from her laptop while the heavy processing happens on the lab workstation.

**Workflow:**

1. **Transfer** — Local → Remote Server: copy the T1 NIfTI to the workstation (or upload via Transfer browse).
2. **Jobs** — Compute **Remote Server**, connect SSH:

| Field | Value |
|-------|-------|
| Host | `brainlab-ws01.med.stanford.edu` |
| Username | `sreyes` |
| Port | `22` |

3. Browse the remote path, pick FreeSurfer, submit. Processing runs in Docker on the workstation.

If she were working from home and the workstation were behind the university firewall, she would first connect her VPN, then enter the same hostname. Alternatively, she could set up a reverse SSH tunnel as described in the HPC section below and use `localhost` / port `2222` instead.

### Prerequisites

1. **A Linux server** with Docker installed and running
2. **SSH access** from the NeuroInsight server to the remote machine (key-based authentication)
3. **Docker permissions** for your SSH user on the remote machine (user must be in the `docker` group)

### Step 1: Set Up SSH Key Authentication

Follow the SSH key setup in the HPC section below (Step 1a-1c). The process is identical -- generate a key on the NeuroInsight server and copy the public key to the remote machine's `~/.ssh/authorized_keys`.

### Step 2: Connect in the NeuroInsight UI

1. Open **Jobs**
2. Under **Compute**, select **Remote Server**
3. Fill in the SSH connection fields:
   - **Host** -- hostname or IP of the remote machine (or `localhost` if using a reverse tunnel)
   - **Username** -- your SSH username on the remote machine
   - **Port** — `22` (default) or `2222` if using a reverse tunnel
4. Click **Connect & Activate**
5. A green "Connected" badge confirms the connection

If the remote server is behind a firewall, use a reverse SSH tunnel (same pattern as HPC Step 2 below).

---

## Connecting to Pennsieve

NeuroInsight connects to [Pennsieve](https://app.pennsieve.io) from the **Transfer** page to browse and copy datasets. Pennsieve is a cloud-based research data management system used by NIH SPARC, RE-JOIN, and other programs.

### Prerequisites

1. **A Pennsieve account** with access to at least one dataset
2. **An API key and secret** generated from your Pennsieve account

### Step 1: Generate API Credentials

1. Log in to Pennsieve at [https://app.pennsieve.io](https://app.pennsieve.io)
2. Click your profile icon (top-right) and select **View My Profile**
3. Scroll down to the **API Keys** section
4. Click **Create API Key**
5. Enter a name (e.g., "NeuroInsight") and click **Create**
6. **Copy both the API Key and the API Secret** -- the secret is only shown once

Example of what you will see after clicking Create:

```
API Key:    a3f8e1d2-7b4c-49e1-8f6a-2d9c0e5b1a73
API Secret: b91d4f7e-3a28-41c5-9e0b-8c6f2d5a4e17
```

The key is a permanent identifier; the secret acts as the password. If you lose the secret, delete the key and create a new one.

### Step 2: Connect in the NeuroInsight UI

1. Open the **Transfer** page
2. In either pane, select **Pennsieve** and paste the credentials you copied:
   - **API Key** -- e.g., `a3f8e1d2-7b4c-49e1-8f6a-2d9c0e5b1a73`
   - **API Secret** — e.g., `b91d4f7e-3a28-41c5-9e0b-8c6f2d5a4e17`
3. Click **Connect**
4. A green "Connected" badge confirms the connection, showing your email and workspace (e.g., "james.wright@upenn.edu -- Penn Epilepsy Center")

### Step 3: Browse and transfer data

Use **Browse** in the Pennsieve pane to open the data browser. The Pennsieve hierarchy is:

```
Workspace (Organization)
 └── Dataset
      └── Package (folder or file collection)
           └── Files
```

1. **Datasets** -- listed automatically after connecting; select the dataset containing your data
2. **Packages** -- navigate through folder structure within the dataset
3. **Files** — select files/folders, then use the transfer arrows to copy to your destination pane (Local, Remote, or HPC).

### Step 4: Submit a job

After data is on the compute backend, open **Jobs**, choose matching **Compute**, browse **Subject path**, pick a pipeline, and submit. Or click **Open in Jobs** when a transfer completes to prefill the path. Your Pennsieve dataset is unchanged; upload results back via **Transfer** if needed.

### Troubleshooting Pennsieve Connection

| Problem | Solution |
|---------|----------|
| **"API Key and Secret are required"** | Both fields must be filled in |
| **"Authentication failed"** | API key or secret is incorrect -- generate a new pair from Pennsieve |
| **"Connection timed out"** | Network issue reaching Pennsieve API (`api.pennsieve.io`) -- check firewall/proxy |
| **Empty dataset list** | Your account may not have access to any datasets -- verify in the Pennsieve web UI |
| **"Token expired"** | Session expired after long idle time -- click Disconnect and reconnect |

---

## Connecting to HPC (SLURM Cluster)

NeuroInsight can submit neuroimaging jobs to a remote HPC cluster via SSH and SLURM, running containerized tools (Singularity/Apptainer) on cluster nodes instead of locally.

### Example Scenario

Priya is a PhD student in neuroscience at Boston University. She has 50 subjects to process through the full diffusion pipeline (QSIPrep + QSIRecon), which takes about 8 hours per subject. Running all 50 sequentially on her laptop would take over 16 days. The university's Shared Computing Cluster (SCC) has hundreds of nodes and can run multiple subjects in parallel.

NeuroInsight is deployed on an AWS EC2 instance so Priya can access it from anywhere. The SCC is behind BU's campus firewall, so she sets up a reverse SSH tunnel from her laptop (see Step 2 below for the exact command).

**Workflow:** Her BIDS data is already on `/projectnb/epilepsy/priya/` on the SCC. On **Jobs**, she connects HPC compute:

| Field | Value |
|-------|-------|
| Host | `localhost` (reverse tunnel) |
| Username | `priya` |
| Port | `2222` |
| Work Directory | `/scratch/priya/neuroinsight` |
| Partition | `general` |
| Modules | `singularity/3.10` |

She browses the BIDS directory in **Subject path**, selects the diffusion workflow, and submits. SLURM queues jobs across cluster nodes; she monitors from the SLURM Queue Monitor on Jobs.

If Priya were on campus (connected to BU's network directly), she would skip the tunnel and enter the real hostname (`scc-login.bu.edu`, port `22`) instead of `localhost:2222`.

### Prerequisites

Before connecting, ensure you have:

1. **An HPC account** with SSH access to a login node
2. **SLURM** scheduler running on the cluster
3. **Singularity or Apptainer** installed on the cluster (for containerized tools)
4. **SSH key-based authentication** configured (see Step 1 below)

### Step 1: Set Up SSH Key Authentication

The NeuroInsight server needs passwordless SSH access to your HPC login node. You must copy the server's public key to your HPC account.

#### 1a. Generate or display the server's public key

On the **NeuroInsight server**, check if a key already exists:

```bash
cat ~/.ssh/id_ed25519.pub
```

If there is no key, generate one (press Enter through the prompts):

```bash
ssh-keygen -t ed25519 -C "neuroinsight" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

Example output:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGk7r0gF4QXBZ1dN8vRpJm2LkO3xEzPfCwU9t2Q4sRmN neuroinsight
```

Copy the entire line (starting with `ssh-ed25519` and ending with `neuroinsight`).

#### 1b. Add the key to your HPC account

From a machine that can reach the HPC (your laptop or the HPC terminal), run a single command to append the key. Replace the username, hostname, and key with your own:

```bash
ssh priya@scc-login.bu.edu \
    "mkdir -p ~/.ssh && echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGk7r0gF4QXBZ1dN8vRpJm2LkO3xEzPfCwU9t2Q4sRmN neuroinsight' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Alternatively, log into the HPC directly and paste the key into `~/.ssh/authorized_keys` with a text editor.

#### 1c. Verify it works

From the **NeuroInsight server**, test that the connection works without a password prompt:

```bash
ssh -o BatchMode=yes priya@scc-login.bu.edu hostname
```

Expected output (the HPC hostname, no password prompt):

```
scc-login1
```

If this succeeds, the key is set up correctly.

### Step 2: Network Access (If HPC Is Behind a Firewall)

If NeuroInsight runs on an external server (e.g., AWS) and the HPC is on a private university network, the server cannot reach the HPC directly. You need a **reverse SSH tunnel** from a machine that has VPN/network access.

#### Architecture

```
NeuroInsight Server (AWS)                    Your Laptop (VPN)                   HPC Login Node
      localhost:2222  ---- reverse tunnel ---->  laptop ---- VPN ---->  hpc-login.university.edu:22
```

#### Set up the reverse tunnel

On your **local machine** (with VPN connected), run:

```bash
ssh -i ~/.ssh/aws-neuroinsight.pem \
    -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -R 2222:scc-login.bu.edu:22 \
    ubuntu@54.89.123.45
```

| Flag | Purpose |
|------|---------|
| `-i ~/.ssh/aws-neuroinsight.pem` | Private key for the AWS EC2 server |
| `-L 3000:localhost:3000` | Forward the UI to your browser |
| `-L 8000:localhost:8000` | Forward the API to your browser |
| `-R 2222:scc-login.bu.edu:22` | Reverse tunnel: server port 2222 reaches HPC via your VPN |
| `ubuntu@54.89.123.45` | Username and IP of the NeuroInsight server |

Replace `scc-login.bu.edu` with your HPC login node and `54.89.123.45` with your server's IP.

Keep this terminal open while using NeuroInsight.

**When using the reverse tunnel**, enter these values in the UI:
- **Host**: `localhost`
- **Port**: `2222`
- **Username**: your HPC username

To avoid entering port 2222 every time, set it in your `.env` file:

```bash
HPC_HOST=localhost
HPC_USER=your-hpc-username
HPC_SSH_PORT=2222
```

The app will use these as defaults whenever you connect.

**If NeuroInsight can reach the HPC directly** (same network, or VPN on the server), use the actual hostname:
- **Host**: `hpc-login.university.edu`
- **Port**: `22` (default, no `.env` change needed)
- **Username**: your HPC username

### Step 3: Connect in the NeuroInsight UI

1. Open **Jobs**
2. Under **Compute**, select **HPC**
3. Fill in the SSH connection fields:

| Field | Direct access (on campus) | Via reverse tunnel (off campus) |
|-------|---------------------------|--------------------------------|
| Host | `scc-login.bu.edu` | `localhost` |
| Username | `priya` | `priya` |
| Port | `22` | `2222` |

4. Click **Connect**
5. A green "Connected" badge appears on success

#### Connecting from the app: VPN, saved hosts, and MFA/Duo

- **VPN first.** If your cluster is on a private/campus network, connect your
  institution's **VPN** before clicking Connect (otherwise the host is unreachable).
- **Saved hosts.** The connect form has a **"Saved host (from ~/.ssh/config)"**
  dropdown — pick an alias you already use (it fills in host/user/port). Aliases,
  `ProxyJump`, and keys from your `~/.ssh/config` are honored.
- **Key-based clusters** connect with **no password** — leave the password field blank.
- **MFA / Duo clusters** (e.g. CIRC/BlueHive): enter your **password**, then
  **approve the Duo push on your phone** to finish connecting. The desktop app
  performs the SSH from the host (broker), so it inherits your working auth
  (agent key, Kerberos, Duo).

### Step 4: Configure SLURM Settings

After connecting:

1. Set the **Work Directory** -- the path on the HPC where job scripts and logs are written (e.g., `/scratch/priya/neuroinsight`)
2. Click **Show SLURM Settings** to expand advanced options:
   - **Partition** -- dropdown auto-populated from the cluster (e.g., `general`, `gpu`, `short`)
   - **Account** -- your SLURM allocation name, if required (e.g., `epilepsy-lab`)
   - **QoS** -- quality of service tier (optional)
   - **Modules** -- comma-separated list of modules to load before each job (e.g., `singularity/3.10`)
3. Click **Activate SLURM Backend**

All subsequent neuroimaging jobs will be submitted to the cluster via `sbatch`.

### Step 5: Monitor Jobs

Once connected, the **SLURM Queue Monitor** panel appears automatically, showing:
- Your SLURM jobs with status (RUNNING, PENDING, COMPLETED, FAILED)
- Auto-refreshes every 10 seconds
- Color-coded status indicators

You can also browse remote files on the HPC using the **File Browser** panel in HPC mode.

### Troubleshooting HPC Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | HPC is unreachable -- check VPN/firewall, verify hostname, set up reverse tunnel |
| **"Authentication failed"** | SSH key not on HPC -- follow Step 1b to add the public key |
| **"Connection refused"** | Wrong port, or the hostname is a web portal (OOD) not an SSH server -- use the actual login node |
| **"No SLURM partitions found"** | SLURM not available on this node -- verify `sinfo` works when you SSH in manually |
| **Reverse tunnel not working** | Ensure your VPN is active and the SSH session with `-R` flag is still open |

---

## Connecting to XNAT

NeuroInsight connects to XNAT from the **Transfer** page to browse and copy imaging data. XNAT is an open-source imaging informatics platform used by hospitals and research centers.

### Example Scenario

Dr. Nakamura is a neuroradiologist at the University of Rochester Medical Center. The imaging center stores all research MRI data on an internal XNAT server at `https://xnat.urmc.rochester.edu`. She wants to run the cortical lesion detection pipeline on five subjects from the "Focal Epilepsy MRI Study" project.

NeuroInsight is running on an AWS EC2 instance, and the XNAT server is on the hospital's internal network (not accessible from the internet). Dr. Nakamura is already connected to the university HPC via NeuroInsight. She uses the HPC login node as a bridge to reach XNAT.

**Setting up the tunnel (on the NeuroInsight server):**

```bash
ssh -L 8443:xnat.urmc.rochester.edu:443 dnakamura@smdodlogin01.urmc.rochester.edu -N
```

This forwards port 8443 on the NeuroInsight server through the HPC login node to the XNAT server. The HPC login node can reach XNAT because both are on the hospital network.

**Transfer setup** (XNAT pane):

| Field | Value |
|-------|-------|
| XNAT URL | `https://localhost:8443` |
| Skip SSL verification | **checked** |
| Username | `dnakamura` |
| Password | (her XNAT password) |

**Workflow:** On **Transfer**, connect XNAT in one pane and HPC in the other. Browse projects, select NIfTI files, transfer XNAT → HPC. On **Jobs**, compute **HPC** (already connected), browse the staged path, choose "Cortical Lesion Detection", submit.

If the XNAT server were publicly accessible (e.g., `https://central.xnat.org`), no tunnel would be needed. She would enter the real URL directly and leave SSL verification enabled.

### Prerequisites

1. **An XNAT account** with read access to at least one project
2. **Network access** from the NeuroInsight server to the XNAT instance (see "XNAT Behind a Firewall" below)

### Step 1: Connect to XNAT

1. Open the **Transfer** page
2. In either pane, select **XNAT**
3. Fill in:

| Field | Direct access | Via SSH tunnel |
|-------|---------------|----------------|
| XNAT URL | `https://xnat.urmc.rochester.edu` | `https://localhost:8443` |
| Skip SSL verification | unchecked | **checked** |
| Username | `dnakamura` | `dnakamura` |
| Password | (your XNAT password) | (your XNAT password) |

4. Click **Connect**
5. A green "Connected" badge confirms the connection

### Step 2: Browse and transfer data

After connecting, click **Browse** in the XNAT pane. The XNAT hierarchy is:

```
Project
 └── Subject
      └── Experiment (session)
           └── Scan
                └── Resource (NIFTI, DICOM, etc.)
                     └── Files
```

1. **Projects** -- select the project containing your data
2. **Subjects** -- click a subject to view their sessions
3. **Experiments** -- click a session to view scans
4. **Scans** -- click a scan to view available resources (NIFTI, DICOM, etc.)
5. **Resources** -- click a resource to see individual files
6. **Files** — select files, then transfer to your destination pane (Local, Remote, or HPC).

Use the breadcrumb navigation at the top to go back to any level.

### Step 3: Submit a job

Open **Jobs**, choose matching **Compute**, browse **Subject path** where files were staged, pick a pipeline, and submit. Use **Open in Jobs** after a transfer to prefill the path. Your XNAT archive is unchanged.

### XNAT Behind a Firewall (SSH Tunnel)

If NeuroInsight runs on an external server (e.g., AWS EC2) and the XNAT instance is on a private institutional network, the server cannot reach XNAT directly. Use an **SSH local port forward** through an intermediary that can reach both networks.

The intermediary can be any SSH-accessible machine that can reach the XNAT server -- typically an HPC login node on the same campus network.

#### Set up the tunnel

On the **NeuroInsight server**, run:

```bash
ssh -L 8443:xnat.urmc.rochester.edu:443 dnakamura@smdodlogin01.urmc.rochester.edu -N
```

This forwards local port `8443` through the HPC login node to the XNAT server. Replace the hostnames and username with your own. Keep this terminal open while using XNAT. Then use the "Via SSH tunnel" column in the Step 1 table above to fill in the UI fields.

Check **"Skip SSL verification"** when connecting via a tunnel -- the XNAT certificate was issued for the real hostname, not `localhost`, so verification will fail. This is safe because the tunnel itself provides encrypted transport.

### Troubleshooting XNAT Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | XNAT is unreachable -- check network/VPN, set up an SSH tunnel if on a different network |
| **"SSL certificate verification failed"** | Check **"Skip SSL verification"** if using an SSH tunnel or self-signed certificate |
| **"Authentication failed (401)"** | Wrong username or password |
| **"Access denied (403)"** | Account lacks permission for this XNAT instance -- contact your XNAT admin |
| **"XNAT REST API not found (404)"** | Incorrect URL -- verify the URL points to the XNAT web root (not a sub-path) |
| **Empty project list** | Your account may not have read access to any projects -- verify in the XNAT web UI |
| **Tunnel connection refused** | SSH tunnel may have closed -- check and restart the `ssh -L` command |

### Important Notes

- XNAT sessions expire after 15-30 minutes of inactivity. If you get errors after being idle, disconnect and reconnect.
- NeuroInsight uses the standard XNAT REST API and works with XNAT 1.7+ instances.

---

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions

---

MIT License. Tool-specific licenses: [TOOL_LICENSES.md](TOOL_LICENSES.md).
