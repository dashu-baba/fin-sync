from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import sys
import streamlit as st


# Ensure project root is on sys.path for absolute imports like `core.*`
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger
from ui import ingest, chat_tab

log = get_logger("ui")

st.set_page_config(
    page_title="FinSync",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("💰 FinSync — Upload Bank Statements")

# near your other tabs
import ui.chat_tab as chat_tab

tab1, tab2 = st.tabs(["📥 Ingest", "💬 Search & Chat"])
with tab1:
    ingest.render()
with tab2:
    chat_tab.render()

