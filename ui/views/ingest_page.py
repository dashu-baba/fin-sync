"""Ingest page - orchestrates file upload, parsing, and indexing."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st

from core.logger import get_logger
from ui.services import SessionManager, UploadService
from ui.components import (
    render_upload_form,
    render_file_list,
    render_parse_section,
)

log = get_logger("ui/pages/ingest_page")


def render() -> None:
    """Render the ingest page."""
    # Initialize session state
    SessionManager.init_session()
    
    # Main title
    st.title("💰 FinSync — Personal Finance Manager")
    st.header("📥 Ingest Bank Statements")
    st.caption("Upload, parse, and index your bank statements")
    
    # Render upload form
    files, password, submitted = render_upload_form()
    
    # Handle form submission
    if submitted:
        _handle_upload(files, password)
    
    # Render parse section if files are uploaded
    uploads_meta = SessionManager.get_uploads_meta()
    current_password = SessionManager.get_password()
    render_parse_section(uploads_meta, current_password)


def _handle_upload(files, password: str) -> None:
    """
    Handle file upload submission.
    
    Args:
        files: Uploaded files from Streamlit
        password: Password for encrypted PDFs
    """
    # Validate files
    is_valid, error_msg = UploadService.validate_files(files)
    if not is_valid:
        if error_msg:
            st.warning(error_msg) if "at least one" in error_msg else st.error(error_msg)
            if "at least one" not in error_msg:
                log.warning(f"Upload validation failed: {error_msg}")
        return
    
    # Process uploads
    upload_dir = SessionManager.get_upload_dir()
    saved_files: List[Dict] = []
    parsed_info: List[Dict] = []
    
    for file in files:
        # Process upload
        meta = UploadService.process_upload(file, upload_dir, password)
        if not meta:
            st.error(f"❌ Could not process: {file.name}")
            continue
        
        saved_files.append(meta)
        
        # Parse PDF info if applicable
        if meta["ext"] == "pdf":
            pdf_info = UploadService.parse_pdf_info(
                meta["path"],
                password=password or None
            )
            if pdf_info:
                parsed_info.append(pdf_info)
            else:
                st.warning(f"Could not parse {meta['name']}. It will be skipped for now.")
    
    # Save to session state
    if saved_files:
        SessionManager.set_uploads_meta(saved_files)
        SessionManager.set_password(password or "")
        
        # Display results
        render_file_list(saved_files, password or "", parsed_info)
    else:
        st.error("No valid files were uploaded.")

