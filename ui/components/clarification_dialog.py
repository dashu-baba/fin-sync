"""Clarification dialog UI components."""
from __future__ import annotations
from typing import Optional
import streamlit as st

from models.intent import IntentResponse


def render_confirmation_dialog(query: str, intent: IntentResponse) -> Optional[bool]:
    """
    Render a confirmation dialog for low-confidence queries.
    
    Args:
        query: User's original query
        intent: Intent classification response
        
    Returns:
        True if confirmed, False if rejected, None if no interaction yet
    """
    classification = intent.classification
    
    st.markdown("---")
    st.warning("⚠️ **Please Confirm Your Query**")
    
    with st.container():
        st.markdown("I understood your query as:")
        
        # Show interpretation
        col1, col2 = st.columns([1, 3])
        
        with col1:
            intent_icons = {
                "aggregate": "🔢",
                "text_qa": "💬",
                "aggregate_filtered_by_text": "🔍",
                "listing": "📋",
                "trend": "📈",
                "provenance": "📄"
            }
            icon = intent_icons.get(classification.intent, "❓")
            st.markdown(f"### {icon}")
        
        with col2:
            st.markdown(f"**Intent:** {classification.intent.replace('_', ' ').title()}")
            st.markdown(f"**Confidence:** {classification.confidence:.0%}")
            
            # Show key details
            if classification.filters.dateFrom or classification.filters.dateTo:
                date_range = f"{classification.filters.dateFrom or '...'} to {classification.filters.dateTo or '...'}"
                st.markdown(f"**Date Range:** {date_range}")
            
            if classification.filters.counterparty:
                st.markdown(f"**Merchant/Payee:** {classification.filters.counterparty}")
            
            if classification.metrics:
                st.markdown(f"**Metrics:** {', '.join(classification.metrics[:3])}")
        
        st.markdown("---")
        st.markdown("**Is this what you're looking for?**")
        
        # Action buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("✅ Yes, Continue", type="primary", use_container_width=True):
                return True
        
        with col2:
            if st.button("❌ No, Let Me Rephrase", use_container_width=True):
                return False
    
    return None


def render_clarification_dialog(query: str, intent: IntentResponse) -> Optional[str]:
    """
    Render a clarification dialog for queries needing more information.
    
    Args:
        query: User's original query
        intent: Intent classification response
        
    Returns:
        User's clarification text, or None if not provided yet
    """
    classification = intent.classification
    clarify_question = classification.clarifyQuestion
    
    if not clarify_question:
        return None
    
    st.markdown("---")
    st.info("❓ **Need More Information**")
    
    with st.container():
        st.markdown(f"**Your Query:** _{query}_")
        st.markdown("")
        
        # Show the clarification question
        st.markdown(f"🤔 {clarify_question}")
        
        # Input for clarification
        clarification_key = "clarification_input"
        clarification = st.text_input(
            "Your response:",
            key=clarification_key,
            placeholder="e.g., 'Last month' or 'My savings account'"
        )
        
        # Action buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            submit_clicked = st.button(
                "Continue with Clarification",
                type="primary",
                use_container_width=True
            )
            
            if submit_clicked and clarification.strip():
                return clarification.strip()
        
        with col2:
            skip_clicked = st.button(
                "Skip & Search All",
                use_container_width=True
            )
            
            if skip_clicked:
                return "__SKIP__"  # Special marker for skip
    
    return None


def render_conversation_context_display(conversation: list) -> None:
    """
    Render conversation context in a clean, readable format.
    
    Args:
        conversation: List of conversation turns
    """
    if not conversation:
        return
    
    st.markdown("---")
    st.markdown("### 💭 Conversation Context")
    
    with st.container():
        for i, turn in enumerate(conversation, 1):
            turn_type = turn.get("type", "")
            text = turn.get("text", "")
            
            if turn_type == "query":
                st.markdown(f"**{i}.** You asked: _{text}_")
            elif turn_type == "clarification_request":
                st.markdown(f"**{i}.** I asked: _{text}_")
            elif turn_type == "clarification_response":
                st.markdown(f"**{i}.** You clarified: _{text}_")
            elif turn_type == "confirmation":
                if text == "yes":
                    st.markdown(f"**{i}.** ✅ You confirmed")
                else:
                    st.markdown(f"**{i}.** ❌ You rejected")
        
        st.caption("Using this context to better understand your request...")


def render_clarification_mode_indicator(mode: str) -> None:
    """
    Render an indicator showing current clarification mode.
    
    Args:
        mode: Current mode ('confirm', 'clarify', or None)
    """
    if not mode:
        return
    
    if mode == "confirm":
        st.info("🎯 **Confirmation Mode:** Please confirm if I understood your query correctly.")
    elif mode == "clarify":
        st.info("🔍 **Clarification Mode:** I need a bit more information to help you better.")

