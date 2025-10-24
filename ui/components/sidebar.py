"""Sidebar component."""
from __future__ import annotations
import streamlit as st


def render_sidebar() -> None:
    """
    Render the sidebar with help information.
    Note: Navigation is handled automatically by Streamlit multi-page apps.
    """
    with st.sidebar:
        st.divider()
        
        # Help info
        st.caption("**FinSync** — Personal Finance Manager")
        st.caption("Upload bank statements, chat with AI, and analyze your finances.")

