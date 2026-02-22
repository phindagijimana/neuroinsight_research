"""
Storage service for managing file uploads and retrieval.

This service abstracts file storage operations, supporting both
local filesystem and S3-compatible (MinIO) storage backends.
"""

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    Minio = None
    S3Error = None

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StorageService:
    """
    Service class for file storage operations.

    Supports MinIO/S3 storage backend for web deployment.
    """
    
    def __init__(self):
        """Initialize storage service with MinIO or local storage."""
        self.use_s3 = False
        self.local_base_dir = None

        # Try MinIO first (production/cloud deployment)
        if MINIO_AVAILABLE and hasattr(settings, "minio_endpoint"):
            try:
                self.use_s3 = True
                self.client = Minio(
                    settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_use_ssl,
                )
                self._ensure_bucket()
                logger.info("storage_initialized_minio", endpoint=settings.minio_endpoint)
            except Exception as e:
                logger.warning("minio_connection_failed", error=str(e))
                self.use_s3 = False

        # Fallback to local storage if MinIO not available or fails
        if not self.use_s3:
            from pathlib import Path
            self.local_base_dir = Path(settings.upload_dir).parent
            self.local_base_dir.mkdir(parents=True, exist_ok=True)
            logger.info("storage_initialized_local", base_dir=str(self.local_base_dir))
    
    def _ensure_bucket(self) -> None:
        """Ensure MinIO bucket exists."""
        try:
            if not self.client.bucket_exists(settings.minio_bucket):
                self.client.make_bucket(settings.minio_bucket)
                logger.info("bucket_created", bucket=settings.minio_bucket)
        except S3Error as e:
            logger.error("bucket_creation_failed", error=str(e))
    
    def save_upload(self, file: BinaryIO, filename: str) -> str:
        """
        Save an uploaded file.
        
        Args:
            file: File-like object to save
            filename: Target filename
        
        Returns:
            Storage path or URI
        """
        # Always persist locally first to guarantee availability for processing
        local_path = self._save_to_local(file, filename)
        
        # Best-effort upload to S3 in background context (synchronous but non-blocking for processing)
        if self.use_s3:
            try:
                # Upload from the local file to avoid file pointer issues
                with open(local_path, "rb") as fsrc:
                    self._save_to_s3(fsrc, filename)
            except S3Error as e:
                # Log but don't fail upload flow; processing will use local file
                logger.warning("s3_upload_deferred", error=str(e), filename=filename)
        
        # Return local path so downstream processing uses local file (avoids S3 read-after-write)
        return local_path

    def save_upload_local_then_s3(self, file: BinaryIO, filename: str) -> str:
        """Explicit helper to save locally then mirror to S3; returns local path."""
        return self.save_upload(file, filename)
    
    def _save_to_local(self, file: BinaryIO, filename: str) -> str:
        """Save file to local filesystem."""
        file_path = Path(settings.upload_dir) / filename
        
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file, f)
        
        logger.info("file_saved_local", path=str(file_path))
        
        return str(file_path)
    
    def _save_to_s3(self, file: BinaryIO, filename: str) -> str:
        """Save file to MinIO/S3."""
        object_name = f"uploads/{filename}"
        
        try:
            # Get file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            self.client.put_object(
                settings.minio_bucket,
                object_name,
                file,
                file_size,
            )
            
            logger.info("file_saved_s3", object_name=object_name)
            
            return f"s3://{settings.minio_bucket}/{object_name}"
        
        except S3Error as e:
            logger.error("s3_upload_failed", error=str(e))
            raise
    
    def get_file_path(self, storage_path: str) -> str:
        """
        Get local file path from storage path.
        
        For S3 URIs, this would download the file locally.
        For local paths, returns the path as-is.
        
        Args:
            storage_path: Storage path or S3 URI
        
        Returns:
            Local file path
        """
        if storage_path.startswith("s3://"):
            # Extract object name from S3 URI
            parts = storage_path.replace("s3://", "").split("/", 1)
            bucket = parts[0]
            object_name = parts[1]
            
            # Download to local temp directory
            local_path = Path(settings.upload_dir) / Path(object_name).name
            
            # Retry download to tolerate transient S3 propagation delays
            import time
            last_err: Exception | None = None
            for attempt in range(1, 4):
                try:
                    self.client.fget_object(bucket, object_name, str(local_path))
                    logger.info(
                        "file_downloaded_s3",
                        object_name=object_name,
                        attempt=attempt,
                    )
                    return str(local_path)
                except S3Error as e:
                    last_err = e
                    logger.warning(
                        "s3_download_retry",
                        attempt=attempt,
                        max_attempts=3,
                        error=str(e),
                        object_name=object_name,
                    )
                    # Exponential backoff: 0.5s, 1s, 2s
                    time.sleep(0.5 * (2 ** (attempt - 1)))
            # After retries, raise the last error
            logger.error("s3_download_failed", error=str(last_err), object_name=object_name)
            raise last_err
        else:
            return storage_path
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            storage_path: Storage path or S3 URI
        
        Returns:
            True if deleted successfully
        """
        try:
            if storage_path.startswith("s3://"):
                parts = storage_path.replace("s3://", "").split("/", 1)
                bucket = parts[0]
                object_name = parts[1]
                
                self.client.remove_object(bucket, object_name)
                logger.info("file_deleted_s3", object_name=object_name)
            else:
                Path(storage_path).unlink(missing_ok=True)
                logger.info("file_deleted_local", path=storage_path)
            
            return True
        
        except Exception as e:
            logger.error("file_deletion_failed", error=str(e))
            return False

