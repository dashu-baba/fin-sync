"""Chat page - orchestrates search and chat functionality with clarification."""
from __future__ import annotations
import streamlit as st

from core.logger import get_logger
from elastic.search import hybrid_search
from llm.vertex_chat import chat_vertex
from llm.intent_router import classify_intent_safe, classify_intent_with_context
from llm.intent_executor import execute_intent
from ui.services import SessionManager
from ui.services.clarification_manager import ClarificationManager
from ui.components import (
    render_chat_history,
    render_intent_display,
    render_intent_error,
    render_confirmation_dialog,
    render_clarification_dialog,
    render_conversation_context_display,
    render_clarification_mode_indicator,
    render_intent_results
)

log = get_logger("ui/pages/chat_page")


def render() -> None:
    """Render the chat/search page with clarification flow."""
    # Initialize session state
    SessionManager.init_session()
    
    # Page header
    st.header("💬 Chat with Your Finances")
    st.caption(
        "Ask questions about your financial transactions and get AI-powered insights"
    )
    
    # Check if we're in clarification mode
    clarification_mode = SessionManager.get_clarification_mode()
    
    if clarification_mode:
        # Show clarification mode indicator
        render_clarification_mode_indicator(clarification_mode)
        
        # Handle clarification interaction
        _handle_clarification_interaction(clarification_mode)
    else:
        # Normal mode: Display chat history and input
        history = SessionManager.get_chat_history()
        render_chat_history(history, max_turns=10)
        
        # Check if processing is in progress
        is_processing = st.session_state.get("is_processing", False)
        
        # Query input at the bottom using chat_input (combines input + send button, handles Enter key)
        user_query = st.chat_input(
            "Ask about your finances…",
            disabled=is_processing,
            key="chat_input"
        )
        
        # Process query when submitted (via Enter or send button)
        if user_query and user_query.strip():
            _handle_new_query(user_query.strip())


def _handle_clarification_interaction(mode: str) -> None:
    """
    Handle user interaction in clarification mode.
    
    Args:
        mode: Current clarification mode ('confirm' or 'clarify')
    """
    pending_query = SessionManager.get_pending_query()
    pending_intent = SessionManager.get_pending_intent()
    
    if not pending_query or not pending_intent:
        log.error("Clarification mode active but no pending data")
        SessionManager.clear_clarification_state()
        st.rerun()
        return
    
    # Show conversation context if any
    conversation = SessionManager.get_current_conversation()
    if conversation:
        render_conversation_context_display(conversation)
    
    if mode == "confirm":
        # Show confirmation dialog
        confirmed = render_confirmation_dialog(pending_query, pending_intent)
        
        if confirmed is not None:
            should_proceed, query_to_use = ClarificationManager.handle_confirmation_response(confirmed)
            
            if should_proceed and query_to_use:
                log.info(f"Proceeding with confirmed query: '{query_to_use}'")
                _proceed_with_search(query_to_use, pending_intent)
            else:
                log.info("User rejected query, clearing state")
                st.info("Please enter a new query below.")
                st.rerun()
    
    elif mode == "clarify":
        # Show clarification dialog
        clarification = render_clarification_dialog(pending_query, pending_intent)
        
        if clarification is not None:
            if clarification == "__SKIP__":
                # User chose to skip clarification
                log.info("User skipped clarification, proceeding with original query")
                ClarificationManager.reset_and_prepare_for_search()
                _proceed_with_search(pending_query, pending_intent)
            else:
                # Handle clarification input
                log.info(f"Processing clarification: '{clarification}'")
                _handle_clarification_input(clarification)


def _handle_clarification_input(clarification: str) -> None:
    """
    Handle user's clarification input and reclassify intent.
    
    Args:
        clarification: User's clarification text
    """
    needs_reclassification, cumulative_query = ClarificationManager.handle_clarification_input(clarification)
    
    if needs_reclassification:
        # Re-classify with context
        with st.spinner("🔄 Understanding your clarification..."):
            log.info(f"Re-classifying with cumulative query: '{cumulative_query}'")
            
            conversation = SessionManager.get_current_conversation()
            intent_response = classify_intent_with_context(
                cumulative_query,
                conversation
            )
            
            if intent_response:
                # Check if we need more clarification or can proceed
                if ClarificationManager.should_ask_for_clarification(intent_response):
                    # Still needs clarification
                    log.info("Still needs clarification after reclassification")
                    ClarificationManager.enter_clarification_mode(cumulative_query, intent_response)
                    st.rerun()
                elif ClarificationManager.should_ask_for_confirmation(intent_response):
                    # Now needs confirmation
                    log.info("Needs confirmation after clarification")
                    ClarificationManager.enter_confirmation_mode(cumulative_query, intent_response)
                    st.rerun()
                else:
                    # Good to go!
                    log.info("Clarification successful, proceeding with search")
                    ClarificationManager.reset_and_prepare_for_search()
                    _proceed_with_search(cumulative_query, intent_response)
            else:
                # Classification failed, proceed anyway
                log.warning("Re-classification failed, proceeding with cumulative query")
                SessionManager.clear_clarification_state()
                _proceed_with_search_without_intent(cumulative_query)
    else:
        # Max iterations reached, proceed with what we have
        log.info("Max clarification iterations reached, proceeding")
        _proceed_with_search(cumulative_query, SessionManager.get_pending_intent())


