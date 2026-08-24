# Transfer page — large files and route matrix

The **Transfer** page moves data **both ways** between Local, Remote Server, HPC, Pennsieve, and XNAT. All routes share the same large-file behavior: **per-file timeouts**, **file-by-file batching**, **resume partial downloads**, and **skip completed files on re-run**.

See also: [USER_GUIDE.md — Transfer vs Jobs](USER_GUIDE.md#transfer-page-vs-jobs-page-planned-simplification).

---

## Transfer matrix

Each cell is **Source (row) → Destination (column)**. Every combination is supported on the Transfer page.

| From ↓ / To → | **Local** | **Remote** | **HPC** | **Pennsieve** | **XNAT** |
|---------------|-----------|------------|---------|---------------|----------|
| **Local** | Filesystem copy | SFTP | SFTP | Platform upload | Platform upload |
| **Remote** | SFTP | Remote `cp`* | Remote `cp`* | SFTP → upload | SFTP → upload |
| **HPC** | SFTP | Remote `cp`* | Remote `cp`* | SFTP → upload | SFTP → upload |
| **Pennsieve** | HTTP download | `curl -C -`† or indirect | `curl -C -`† or indirect | Platform P2P | Platform P2P |
| **XNAT** | HTTP download | Indirect‡ | Indirect‡ | Platform P2P | Platform P2P |

\*Same SSH host — cluster-side `cp` (no laptop hop); falls back to SFTP if needed.  
†Direct presigned `curl` on the remote/HPC host (data bypasses NeuroInsight).  
‡Download via NeuroInsight (XNAT session/tunnel), then SFTP to remote/HPC.

**Typical workflow:** Transfer data to compute (e.g. Pennsieve → HPC) → **Jobs** runs on that path → Transfer results back if needed.

---

## Large-file features (all routes)

| Feature | Behavior |
|---------|----------|
| **Per-file timeout** | Default **24 h** per file for `curl` and SFTP/scp (not one timeout for the whole folder). |
| **Batching** | Folders expand to files; each file transfers separately with progress logging. |
| **Resume** | Partial files continue via HTTP Range (platform→local) or `curl -C -` (Pennsieve→remote/HPC). |
| **Re-run skip** | Repeat Transfer to the **same destination** — files already at the correct byte size are skipped. |
| **Retries** | Pennsieve direct curl retries with a **fresh presigned URL** (default 3 attempts). |

**Best practice for 300GB+:** Pennsieve → **HPC** (direct curl). Avoid routing huge datasets through your laptop.

---

## Configuration

Set in `.env` (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `NIR_TRANSFER_CURL_TIMEOUT_SEC` | `86400` | Max seconds per file for cluster `curl` |
| `NIR_TRANSFER_SCP_TIMEOUT_SEC` | `86400` | Max seconds per file for SFTP/scp |
| `NIR_TRANSFER_CURL_RETRIES` | `3` | Retries with fresh presigned URL |
| `NIR_TRANSFER_SKIP_COMPLETE` | `1` | Skip destination files that already match size |
| `NIR_TRANSFER_CHUNK_BYTES` | `1048576` | HTTP stream chunk size (1 MiB) |
| `NIR_TRANSFER_BATCH_LOG_EVERY` | `25` | Log every N files in large folder transfers |

**After a failure:** run the same Transfer again (same destination path). Completed files are skipped; partials resume where supported.

---

## Limitations

- **One SSH host at a time** — Remote↔HPC `cp` requires the same connected host; two clusters at once is not supported.
- **SCP mid-file** — if scp fails halfway, re-run skips only **complete** files; the partial file restarts (no byte-level scp resume).
- **Platform upload skip** — re-run skip applies to filesystem destinations; Pennsieve/XNAT “already uploaded” is not checked automatically.

For manual recovery on a cluster: `curl -C -` or `rsync` to the same path, then use that path on Jobs.

---

## Implementation reference

| Component | Path |
|-----------|------|
| Route orchestration | `backend/core/transfer_manager.py` |
| Shared I/O (resume, skip, scp) | `backend/core/transfer_io.py` |
| Timeouts / env defaults | `backend/core/transfer_settings.py` |
