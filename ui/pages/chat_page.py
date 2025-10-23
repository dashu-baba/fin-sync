"""Chat page - orchestrates search and chat functionality."""
from __future__ import annotations
import streamlit as st

from core.logger import get_logger
from elastic.search import hybrid_search
from llm.vertex_chat import chat_vertex
from ui.services import SessionManager
from ui.components import render_filter_bar, render_chat_history

log = get_logger("ui/pages/chat_page")


def render() -> None:
    """Render the chat/search page."""
    # Initialize session state
    SessionManager.init_session()
    
    # Page header
    st.header("🔎 Search & Chat (Hybrid)")
    st.caption(
        "Semantic (statements) + Keyword (transactions) → "
        "grounded Gemini answers with citations"
    )
    
    # Render filters
    filters = render_filter_bar()
    
    # Query input
    user_query = st.text_input(
        "Ask about your finances… e.g., \"Summarize June expenses by category\""
    )
    
    # Search and answer
    if st.button("Search & Answer", type="primary") and user_query.strip():
        _handle_search_and_answer(user_query, filters)
    
    # Display chat history
    history = SessionManager.get_chat_history()
    render_chat_history(history, max_turns=10)


def _handle_search_and_answer(query: str, filters: dict) -> None:
    """
    Handle search and answer workflow.
    
    Args:
        query: User query string
        filters: Filter dictionary from filter bar
    """
    try:
        # Retrieve relevant documents
        with st.spinner("Retrieving…"):
            results = hybrid_search(query, filters, top_k=20)
        
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

