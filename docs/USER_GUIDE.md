# NeuroInsight Research -- User Guide

Complete guide for deploying and using the NeuroInsight Research platform for neuroimaging analysis.

## Prerequisites

- Docker and Docker Compose (for local or containerized deployment)
- Python 3.10+ (for development setup)
- Node.js 18+ (for frontend development)
- 16GB+ RAM (32GB recommended for processing)
- SSH key-based authentication (for remote/HPC connections)

## Docker Installation

Docker is required for local processing and for containerized deployment. Choose the method for your platform.

### Linux (Ubuntu/Debian)

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

sudo systemctl start docker
sudo systemctl enable docker

sudo usermod -aG docker $USER
```

Log out and back in after the `usermod` command, then verify:

```bash
docker --version
docker compose version
docker run hello-world
```

### macOS

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
2. Open Docker Desktop and verify it is running
3. Open Terminal and verify:

```bash
docker --version
docker compose version
docker run hello-world
```

### Windows (WSL2)

1. Install Docker Desktop from https://www.docker.com/products/docker-desktop/
2. In Docker Desktop Settings, go to **Resources > WSL Integration** and enable your Ubuntu distribution
3. Open an Ubuntu terminal and verify `docker ps` works

If Docker Desktop is not installed yet, also enable WSL2:

```powershell
wsl --install -d Ubuntu
```

---

## macOS Notes

> **Recommendation:** For the best experience, especially with local processing, use **Linux** or **Windows with WSL2**. macOS is supported but has performance and compatibility limitations described below. If you use macOS primarily as an orchestration layer (submitting jobs to a remote server or HPC), these limitations do not apply.

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

## Deployment

### Using Docker Compose (recommended)

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research

cp .env.example .env
# Edit .env to set passwords (POSTGRES_PASSWORD, SECRET_KEY, etc.)

docker compose up -d
```

Access the UI at `http://localhost:3000` (or the port configured in `.env`).

### CLI Setup (recommended)

```bash
git clone https://github.com/phindagijimana/neuroinsight_research.git
cd neuroinsight_research
./research install        # Install deps, start infra, init DB
./research license        # Set up FreeSurfer / MELD license files
./research start          # Launch the app (production)
```

For development mode with hot-reload:

```bash
./research-dev start      # Backend auto-reload + Vite HMR frontend
```

The frontend dev server runs at `http://localhost:3000` and proxies API requests to the backend on port `3051`.

### Configuration

Key environment variables (set in `.env` or passed to Docker):

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
| **Singularity / Apptainer** | Container software designed for HPC environments. It serves the same purpose as Docker but is allowed on shared clusters where Docker is not (for security reasons). Apptainer is the newer name for Singularity. |
| **API key** | A credential (like a username and password combined into one token) used to authenticate with a web service programmatically. Pennsieve uses API keys for access. |
| **SSL certificate** | A digital certificate that verifies a website's identity and enables encrypted (HTTPS) connections. When you connect through an SSH tunnel, the certificate check may fail because the certificate was issued for the real hostname, not `localhost`. |

---

## Compute and Data Sources

NeuroInsight separates **where your data lives** from **where processing runs**. You can mix and match any data source with any compute backend to suit your environment.

### Data Sources

| Source | Description | Authentication |
|--------|-------------|----------------|
| **Local** | Files on the machine running NeuroInsight | None (filesystem access) |
| **Remote Server** | Files on any SSH-accessible Linux machine | SSH key (same credentials as compute) |
| **HPC** | Files on an HPC cluster filesystem | SSH key (same credentials as compute) |
| **Pennsieve** | Browse and download from the Pennsieve platform | API key + secret |
| **XNAT** | Browse and download from any XNAT instance | XNAT username + password |

### Compute Backends

| Backend | Description | Requirements |
|---------|-------------|--------------|
| **Local Docker** | Process on the NeuroInsight server using Docker containers | Docker installed |
| **Remote Server** | Process on a remote Linux machine via SSH + Docker | SSH access, Docker on remote |
| **HPC/SLURM** | Submit jobs to an HPC cluster via SLURM | SSH access, SLURM, Singularity/Apptainer |

You select a **data source** and a **compute backend** on the main processing page. Any combination works. For example: Local + Local Docker (simplest), Pennsieve + HPC/SLURM (download from cloud, process on cluster), or XNAT + Local Docker (download from hospital archive, process locally).

---

## Connecting to a Remote Server

