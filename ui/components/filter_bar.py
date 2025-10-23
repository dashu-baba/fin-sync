"""Filter bar component for chat/search."""
from __future__ import annotations
from typing import Dict, Optional
from datetime import date
import streamlit as st


def render_filter_bar() -> Dict[str, Optional[str]]:
    """
    Render the filter bar with date range and account number filters.
    
    Returns:
        Dictionary with filter values (date_from, date_to, accountNo)
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_from = st.date_input("From", value=None, format="YYYY-MM-DD")
    
    with col2:
        date_to = st.date_input("To", value=None, format="YYYY-MM-DD")
    
    with col3:
        account_no = st.text_input("Account No (optional)", value="")
    
    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "accountNo": account_no.strip() or None
    }

