"""Sidebar component."""
from __future__ import annotations
import streamlit as st

from core.config import config


def render_sidebar() -> None:
    """Render the sidebar with pipeline information."""
    with st.sidebar:
        st.header("📊 FinSync Pipeline")
        st.markdown("""
1. Upload files & password ✅  
2. Parse statements (Vertex AI) ✅  
3. Clean / normalize ✅  
4. Embed & index (Elastic Cloud) ✅  
5. Chat & analytics ⏳  
"""
        )
        st.divider()
        st.caption(
            f"Environment: `{config.environment}`  \n"
            f"Log file: `{config.log_file}`"
        )