NeuroInsight can run neuroimaging jobs on any SSH-accessible Linux machine with Docker installed. This is useful for offloading processing to a more powerful server, a cloud VM (AWS, GCP, Azure), or a lab workstation.

### Example Scenario

Dr. Reyes runs NeuroInsight on her laptop (8 GB RAM), but FreeSurfer and fMRIPrep need far more memory. Her lab has a shared Linux workstation (`brainlab-ws01.med.stanford.edu`) with 128 GB RAM, 32 CPU cores, and Docker installed. She wants to keep browsing and uploading files from her laptop while the heavy processing happens on the lab workstation.

**What she enters in the UI:**

| Field | Value |
|-------|-------|
| Data Source | **Local** (files are on her laptop) |
| Compute Source | **Remote Server** |
| Host | `brainlab-ws01.med.stanford.edu` |
| Username | `sreyes` |
| Port | `22` |

After clicking **Connect & Activate**, she uploads a T1 NIfTI file from her laptop. NeuroInsight transfers it to the workstation, runs FreeSurfer inside a Docker container there, and streams the results back.

If she were working from home and the workstation were behind the university firewall, she would first connect her VPN, then enter the same hostname. Alternatively, she could set up a reverse SSH tunnel as described in the HPC section below and use `localhost` / port `2222` instead.

### Prerequisites

1. **A Linux server** with Docker installed and running
2. **SSH access** from the NeuroInsight server to the remote machine (key-based authentication)
3. **Docker permissions** for your SSH user on the remote machine (user must be in the `docker` group)

### Step 1: Set Up SSH Key Authentication

Follow the SSH key setup in the HPC section below (Step 1a-1c). The process is identical -- generate a key on the NeuroInsight server and copy the public key to the remote machine's `~/.ssh/authorized_keys`.

### Step 2: Connect in the NeuroInsight UI

1. Open NeuroInsight in your browser
2. Under **Data Source**, select **Local** (or **Remote Server** if your data is on the remote machine)
3. Under **Compute Source**, select **Remote Server**
4. Fill in the SSH connection fields:
   - **Host** -- hostname or IP of the remote machine (or `localhost` if using a reverse tunnel)
   - **Username** -- your SSH username on the remote machine
   - **Port** -- `22` (default) or `2222` if using a reverse tunnel
5. Click **Connect & Activate**
6. A green "Connected" badge confirms the connection

If the remote server is behind a firewall, use a reverse SSH tunnel (same pattern as HPC Step 2 below).

---

## Connecting to Pennsieve

