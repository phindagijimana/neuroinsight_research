"""
Celery tasks for async data transfers between platforms and processing backends.

These tasks are used when transfers need to survive server restarts or
when the transfer should be handled by a Celery worker rather than a
background thread. The TransferManager uses threads for immediate
responsiveness, but these tasks can be used as an alternative for
production deployments with dedicated workers.
"""

import logging
import os
import tempfile

from backend.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="transfer.download")
def transfer_download(
    self,
    platform: str,
    file_ids: list,
    target_backend: str,
    target_path: str,
):
    """Download files from a platform to a processing backend.

    Progress is reported via Celery task state updates.
    """
    from backend.routes.platform import _get_connector

    connector = _get_connector(platform)
    if not connector.is_connected():
        raise RuntimeError(f"Not connected to {platform}")

    total = len(file_ids)
    self.update_state(
        state="PROGRESS",
        meta={"status": "downloading", "files_completed": 0, "total_files": total, "progress_percent": 0},
    )

    if target_backend == "local":
        os.makedirs(target_path, exist_ok=True)
        for i, fid in enumerate(file_ids):
            dest = os.path.join(target_path, f"file_{i}")
            try:
                connector.download_file(fid, dest)
            except Exception as e:
                logger.warning("download %s failed: %s", fid, e)
            self.update_state(
                state="PROGRESS",
                meta={
                    "status": "downloading",
                    "files_completed": i + 1,
                    "total_files": total,
                    "progress_percent": ((i + 1) / total) * 100,
                },
            )
    else:
        from backend.core.ssh_manager import SSHManager

        ssh = SSHManager.get_instance()
        with tempfile.TemporaryDirectory(prefix="neuroinsight_dl_") as tmpdir:
            for i, fid in enumerate(file_ids):
                try:
                    local_tmp = os.path.join(tmpdir, f"file_{i}")
                    connector.download_file(fid, local_tmp)
                    remote_dest = os.path.join(target_path, os.path.basename(local_tmp))
                    ssh.put_file(local_tmp, remote_dest)
                except Exception as e:
                    logger.warning("transfer %s failed: %s", fid, e)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "status": "downloading",
                        "files_completed": i + 1,
                        "total_files": total,
                        "progress_percent": ((i + 1) / total) * 100,
                    },
                )

    return {"status": "completed", "files_completed": total, "total_files": total, "progress_percent": 100}


@celery_app.task(bind=True, name="transfer.upload")
def transfer_upload(
    self,
    platform: str,
    source_backend: str,
    source_path: str,
    dataset_id: str,
):
    """Upload files from a processing backend to a platform."""
    from backend.routes.platform import _get_connector

    connector = _get_connector(platform)
    if not connector.is_connected():
        raise RuntimeError(f"Not connected to {platform}")

    files_to_upload = []

    if source_backend == "local":
        if os.path.isdir(source_path):
            for root, _, fnames in os.walk(source_path):
                for fname in fnames:
                    files_to_upload.append(os.path.join(root, fname))
        elif os.path.isfile(source_path):
            files_to_upload.append(source_path)
    else:
        from backend.core.ssh_manager import SSHManager

        ssh = SSHManager.get_instance()
        with tempfile.TemporaryDirectory(prefix="neuroinsight_ul_") as tmpdir:
            try:
                listing = ssh.list_dir(source_path)
                for item in listing:
                    if item.get("type") == "file":
                        fname = os.path.basename(item["path"])
                        local_tmp = os.path.join(tmpdir, fname)
                        ssh.get_file(item["path"], local_tmp)
                        files_to_upload.append(local_tmp)
            except Exception:
                local_tmp = os.path.join(tmpdir, os.path.basename(source_path))
                ssh.get_file(source_path, local_tmp)
                files_to_upload.append(local_tmp)

    total = len(files_to_upload)
    for i, fpath in enumerate(files_to_upload):
        try:
            connector.upload_file(fpath, dataset_id)
        except Exception as e:
            logger.warning("upload %s failed: %s", fpath, e)
        self.update_state(
            state="PROGRESS",
            meta={
                "status": "uploading",
                "files_completed": i + 1,
                "total_files": total,
                "progress_percent": ((i + 1) / max(total, 1)) * 100,
            },
        )

    return {"status": "completed", "files_completed": total, "total_files": total, "progress_percent": 100}
