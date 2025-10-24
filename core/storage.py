"""
Storage abstraction layer for local and GCS file operations.

Provides unified interface for file storage operations with support for:
- Local filesystem storage (development)
- Google Cloud Storage (production)

Implements automatic backend selection based on environment configuration.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import BinaryIO, Optional

from core.logger import get_logger

log = get_logger("core/storage")


class StorageBackend:
    """
    Abstract storage interface for file operations.
    
    All storage backend implementations must inherit from this class
    and implement all abstract methods.
    """
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """
        Save file to storage backend.
        
        Args:
            file_obj: Binary file object to save
            destination_path: Destination path for the file
            
        Returns:
            str: Full path or URL where file was saved
            
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError(f"{self.__class__.__name__}.save_file() must be implemented")
    
    def read_file(self, file_path: str) -> bytes:
        """
        Read file contents from storage.
        
        Args:
            file_path: Path to file to read
            
        Returns:
            bytes: File contents as bytes
            
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError(f"{self.__class__.__name__}.read_file() must be implemented")
    
    def delete_file(self, file_path: str) -> None:
        """
        Delete a file from storage.
        
        Args:
            file_path: Path to file to delete
            
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError(f"{self.__class__.__name__}.delete_file() must be implemented")
    
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in storage with optional prefix filter.
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            list[str]: List of file paths
            
        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError(f"{self.__class__.__name__}.list_files() must be implemented")


