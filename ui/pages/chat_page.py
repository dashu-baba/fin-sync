"""Chat page - orchestrates search and chat functionality."""
from __future__ import annotations
import streamlit as st

from core.logger import get_logger
from elastic.search import hybrid_search
from llm.vertex_chat import chat_vertex
from ui.services import SessionManager
from ui.components import render_chat_history

log = get_logger("ui/pages/chat_page")


def render() -> None:
    """Render the chat/search page."""
    # Initialize session state
    SessionManager.init_session()
    
    # Page header
    st.header("💬 Chat with Your Finances")
    st.caption(
        "Ask questions about your financial transactions and get AI-powered insights"
    )
    
    # Display chat history first
    history = SessionManager.get_chat_history()
    render_chat_history(history, max_turns=10)
    
    # Query input at the bottom
    user_query = st.text_input(
        "Ask about your finances…",
        placeholder="e.g., 'Summarize my expenses for last month' or 'Show me all transactions over $500'"
    )
    
    # Search and answer
    if st.button("Send", type="primary") and user_query.strip():
        _handle_search_and_answer(user_query)


def _handle_search_and_answer(query: str) -> None:
    """
    Handle search and answer workflow.
    
    Args:
        query: User query string
    """
    try:
        # Retrieve relevant documents (no filters)
        with st.spinner("Retrieving…"):
            results = hybrid_search(query, filters={}, top_k=20)
        
        # Generate answer
        with st.spinner("Thinking…"):
            answer = chat_vertex(
                query,
                results["transactions_vector"],
                results["transactions_keyword"]
            )
        
        # Save to chat history
        SessionManager.add_chat_turn(query, answer, results)
        
        # Rerun to display the new turn
        st.rerun()
        
    except Exception as e:
        log.error(f"Error in search and answer: {e!r}")
        st.error(f"An error occurred: {e}")

