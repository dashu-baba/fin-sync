"""Upload form component."""
from __future__ import annotations
from typing import Optional, Tuple, List
from streamlit.runtime.uploaded_file_manager import UploadedFile
import streamlit as st

from core.config import config


def render_upload_form() -> Tuple[Optional[List[UploadedFile]], Optional[str], bool]:
    """
    Render the file upload form.
    
    Returns:
        (files, password, submitted)
    """
    with st.form("upload_form", clear_on_submit=False):
        files = st.file_uploader(
            "Upload Bank Statement PDF",
            type=["pdf"],
            accept_multiple_files=False,
            help="Upload your bank statement PDF file. Encrypted PDFs are supported."
        )
        password = st.text_input(
            "Password (optional)",
            type="password",
            help="If your PDF is encrypted, enter the password here."
        )
        submitted = st.form_submit_button("Upload ➜")
    
    # Convert single file to list for compatibility
    files_list = [files] if files else None
    
    return files_list, password, submitted

