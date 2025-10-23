"""Streamlit page configuration."""
from __future__ import annotations
import streamlit as st


def setup_page() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="FinSync",
        page_icon="💰",
        layout="centered",
        initial_sidebar_state="expanded"
    )
    st.title("💰 FinSync — Personal Finance Manager")

