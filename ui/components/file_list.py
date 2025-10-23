"""File list display component."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st


def render_file_list(
    saved_files: List[Dict],
    password: str,
    parsed_info: List[Dict]
) -> None:
    """
    Display list of uploaded and parsed files.
    
    Args:
        saved_files: List of saved file metadata
        password: Session password (for lock icon)
        parsed_info: List of parsed PDF information
    """
    if not saved_files:
        return
    
    st.success(f"✅ {len(saved_files)} file(s) uploaded successfully.")
    
    with st.expander("Review uploaded files"):
        for meta in saved_files:
            lock_icon = "🔒" if password else ""
            st.write(
                f"• **{meta['name']}** — "
                f"{meta['size_human']} ({meta['ext']}) {lock_icon}"
            )
    
    if parsed_info:
        st.subheader("📄 PDF Parse Summary")
        for info in parsed_info:
            enc = "Yes" if info["encrypted"] else "No"
            st.write(
                f"• {info['name']} — "
                f"pages: {info['num_pages']}, "
                f"encrypted: {enc}, "
                f"title: {info['title'] or 'N/A'}"
            )

