"""Analytics page - displays charts, tables, and financial insights."""
from __future__ import annotations
import streamlit as st
from datetime import datetime, timedelta

from core.logger import get_logger
from ui.services import SessionManager
from ui.components import render_analytics_view

log = get_logger("ui/pages/analytics_page")


def render() -> None:
    """Render the analytics page."""
    # Initialize session state
    SessionManager.init_session()
    
    # Page header
    st.header("📊 Financial Analytics")
    st.caption("Visualize your financial data with interactive charts and tables")
    
    # Render date range filter
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=90),
            key="analytics_start_date"
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now(),
            key="analytics_end_date"
        )
    
    # Additional filters
    with st.expander("🔧 Advanced Filters", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            account_filter = st.multiselect(
                "Filter by Account",
                options=[],  # Will be populated with actual accounts
                default=[],
                key="analytics_account_filter"
            )
        with col2:
            transaction_type = st.multiselect(
                "Transaction Type",
                options=["credit", "debit"],
                default=["credit", "debit"],
                key="analytics_type_filter"
            )
    
    # Prepare filters
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "accounts": account_filter,
        "transaction_types": transaction_type,
    }
    
    # Render analytics view
    render_analytics_view(filters)

