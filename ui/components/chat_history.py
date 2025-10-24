"""Chat history display component."""
from __future__ import annotations
from typing import List, Dict
import streamlit as st
from ui.components.intent_results import render_intent_results


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
        with st.chat_message("user"):
            st.markdown(turn['q'])
        
        # AI response
        with st.chat_message("assistant"):
            st.markdown(turn["a"])
            
            # Check if this turn has intent results
            results = turn.get("results", {})
            intent_result = results.get("intent_result")
            
            # If we have intent data, render the visual components
            if intent_result and turn.get("intent"):
                intent_type = turn["intent"].get("classification", {}).get("intent")
                if intent_type:
                    st.divider()
                    # Extract citations if available
                    citations = intent_result.get("citations", [])
                    render_intent_results(intent_type, intent_result, citations)
        
        st.divider()

