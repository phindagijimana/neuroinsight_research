"""
MinIO Object Storage Service

Provides file upload/download/listing for neuroimaging inputs and outputs.

Buckets:
    neuroinsight-inputs   -- uploaded scans (T1w, FLAIR, etc.)
    neuroinsight-outputs  -- job results (native + bundle)

Usage:
    from backend.core.storage importstorage

    # Upload a file
    storage.upload_input("sub-001_T1w.nii.gz", "/local/path/T1w.nii.gz")

    # Download a result
    storage.download_output(job_id, "bundle/volumes/orig.nii.gz", "/tmp/orig.nii.gz")

    # Get presigned URL (for browser download)
    url = storage.presign_output(job_id, "bundle/volumes/orig.nii.gz")
"""

import io
import logging
import os
from pathlib import Path
from typing import BinaryIO, List, Optional

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

MINIO_HOST = os.getenv("MINIO_HOST", "localhost")
MINIO_PORT = int(os.getenv("MINIO_PORT", "9000"))
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin_secure")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

BUCKET_INPUTS = os.getenv("MINIO_BUCKET_INPUTS", "neuroinsight-inputs")
BUCKET_OUTPUTS = os.getenv("MINIO_BUCKET_OUTPUTS", "neuroinsight-outputs")


class StorageService:
    """MinIO-backed object storage for neuroimaging data."""

    def __init__(self):
        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            endpoint = f"{MINIO_HOST}:{MINIO_PORT}"
            self._client = Minio(
                endpoint,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
                secure=MINIO_SECURE,
            )
            # Ensure buckets exist
            for bucket in [BUCKET_INPUTS, BUCKET_OUTPUTS]:
                if not self._client.bucket_exists(bucket):
                    self._client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")
        return self._client

    # -- Inputs --

    def upload_input(self, object_name: str, file_path: str) -> str:
        """Upload a local file to the inputs bucket.

        Args:
            object_name: Key in the bucket (e.g. "sub-001/T1w.nii.gz")
            file_path: Local filesystem path

        Returns:
            Full object path  "neuroinsight-inputs/sub-001/T1w.nii.gz"
        """
        self.client.fput_object(BUCKET_INPUTS, object_name, file_path)
        logger.info(f"Uploaded input: {object_name}")
        return f"{BUCKET_INPUTS}/{object_name}"

    def upload_input_stream(self, object_name: str, data: BinaryIO, length: int) -> str:
        """Upload from a stream (e.g. FastAPI UploadFile)."""
        self.client.put_object(BUCKET_INPUTS, object_name, data, length)
        return f"{BUCKET_INPUTS}/{object_name}"

    def download_input(self, object_name: str, dest_path: str) -> str:
        """Download an input file to a local path."""
        self.client.fget_object(BUCKET_INPUTS, object_name, dest_path)
        return dest_path

    def get_input_url(self, object_name: str, expires_hours: int = 24) -> str:
        """Get a presigned download URL for an input file."""
        from datetime import timedelta
        return self.client.presigned_get_object(
            BUCKET_INPUTS, object_name, expires=timedelta(hours=expires_hours)
        )

    # -- Outputs --

    def upload_output(self, job_id: str, object_name: str, file_path: str) -> str:
        """Upload a job output file.

        Args:
            job_id: Job UUID
            object_name: Relative path within job outputs (e.g. "bundle/volumes/orig.nii.gz")
            file_path: Local filesystem path
        """
        key = f"{job_id}/{object_name}"
        self.client.fput_object(BUCKET_OUTPUTS, key, file_path)
        logger.debug(f"Uploaded output: {key}")
        return f"{BUCKET_OUTPUTS}/{key}"

    def upload_output_dir(self, job_id: str, local_dir: str, prefix: str = "") -> int:
        """Recursively upload an entire directory as job outputs.

        Returns:
            Number of files uploaded
        """
        count = 0
        base = Path(local_dir)
        for filepath in base.rglob("*"):
            if filepath.is_file():
                rel = filepath.relative_to(base)
                key = f"{prefix}/{rel}" if prefix else str(rel)
                self.upload_output(job_id, key, str(filepath))
                count += 1
        logger.info(f"Uploaded {count} output files for job {job_id[:8]}")
        return count

    def download_output(self, job_id: str, object_name: str, dest_path: str) -> str:
        """Download a job output file."""
        key = f"{job_id}/{object_name}"
        self.client.fget_object(BUCKET_OUTPUTS, key, dest_path)
        return dest_path

    def get_output_url(self, job_id: str, object_name: str, expires_hours: int = 24) -> str:
        """Get a presigned download URL for a job output file."""
        from datetime import timedelta
        key = f"{job_id}/{object_name}"
        return self.client.presigned_get_object(
            BUCKET_OUTPUTS, key, expires=timedelta(hours=expires_hours)
        )

    def list_outputs(self, job_id: str, prefix: str = "") -> List[dict]:
        """List all output files for a job.

        Returns:
            List of dicts with 'name', 'size', 'last_modified' keys
        """
        key_prefix = f"{job_id}/{prefix}" if prefix else f"{job_id}/"
        objects = self.client.list_objects(BUCKET_OUTPUTS, prefix=key_prefix, recursive=True)
        results = []
        for obj in objects:
            # Strip the job_id prefix for the relative name
            rel_name = obj.object_name
            if rel_name.startswith(f"{job_id}/"):
                rel_name = rel_name[len(f"{job_id}/"):]
            results.append({
                "name": rel_name,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
            })
        return results

    # -- Health --

    def health_check(self) -> dict:
        try:
            buckets = [b.name for b in self.client.list_buckets()]
            return {
                "healthy": True,
                "endpoint": f"{MINIO_HOST}:{MINIO_PORT}",
                "buckets": buckets,
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


# Singleton
storage = StorageService()
