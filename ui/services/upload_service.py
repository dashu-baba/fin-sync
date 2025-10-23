"""Upload business logic service."""
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional, Any
from streamlit.runtime.uploaded_file_manager import UploadedFile

from core.config import config
from core.logger import get_logger
from core.utils import human_size, safe_write
from ingestion import read_pdf

log = get_logger("ui/services/upload_service")


class UploadService:
    """Handles file upload business logic."""
    
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