class LocalStorage(StorageBackend):
    """
    Local filesystem storage implementation.
    
    Stores files in a local directory on the filesystem.
    Suitable for development and testing environments.
    """
    
    def __init__(self, base_dir: Path):
        """
        Initialize local storage backend.
        
        Args:
            base_dir: Base directory for file storage
        """
        self.base_dir = Path(base_dir)
        
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            log.info(f"Local storage initialized: base_dir={self.base_dir}")
        except Exception as e:
            log.error(f"Failed to create local storage directory {self.base_dir}: {e}")
            raise
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """
        Save file to local filesystem.
        
        Args:
            file_obj: Binary file object to save
            destination_path: Relative path within base directory
            
        Returns:
            str: Full path where file was saved
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            full_path = self.base_dir / destination_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get file size for logging
            file_obj.seek(0, 2)  # Seek to end
            file_size = file_obj.tell()
            file_obj.seek(0)  # Reset to beginning
            
            with open(full_path, "wb") as f:
                f.write(file_obj.read())
            
            log.info(
                f"Saved file to local storage: path={full_path} "
                f"size={file_size} bytes"
            )
            return str(full_path)
            
        except Exception as e:
            log.error(
                f"Failed to save file to local storage: "
                f"destination={destination_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to save file to local storage: {e}")
    
    def read_file(self, file_path: str) -> bytes:
        """
        Read file from local filesystem.
        
        Args:
            file_path: Relative path within base directory
            
        Returns:
            bytes: File contents
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        try:
            full_path = self.base_dir / file_path
            
            if not full_path.exists():
                log.error(f"File not found in local storage: {full_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(full_path, "rb") as f:
                content = f.read()
            
            log.debug(f"Read file from local storage: path={full_path} size={len(content)} bytes")
            return content
            
        except FileNotFoundError:
            raise
        except Exception as e:
            log.error(
                f"Failed to read file from local storage: "
                f"path={file_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to read file from local storage: {e}")
    
    def delete_file(self, file_path: str) -> None:
        """
        Delete file from local filesystem.
        
        Args:
            file_path: Relative path within base directory
            
        Raises:
            IOError: If file cannot be deleted
        """
        try:
            full_path = self.base_dir / file_path
            
            if not full_path.exists():
                log.warning(f"File not found for deletion: {full_path}")
                return
            
            full_path.unlink()
            log.info(f"Deleted file from local storage: {full_path}")
            
        except Exception as e:
            log.error(
                f"Failed to delete file from local storage: "
                f"path={file_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to delete file from local storage: {e}")
    
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in local filesystem.
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            list[str]: List of relative file paths
        """
        try:
            search_path = self.base_dir / prefix if prefix else self.base_dir
            
            if not search_path.exists():
                log.debug(f"Search path does not exist: {search_path}")
                return []
            
            files = []
            for item in search_path.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(self.base_dir)
                    files.append(str(rel_path))
            
            log.debug(f"Listed {len(files)} files from local storage with prefix '{prefix}'")
            return files
            
        except Exception as e:
            log.error(
                f"Failed to list files from local storage: "
                f"prefix={prefix} error={e}",
                exc_info=True
            )
            return []


class GCSStorage(StorageBackend):
    """
    Google Cloud Storage backend implementation.
    
    Stores files in a Google Cloud Storage bucket.
    Suitable for production environments and cloud deployments.
    """
    
    def __init__(self, bucket_name: str):
        """
        Initialize GCS storage backend.
        
        Args:
            bucket_name: Name of the GCS bucket
            
        Raises:
            RuntimeError: If GCS client initialization fails
        """
        try:
            from google.cloud import storage
            from google.cloud.exceptions import GoogleCloudError
            
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket_name)
            self.bucket_name = bucket_name
            
            # Verify bucket exists
            if not self.bucket.exists():
                log.warning(f"GCS bucket does not exist: {bucket_name}")
            
            log.info(f"GCS storage initialized: bucket={bucket_name}")
            
        except Exception as e:
            log.error(
                f"Failed to initialize GCS storage: bucket={bucket_name} error={e}",
                exc_info=True
            )
            raise RuntimeError(f"Failed to initialize GCS storage: {e}")
    
    def save_file(self, file_obj: BinaryIO, destination_path: str) -> str:
        """
        Upload file to GCS.
        
        Args:
            file_obj: Binary file object to upload
            destination_path: Path within GCS bucket
            
        Returns:
            str: GCS URL (gs://bucket/path)
            
        Raises:
            IOError: If upload fails
        """
        try:
            blob = self.bucket.blob(destination_path)
            
            # Reset file pointer if needed
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0, 2)  # Seek to end for size
                file_size = file_obj.tell()
                file_obj.seek(0)  # Reset to beginning
            else:
                file_size = -1
            
            blob.upload_from_file(file_obj)
            
            gcs_url = f"gs://{self.bucket_name}/{destination_path}"
            log.info(
                f"Uploaded file to GCS: url={gcs_url} "
                f"size={file_size} bytes"
            )
            return gcs_url
            
        except Exception as e:
            log.error(
                f"Failed to upload file to GCS: "
                f"destination={destination_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to upload file to GCS: {e}")
    
    def read_file(self, file_path: str) -> bytes:
        """
        Download file from GCS.
        
        Args:
            file_path: Path within GCS bucket
            
        Returns:
            bytes: File contents
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If download fails
        """
        try:
            blob = self.bucket.blob(file_path)
            
            if not blob.exists():
                log.error(f"File not found in GCS: gs://{self.bucket_name}/{file_path}")
                raise FileNotFoundError(f"File not found in GCS: {file_path}")
            
            content = blob.download_as_bytes()
            
            log.debug(
                f"Downloaded file from GCS: "
                f"path=gs://{self.bucket_name}/{file_path} "
                f"size={len(content)} bytes"
            )
            return content
            
        except FileNotFoundError:
            raise
        except Exception as e:
            log.error(
                f"Failed to download file from GCS: "
                f"path={file_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to download file from GCS: {e}")
    
    def delete_file(self, file_path: str) -> None:
        """
        Delete file from GCS.
        
        Args:
            file_path: Path within GCS bucket
            
        Raises:
            IOError: If deletion fails
        """
        try:
            blob = self.bucket.blob(file_path)
            
            if not blob.exists():
                log.warning(
                    f"File not found for deletion: "
                    f"gs://{self.bucket_name}/{file_path}"
                )
                return
            
            blob.delete()
            log.info(f"Deleted file from GCS: gs://{self.bucket_name}/{file_path}")
            
        except Exception as e:
            log.error(
                f"Failed to delete file from GCS: "
                f"path={file_path} error={e}",
                exc_info=True
            )
            raise IOError(f"Failed to delete file from GCS: {e}")
    
    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in GCS bucket.
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            list[str]: List of file paths in bucket
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            files = [blob.name for blob in blobs]
            
            log.debug(
                f"Listed {len(files)} files from GCS bucket "
                f"{self.bucket_name} with prefix '{prefix}'"
            )
            return files
            
        except Exception as e:
            log.error(
                f"Failed to list files from GCS: "
                f"bucket={self.bucket_name} prefix={prefix} error={e}",
                exc_info=True
            )
            return []


def get_storage_backend() -> StorageBackend:
    """
    Factory function to get appropriate storage backend.
    
    Automatically selects backend based on environment:
    - Production with GCS bucket configured: GCSStorage
    - Otherwise: LocalStorage
    
    Returns:
        StorageBackend: Configured storage backend instance
        
    Raises:
        RuntimeError: If backend initialization fails
    """
    from core.config import config
    
    try:
        if config.gcs_bucket and config.environment == "production":
            log.info(
                f"Using GCS storage backend: "
                f"bucket={config.gcs_bucket} environment={config.environment}"
            )
            return GCSStorage(config.gcs_bucket)
        else:
            log.info(
                f"Using local storage backend: "
                f"base_dir={config.uploads_dir} environment={config.environment}"
            )
            return LocalStorage(config.uploads_dir)
            
    except Exception as e:
        log.error(f"Failed to initialize storage backend: {e}", exc_info=True)
        raise RuntimeError(f"Failed to initialize storage backend: {e}")

