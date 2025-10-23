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
            "Choose files",
            type=list(config.allowed_ext),
            accept_multiple_files=True,
            help="You can upload multiple statements (PDF or CSV)."
        )
        password = st.text_input(
            "Password (optional)",
            type="password",
            help="If your PDFs are encrypted, enter the password here."
        )
        submitted = st.form_submit_button("Continue ➜")
    
    return files, password, submitted

