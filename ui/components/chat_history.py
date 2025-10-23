"""Chat history display component."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st


def render_chat_history(history: List[Dict], max_turns: int = 10) -> None:
    """
    Render chat history in a clean chat interface style.
    
    Args:
        history: List of chat turns with 'q', 'a', and 'results' keys
        max_turns: Maximum number of turns to display
    """
    if not history:
        st.info("👋 Start a conversation by asking a question about your finances!")
        return
    
    st.markdown("### 💬 Conversation")
    
    # Show most recent turns (maintaining order, oldest to newest)
    for turn in history[-max_turns:]:
        # User message
        with st.container():
            st.markdown(
                f"""<div style='background-color: #E3F2FD; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                    <strong>👤 You:</strong><br>{turn['q']}
                </div>""",
                unsafe_allow_html=True
            )
        
        # AI response
        with st.container():
            st.markdown(
                f"""<div style='background-color: #F5F5F5; padding: 15px; border-radius: 10px; margin: 10px 0;'>
                    <strong>🤖 Assistant:</strong><br>
                </div>""",
                unsafe_allow_html=True
            )
            st.markdown(turn["a"])
        
        # Optional debug info
        with st.expander("🔍 View search results (debug)", expanded=False):
            results = turn.get("results", {})
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Vector Search Results:**")
                vec_results = results.get("transactions_vector", [])
                st.write(f"Found {len(vec_results)} results")
                if vec_results:
                    for i, hit in enumerate(vec_results[:5], 1):
                        st.caption(f"{i}. ID: {hit.get('_id')}")
            
            with col2:
                st.markdown("**Keyword Search Results:**")
                kw_results = results.get("transactions_keyword", [])
                st.write(f"Found {len(kw_results)} results")
                if kw_results:
                    for i, hit in enumerate(kw_results[:5], 1):
                        st.caption(f"{i}. ID: {hit.get('_id')}")
        
        st.divider()

