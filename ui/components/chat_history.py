"""Chat history display component."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st


def render_chat_history(history: List[Dict], max_turns: int = 10) -> None:
    """
    Render chat history with expandable debug information.
    
    Args:
        history: List of chat turns with 'q', 'a', and 'results' keys
        max_turns: Maximum number of turns to display
    """
    if not history:
        return
    
    # Show most recent turns first
    for turn in reversed(history[-max_turns:]):
        st.markdown(f"**You:** {turn['q']}")
        st.markdown(turn["a"])
        
        with st.expander("Results (debug)"):
            results = turn.get("results", {})
            st.write({
                "transactions_vector": [
                    h.get("_id") for h in results.get("transactions_vector", [])
                ],
                "transactions_keyword": [
                    h.get("_id") for h in results.get("transactions_keyword", [])
                ]
            })
        
        st.divider()