def _handle_new_query(query: str) -> None:
    """
    Handle a new user query with intent classification and clarification flow.
    
    Args:
        query: User's query string
    """
    # Set processing flag to disable input
    st.session_state["is_processing"] = True
    
    try:
        # Step 1: Classify intent
        with st.spinner("🎯 Analyzing your query..."):
            log.info(f"Starting intent classification for query: '{query}'")
            intent_response = classify_intent_safe(query)
            
            if intent_response:
                log.info(
                    f"Intent classified: {intent_response.classification.intent} "
                    f"(confidence: {intent_response.classification.confidence})"
                )
                
                # Display intent classification results
                render_intent_display(intent_response)
                
                # Step 2: Decision point based on intent
                if ClarificationManager.should_ask_for_confirmation(intent_response):
                    # Low confidence - ask for confirmation
                    log.info("Low confidence, entering confirmation mode")
                    ClarificationManager.enter_confirmation_mode(query, intent_response)
                    st.session_state["is_processing"] = False
                    st.rerun()
                    return
                
                elif ClarificationManager.should_ask_for_clarification(intent_response):
                    # Needs specific clarification
                    log.info("Needs clarification, entering clarification mode")
                    ClarificationManager.enter_clarification_mode(query, intent_response)
                    st.session_state["is_processing"] = False
                    st.rerun()
                    return
                
                else:
                    # High confidence - proceed immediately
                    log.info("High confidence, proceeding with search")
                    _proceed_with_search(query, intent_response)
            else:
                log.warning("Intent classification failed, proceeding with default workflow")
                render_intent_error("Could not classify query intent")
                _proceed_with_search_without_intent(query)
                
    except Exception as e:
        log.exception(f"Error in new query handler: {e!r}")
        st.error(f"❌ An error occurred: {str(e)}")
        # Clear processing flag on error
        st.session_state["is_processing"] = False


def _proceed_with_search(query: str, intent_response) -> None:
    """
    Execute the search and answer workflow.
    
    Args:
        query: Query to search for (may be cumulative with clarifications)
        intent_response: Intent classification response
    """
    try:
        # Check if we have intent classification and route accordingly
        if intent_response and hasattr(intent_response, 'classification'):
            intent_type = intent_response.classification.intent
            
            # Route based on intent type
            if intent_type in ["aggregate", "trend", "listing", "text_qa", "aggregate_filtered_by_text", "provenance"]:
                # Use new intent execution flow for structured queries
                log.info(f"Using intent executor for: {intent_type}")
                
                with st.spinner(f"🔍 Processing {intent_type} query..."):
                    result = execute_intent(query, intent_response)
                
                # Display results in assistant container
                answer = result.get("answer", "No response generated")
                data = result.get("data", {})
                citations = result.get("citations", [])
                
                # Use a chat message container for proper formatting
                with st.chat_message("assistant"):
                    # Display answer text
                    st.markdown(answer)
                    
                    # Display visual results based on intent type
                    if data:
                        st.divider()
                        render_intent_results(intent_type, data, citations)
                
                # Save to chat history
                log.info("Saving intent-based chat turn to session")
                intent_data = intent_response.model_dump() if intent_response else None
                SessionManager.add_chat_turn(
                    query, 
                    answer, 
                    {"intent_result": {**data, "citations": citations}},
                    intent=intent_data
                )
                
                # Clear clarification state and processing flag
                SessionManager.clear_clarification_state()
                st.session_state["is_processing"] = False
                
                # Rerun to update chat history display
                st.rerun()
                return
        
        # Fallback to original hybrid search flow for text_qa and unclassified queries
        log.info("Using fallback hybrid search flow")
        
        # Step 1: Retrieve relevant documents
        with st.spinner("🔍 Retrieving relevant transactions..."):
            log.info("Starting hybrid search")
            results = hybrid_search(query, filters={}, top_k=20)
            log.info(
                f"Search complete: vector={len(results.get('transactions_vector', []))}, "
                f"keyword={len(results.get('transactions_keyword', []))}"
            )
        
        # Step 2: Generate answer using Vertex AI
        with st.spinner("🤖 Generating answer..."):
            log.info("Starting answer generation")
            answer = chat_vertex(
                query,
                results["transactions_vector"],
                results["transactions_keyword"]
            )
            log.info("Answer generated successfully")
        
        # Step 3: Save to chat history with intent information
        log.info("Saving chat turn to session")
        intent_data = intent_response.model_dump() if intent_response else None
        SessionManager.add_chat_turn(query, answer, results, intent=intent_data)
        
        # Step 4: Clear clarification state and processing flag
        SessionManager.clear_clarification_state()
        st.session_state["is_processing"] = False
        
        # Rerun to display the new turn
        log.info("Chat turn complete, refreshing UI")
        st.rerun()
        
    except Exception as e:
        log.exception(f"Error in search and answer workflow: {e!r}")
        st.error(f"❌ An error occurred: {str(e)}")
        SessionManager.clear_clarification_state()
        st.session_state["is_processing"] = False


def _proceed_with_search_without_intent(query: str) -> None:
    """
    Execute search without intent classification (fallback).
    
    Args:
        query: Query to search for
    """
    try:
        with st.spinner("🔍 Searching..."):
            results = hybrid_search(query, filters={}, top_k=20)
        
        with st.spinner("🤖 Generating answer..."):
            answer = chat_vertex(
                query,
                results["transactions_vector"],
                results["transactions_keyword"]
            )
        
        SessionManager.add_chat_turn(query, answer, results)
        SessionManager.clear_clarification_state()
        st.session_state["is_processing"] = False
        st.rerun()
        
    except Exception as e:
        log.exception(f"Error in fallback search: {e!r}")
        st.error(f"❌ An error occurred: {str(e)}")
        SessionManager.clear_clarification_state()
        st.session_state["is_processing"] = False
