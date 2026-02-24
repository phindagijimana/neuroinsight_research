# Troubleshooting Guide

Common issues and solutions for NeuroInsight Research.

## Connection Issues

### SSH / HPC

| Problem | Solution |
|---------|----------|
| "Connection timed out" | HPC is unreachable -- check VPN, verify hostname, or set up a reverse SSH tunnel (see USER_GUIDE.md) |
| "Authentication failed" | SSH key not on the remote machine -- copy the NeuroInsight server's public key to `~/.ssh/authorized_keys` on the target |
| "Connection refused" | Wrong port, or the hostname is a web portal (e.g., Open OnDemand) not an SSH server -- use the actual login node |
| Reverse tunnel disconnects | Add `-o ServerAliveInterval=60` to the `ssh` command to keep the tunnel alive |

### XNAT

| Problem | Solution |
|---------|----------|
| "SSL certificate verification failed" | Check the **Skip SSL verification** checkbox if connecting through an SSH tunnel |
| "Authentication failed (401)" | Wrong XNAT username or password |
| "404 Not Found" when browsing | Incorrect XNAT URL -- ensure the URL points to the XNAT web root |
| Empty project list | Your XNAT account may lack read access -- check permissions in the XNAT web UI |

### Pennsieve

| Problem | Solution |
|---------|----------|
| "Authentication failed" | API key or secret is incorrect -- generate a new pair from your Pennsieve profile |
| "Connection timed out" | Network issue reaching `api.pennsieve.io` -- check firewall or proxy settings |
| "Token expired" | Session expired after long idle -- click Disconnect and reconnect |

## Job Failures

### SLURM Jobs

| Problem | Solution |
|---------|----------|
| Job status FAILED | Check the job log file in the work directory (e.g., `<work_dir>/slurm_<jobid>/step_1_*.log`) |
| TIMEOUT | Increase `time_hours` in the plugin YAML or choose a partition with longer time limits |
| OUT_OF_MEMORY | Increase `mem_gb` in the plugin YAML |
| "Singularity image not found" | Ensure the container `.sif` file exists on the HPC at the path configured in the plugin |
| "Module not found" | Verify the module name (e.g., `singularity/3.8`) matches your cluster's available modules (`module avail`) |

### Local Docker Jobs

| Problem | Solution |
|---------|----------|
| "Docker daemon not running" | Start Docker: `sudo systemctl start docker` |
| "Permission denied" on Docker socket | Add your user to the `docker` group: `sudo usermod -aG docker $USER`, then log out and back in |
| Container exits immediately | Check container logs: `docker logs <container_id>` |

## Frontend / UI

| Problem | Solution |
|---------|----------|
| UI does not load | Verify the backend is running (`curl http://localhost:3001/health`) and check that the frontend port is correct |
| "Network Error" in browser | CORS issue or backend not reachable -- check `VITE_API_URL` and `CORS_ORIGINS` in `.env` |
| SLURM queue not updating | Check that the HPC connection is still active (green badge) -- reconnect if needed |

## Database

| Problem | Solution |
|---------|----------|
| "Database connection refused" | Ensure PostgreSQL is running. For Docker Compose: `docker compose ps` to check service status |
| Migration errors | Run `alembic upgrade head` from the backend directory |

## Getting Help

- **GitHub Issues**: [Report a bug](https://github.com/phindagijimana/neuroinsight_research/issues)
- **User Guide**: See [USER_GUIDE.md](USER_GUIDE.md) for detailed setup and connection instructions
