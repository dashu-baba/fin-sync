"""
Storage abstraction layer for local and GCS file operations.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import BinaryIO
from io import BytesIO

from loguru import logger


class StorageBackend:
    """Abstract storage interface."""
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """Save file and return the saved path."""
        raise NotImplementedError
    
    def read_file(self, file_path: str) -> bytes:
        """Read file contents."""
        raise NotImplementedError
    
    def delete_file(self, file_path: str) -> None:
        """Delete a file."""
        raise NotImplementedError
    
    def list_files(self, prefix: str = "") -> list[str]:
        """List files with optional prefix."""
        raise NotImplementedError


class LocalStorage(StorageBackend):
    """Local filesystem storage."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """Save file to local filesystem."""
        full_path = self.base_dir / destination_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "wb") as f:
            f.write(file_obj.read())
        
        logger.info(f"Saved file to local storage: {full_path}")
        return str(full_path)
    
    def read_file(self, file_path: str) -> bytes:
        """Read file from local filesystem."""
        full_path = self.base_dir / file_path
        with open(full_path, "rb") as f:
            return f.read()
    
    def delete_file(self, file_path: str) -> None:
        """Delete file from local filesystem."""
        full_path = self.base_dir / file_path
        if full_path.exists():
            full_path.unlink()
            logger.info(f"Deleted file from local storage: {full_path}")
    
    def list_files(self, prefix: str = "") -> list[str]:
        """List files in local filesystem."""
        search_path = self.base_dir / prefix if prefix else self.base_dir
        if not search_path.exists():
            return []
        
        files = []
        for item in search_path.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(self.base_dir)
                files.append(str(rel_path))
        return files


class GCSStorage(StorageBackend):
    """Google Cloud Storage backend."""
    
    def __init__(self, bucket_name: str):
        from google.cloud import storage
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.bucket_name = bucket_name
        logger.info(f"Initialized GCS storage with bucket: {bucket_name}")
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """Upload file to GCS."""
        blob = self.bucket.blob(destination_path)
        
        # Reset file pointer if needed
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        
        blob.upload_from_file(file_obj)
        logger.info(f"Uploaded file to GCS: gs://{self.bucket_name}/{destination_path}")
        return f"gs://{self.bucket_name}/{destination_path}"
    
    def read_file(self, file_path: str) -> bytes:
        """Download file from GCS."""
        blob = self.bucket.blob(file_path)
        return blob.download_as_bytes()
    
    def delete_file(self, file_path: str) -> None:
        """Delete file from GCS."""
        blob = self.bucket.blob(file_path)
        blob.delete()
        logger.info(f"Deleted file from GCS: gs://{self.bucket_name}/{file_path}")
    
    def list_files(self, prefix: str = "") -> list[str]:
        """List files in GCS bucket."""
        blobs = self.bucket.list_blobs(prefix=prefix)
        return [blob.name for blob in blobs]


def get_storage_backend() -> StorageBackend:
    """Factory function to get appropriate storage backend."""
    from core.config import config
    
    if config.gcs_bucket and config.environment == "production":
        logger.info("Using GCS storage backend")
        return GCSStorage(config.gcs_bucket)
    else:
        logger.info("Using local storage backend")
        return LocalStorage(config.uploads_dir)

