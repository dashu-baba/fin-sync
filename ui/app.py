"""FinSync - Main Streamlit application entry point."""
from __future__ import annotations
from pathlib import Path
import sys
import streamlit as st

# Ensure project root is on sys.path for absolute imports
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger
from ui.config import setup_page
from ui.pages import render_ingest_page, render_chat_page, render_analytics_page

log = get_logger("ui")

# Configure page
setup_page()

# Create tabs
tab1, tab2, tab3 = st.tabs(["📥 Ingest", "💬 Chat", "📊 Analytics"])

with tab1:
    render_ingest_page()

with tab2:
    render_chat_page()

with tab3:
    render_analytics_page()
