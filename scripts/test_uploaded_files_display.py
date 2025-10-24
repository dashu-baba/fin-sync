"""Test script for uploaded files display component."""
from __future__ import annotations
from pathlib import Path
import sys

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger
from core.storage import get_storage_backend

log = get_logger("test_uploaded_files_display")


def test_list_uploaded_files():
    """Test listing uploaded files from storage backend."""
    try:
        storage = get_storage_backend()
        log.info(f"Storage backend initialized: {type(storage).__name__}")
        
        files = storage.list_files()
        log.info(f"Total files found: {len(files)}")
        
        # Filter PDF files
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        log.info(f"PDF files found: {len(pdf_files)}")
        
        # Display file info
        for idx, file_path in enumerate(pdf_files, 1):
            log.info(f"{idx}. {Path(file_path).name}")
        
        if not pdf_files:
            log.info("No PDF files uploaded yet. Upload some files first!")
        
        log.info("✓ Test completed successfully")
        
    except Exception as e:
        log.error(f"Test failed: {e!r}")
        raise


if __name__ == "__main__":
    test_list_uploaded_files()

