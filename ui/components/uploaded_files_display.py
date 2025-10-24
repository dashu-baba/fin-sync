"""Component to display previously uploaded files."""
from __future__ import annotations
from typing import List, Dict
from pathlib import Path
from datetime import datetime
import streamlit as st

from core.logger import get_logger
from core.storage import get_storage_backend
from core.config import config

log = get_logger("ui/components/uploaded_files_display")


def get_uploaded_files_list() -> List[Dict]:
    """
    Get list of uploaded files from storage backend.
    
    Returns:
        List of file info dictionaries with name, size, and modified date
    """
    try:
        storage = get_storage_backend()
        files = storage.list_files()
        
        # Filter for PDF files only
        pdf_files = [f for f in files if f.lower().endswith('.pdf')]
        
        file_list = []
        for file_path in pdf_files:
            try:
                filename = Path(file_path).name
                
                # Try to get file size
                try:
                    file_content = storage.read_file(file_path)
                    size_bytes = len(file_content)
                    size_human = _format_size(size_bytes)
                except Exception as e:
                    log.warning(f"Could not read file size for {filename}: {e}")
                    size_bytes = 0
                    size_human = "Unknown"
                
                file_list.append({
                    "name": filename,
                    "path": file_path,
                    "size_bytes": size_bytes,
                    "size_human": size_human
                })
            except Exception as e:
                log.error(f"Error processing file {file_path}: {e}")
                continue
        
        # Sort by name
        file_list.sort(key=lambda x: x["name"].lower())
        
        return file_list
        
    except Exception as e:
        log.error(f"Error retrieving uploaded files: {e}")
        return []


def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def render_uploaded_files_display() -> None:
    """
    Display all previously uploaded files.
    """
    st.divider()
    
    # Header with refresh button
    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("📁 Previously Uploaded Files")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    with st.spinner("Loading uploaded files..."):
        files = get_uploaded_files_list()
    
    if not files:
        st.info("📭 No files have been uploaded yet. Upload your first bank statement above!")
        return
    
    # Calculate total storage
    total_bytes = sum(f['size_bytes'] for f in files)
    total_size = _format_size(total_bytes)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Files", len(files))
    with col2:
        st.metric("Total Storage", total_size)
    with col3:
        # Show storage type based on config
        storage_type = "GCS" if config.environment == "production" and config.gcs_bucket else "Local"
        st.metric("Storage Type", storage_type)
    
    st.caption("These files have been successfully uploaded and indexed.")
    
    # Display files in a compact list
    with st.container():
        for idx, file_info in enumerate(files, 1):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"**{idx}.** 📄 `{file_info['name']}`")
            
            with col2:
                st.markdown(f"<div style='text-align: right;'>{file_info['size_human']}</div>", unsafe_allow_html=True)
            
            # Add subtle separator between files
            if idx < len(files):
                st.markdown("<hr style='margin: 0.3rem 0; opacity: 0.1; border: none; height: 1px; background: #ccc;'>", unsafe_allow_html=True)
    
    # Optional: Add expander with more details
    with st.expander("📊 View detailed file information"):
        st.dataframe(
            [
                {
                    "Filename": f["name"],
                    "Size": f["size_human"],
                    "Storage Path": f["path"]
                }
                for f in files
            ],
            use_container_width=True,
            hide_index=True
        )

