"""FinSync - Chat Page."""
from __future__ import annotations
from pathlib import Path
import sys
import streamlit as st

# Ensure project root is on sys.path for absolute imports
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.logger import get_logger
from ui.config import setup_page
from ui.views.chat_page import render

log = get_logger("ui.chat")

# Configure page
setup_page()

# Render chat page
render()

