"""
Celery tasks for async data transfers.

Production deployments may route transfers through Celery workers. These tasks
delegate to TransferManager so all Transfer page combinations share the same
large-file timeouts, batching, and resume behavior.
"""

import logging

from backend.core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_download(platform, file_ids, target_backend, target_path):
    from backend.core.transfer_manager import TransferManager, TransferRecord
    import uuid

    record = TransferRecord(
        transfer_id=str(uuid.uuid4()),
        direction="download",
        platform=platform,
        file_ids=file_ids,
        target_backend=target_backend,
        target_path=target_path,
    )
    TransferManager()._execute_download(record)
    return record.to_dict()


def _run_upload(source_backend, source_path, platform, dataset_id):
    from backend.core.transfer_manager import TransferManager, TransferRecord
    import uuid

    record = TransferRecord(
        transfer_id=str(uuid.uuid4()),
        direction="upload",
        platform=platform,
        target_backend=source_backend,
        source_path=source_path,
        dataset_id=dataset_id,
    )
    TransferManager()._execute_upload(record)
    return record.to_dict()


@celery_app.task(bind=True, name="transfer.download")
def transfer_download(
    self,
    platform: str,
    file_ids: list,
    target_backend: str,
    target_path: str,
):
    """Download files from a platform to a processing backend."""
    self.update_state(
        state="PROGRESS",
        meta={"status": "downloading", "files_completed": 0, "total_files": len(file_ids)},
    )
    result = _run_download(platform, file_ids, target_backend, target_path)
    return result


@celery_app.task(bind=True, name="transfer.upload")
def transfer_upload(
    self,
    platform: str,
    source_backend: str,
    source_path: str,
    dataset_id: str,
):
    """Upload files from a processing backend to a platform."""
    self.update_state(state="PROGRESS", meta={"status": "uploading"})
    result = _run_upload(source_backend, source_path, platform, dataset_id)
    return result