NeuroInsight can browse, download, and process data stored on the [Pennsieve](https://app.pennsieve.io) data management platform. Pennsieve is a cloud-based research data management system used by NIH SPARC, RE-JOIN, and other programs to store, organize, and share biomedical datasets.

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

1. Open NeuroInsight and click **Get Started**
2. Under **Data Source**, click the **Pennsieve** tab (blue database icon)
3. Paste the credentials you copied:
   - **API Key** -- e.g., `a3f8e1d2-7b4c-49e1-8f6a-2d9c0e5b1a73`
   - **API Secret** -- e.g., `b91d4f7e-3a28-41c5-9e0b-8c6f2d5a4e17`
4. Click **Connect**
5. A green "Connected" badge confirms the connection, showing your email and workspace (e.g., "james.wright@upenn.edu -- Penn Epilepsy Center")

### Step 3: Browse Data

After connecting, click **Browse** in the input section to open the Pennsieve Data Browser. The Pennsieve hierarchy is:

```
Workspace (Organization)
 └── Dataset
      └── Package (folder or file collection)
           └── Files
```

1. **Datasets** -- listed automatically after connecting; select the dataset containing your data
2. **Packages** -- navigate through folder structure within the dataset
3. **Files** -- select the files you want to process, then click **Select for Processing**

### Step 4: Process Data

After selecting files from Pennsieve, the files are downloaded to the NeuroInsight server and submitted to your chosen compute backend (Local Docker, Remote Server, or HPC/SLURM) for processing.

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

**What she enters in the NeuroInsight UI:**

| Field | Value |
|-------|-------|
| Data Source | **HPC** (her BIDS data is on `/projectnb/epilepsy/priya/`) |
| Compute Source | **HPC/SLURM** |
| Host | `localhost` (because of the reverse tunnel) |
| Username | `priya` |
| Port | `2222` (the tunnel port) |
| Work Directory | `/scratch/priya/neuroinsight` |
| Partition | `general` (auto-populated after connecting) |
| Modules | `singularity/3.10` |

After connecting, she browses her BIDS directory on the SCC through the file browser, selects all 50 subjects, chooses "Diffusion Full Pipeline", and clicks Submit. SLURM queues the jobs and processes multiple subjects in parallel across cluster nodes. She monitors everything from the SLURM Queue Monitor panel in her browser.

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

1. Open NeuroInsight in your browser
2. In the top toolbar, click the **HPC** tab (purple server icon)
3. Fill in the SSH connection fields:

| Field | Direct access (on campus) | Via reverse tunnel (off campus) |
|-------|---------------------------|--------------------------------|
| Host | `scc-login.bu.edu` | `localhost` |
| Username | `priya` | `priya` |
| Port | `22` | `2222` |

4. Click **Connect**
5. A green "Connected" badge appears on success

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

NeuroInsight can browse, download, and process data directly from any XNAT instance (CIDUR, CNDA, NITRC, Central, or your own). XNAT is an open-source imaging informatics platform used by hospitals and research centers to archive and share neuroimaging data.

### Example Scenario

Dr. Nakamura is a neuroradiologist at the University of Rochester Medical Center. The imaging center stores all research MRI data on an internal XNAT server at `https://xnat.urmc.rochester.edu`. She wants to run the cortical lesion detection pipeline on five subjects from the "Focal Epilepsy MRI Study" project.

NeuroInsight is running on an AWS EC2 instance, and the XNAT server is on the hospital's internal network (not accessible from the internet). Dr. Nakamura is already connected to the university HPC via NeuroInsight. She uses the HPC login node as a bridge to reach XNAT.

**Setting up the tunnel (on the NeuroInsight server):**

```bash
ssh -L 8443:xnat.urmc.rochester.edu:443 dnakamura@smdodlogin01.urmc.rochester.edu -N
```

This forwards port 8443 on the NeuroInsight server through the HPC login node to the XNAT server. The HPC login node can reach XNAT because both are on the hospital network.

**What she enters in the NeuroInsight UI:**

| Field | Value |
|-------|-------|
| Data Source | **XNAT** |
| Compute Source | **HPC/SLURM** (already connected) |
| XNAT URL | `https://localhost:8443` |
| Skip SSL verification | **checked** (required because the certificate is for `xnat.urmc.rochester.edu`, not `localhost`) |
| Username | `dnakamura` |
| Password | (her XNAT password) |

**Browsing data:** After connecting, she clicks Browse and sees the project list. She selects "Focal Epilepsy MRI Study", clicks into the first subject, opens their MR Session, selects Scan 1 (T1 MPRAGE), opens the NIFTI resource, and selects the `.nii.gz` file. She repeats for all five subjects.

**Processing:** She selects "Cortical Lesion Detection" as the pipeline and clicks Submit. NeuroInsight downloads the five NIfTI files from XNAT (via the tunnel), then submits them to the HPC for processing via SLURM.

If the XNAT server were publicly accessible (e.g., `https://central.xnat.org`), no tunnel would be needed. She would enter the real URL directly and leave SSL verification enabled.

### Prerequisites

1. **An XNAT account** with read access to at least one project
2. **Network access** from the NeuroInsight server to the XNAT instance (see "XNAT Behind a Firewall" below)

### Step 1: Connect to XNAT

1. Open NeuroInsight and click **Get Started**
2. Under **Data Source**, click the **XNAT** tab
3. Fill in:

| Field | Direct access | Via SSH tunnel |
|-------|---------------|----------------|
| XNAT URL | `https://xnat.urmc.rochester.edu` | `https://localhost:8443` |
| Skip SSL verification | unchecked | **checked** |
| Username | `dnakamura` | `dnakamura` |
| Password | (your XNAT password) | (your XNAT password) |

4. Click **Connect**
5. A green "Connected" badge confirms the connection

### Step 2: Browse Data

After connecting, click **Browse** in the input section to open the XNAT Data Browser. The XNAT hierarchy is:

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
6. **Files** -- select the files you want to process, then click **Select for Processing**

Use the breadcrumb navigation at the top to go back to any level.

### Step 3: Process Data

After selecting files from XNAT, the files are downloaded to the NeuroInsight server and submitted to your chosen compute backend (Local Docker, Remote Server, or HPC/SLURM) for processing.

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

MIT License. Individual neuroimaging tools (FreeSurfer, fMRIPrep, etc.) have their own licenses.
