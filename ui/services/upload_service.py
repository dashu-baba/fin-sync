"""Upload business logic service."""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from streamlit.runtime.uploaded_file_manager import UploadedFile
import hashlib

from core.config import config
from core.logger import get_logger
from core.utils import human_size, safe_write, sha256_bytes
from ingestion import read_pdf

log = get_logger("ui/services/upload_service")


class UploadService:
    """Handles file upload business logic."""
    
    @staticmethod
    def check_duplicate_by_hash(
        file_content: bytes,
        upload_dir: Path
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a file with the same content hash already exists.
        
        Args:
            file_content: The file content bytes
            upload_dir: Directory to check for existing files
            
        Returns:
            (is_duplicate, existing_filename)
        """
        file_hash = sha256_bytes(file_content)
        
        # Check all existing files in upload directory
        if upload_dir.exists():
            for existing_file in upload_dir.glob("*.pdf"):
                try:
                    with open(existing_file, "rb") as f:
                        existing_hash = sha256_bytes(f.read())
                    if existing_hash == file_hash:
                        log.warning(f"Duplicate file detected by hash: {existing_file.name}")
                        return True, existing_file.name
                except Exception as e:
                    log.error(f"Error checking file {existing_file}: {e}")
                    continue
        
        return False, None
    
    @staticmethod
    def check_duplicate_by_name(
        filename: str,
        upload_dir: Path
    ) -> bool:
        """
        Check if a file with the same name already exists.
        
        Args:
            filename: Name of the file to check
            upload_dir: Directory to check for existing files
            
        Returns:
            True if file exists, False otherwise
        """
        target_path = upload_dir / filename
        exists = target_path.exists()
        if exists:
            log.warning(f"Duplicate file detected by name: {filename}")
        return exists
    
    @staticmethod
    def validate_files(files: List[UploadedFile]) -> tuple[bool, Optional[str]]:
        """
        Validate uploaded files.
        
        Returns:
            (is_valid, error_message)
        """
        if not files:
            return False, "Please upload at least one file."
        
        if len(files) > config.max_files:
            return False, f"Too many files. Max allowed: {config.max_files}."
        
        total_size = sum(f.size for f in files)
        if total_size > config.max_total_mb * 1024 * 1024:
            return False, f"Total upload size exceeds {config.max_total_mb} MB."
        
        return True, None
    
    @staticmethod
    def process_upload(
        file: UploadedFile,
        upload_dir: Path,
        password: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Process a single uploaded file.
        
        Returns:
            File metadata dict or None if processing failed.
        """
        name = Path(file.name).name
        ext = Path(name).suffix.lower().lstrip(".")
        
        # Validate extension
        if ext not in config.allowed_ext:
            log.warning(f"Rejected file (ext): {name}")
            return None
        
        # Save file
        target_path = upload_dir / name
        try:
            safe_write(target_path, file.getvalue())
        except Exception as e:
            log.error(f"Failed to save {name}: {e}")
            return None
        
        # Build metadata
        meta = {
            "name": name,
            "ext": ext,
            "size_bytes": file.size,
            "size_human": human_size(file.size),
            "path": str(target_path),
        }
        log.info(f"Saved upload: {meta}")
        
        return meta
    
    @staticmethod
    def check_duplicate_in_elasticsearch(
        account_no: str,
        statement_from: str,
        statement_to: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a statement with the same account and period already exists in Elasticsearch.
        
        Args:
            account_no: Account number
            statement_from: Statement start date (ISO format: YYYY-MM-DD)
            statement_to: Statement end date (ISO format: YYYY-MM-DD)
            
        Returns:
            (is_duplicate, existing_source_file)
        """
        try:
            from elastic.client import es
            
            client = es()
            index = config.elastic_index_statements
            
            # Search for existing statement with same account and period
            query = {
                "bool": {
                    "must": [
                        {"term": {"account_no": account_no}},
                        {"term": {"statement_from": statement_from}},
                        {"term": {"statement_to": statement_to}}
                    ]
                }
            }
            
            response = client.search(
                index=index,
                query=query,
                size=1,
                _source=["source_file", "account_name", "bank_name"]
            )
            
            if response["hits"]["total"]["value"] > 0:
                hit = response["hits"]["hits"][0]["_source"]
                source_file = hit.get("source_file", "unknown")
                log.warning(
                    f"Duplicate statement found in Elasticsearch: "
                    f"Account={account_no}, Period={statement_from} to {statement_to}, "
                    f"Source={source_file}"
                )
                return True, source_file
            
            return False, None
            
        except Exception as e:
            log.error(f"Error checking Elasticsearch for duplicates: {e}")
            # Don't block upload if ES check fails
            return False, None
    
    @staticmethod
    def parse_pdf_info(
        file_path: str,
        password: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Parse PDF file to extract basic information.
        
        Returns:
            PDF info dict or None if parsing failed.
        """
        try:
            result = read_pdf(file_path, password=password)
            info = {
                "name": Path(file_path).name,
                "num_pages": result.num_pages,
                "encrypted": result.encrypted,
                "title": result.meta.title,
            }
            log.info(
                f"Parsed PDF: name={info['name']} "
                f"pages={info['num_pages']} "
                f"encrypted={info['encrypted']}"
            )
            return info
        except Exception as e:
            log.error(f"Failed to parse PDF {Path(file_path).name}: {e}")
            return None

