"""Clarification dialog UI components."""
from __future__ import annotations
from typing import Optional
import streamlit as st

from models.intent import IntentResponse


def _format_intent_as_plain_english(classification) -> str:
    """
    Convert intent classification into plain English description.
    
    Args:
        classification: IntentClassification object
        
    Returns:
        Human-readable description of the intent
    """
    intent = classification.intent
    filters = classification.filters
    metrics = classification.metrics or []
    
    # Build the description parts
    parts = []
    
    # Action based on intent
    if intent == "aggregate":
        if "sum_expense" in metrics or "sum_amount" in metrics:
            parts.append("Calculate total spending")
        elif "sum_income" in metrics:
            parts.append("Calculate total income")
        elif "count" in metrics:
            parts.append("Count transactions")
        else:
            parts.append("Calculate totals")
    
    elif intent == "aggregate_filtered_by_text":
        if filters.counterparty:
            parts.append(f"Calculate spending on **{filters.counterparty}**")
        else:
            parts.append("Calculate spending for specific items")
    
    elif intent == "text_qa":
        parts.append("Answer your question about transactions")
    
    elif intent == "listing":
        parts.append("Show a list of transactions")
    
    elif intent == "trend":
        parts.append("Show spending trends")
    
    elif intent == "provenance":
        parts.append("Show which documents contain this transaction")
    
    # Add date range if specified
    if filters.dateFrom and filters.dateTo:
        parts.append(f"from **{filters.dateFrom}** to **{filters.dateTo}**")
    elif filters.dateFrom:
        parts.append(f"starting from **{filters.dateFrom}**")
    elif filters.dateTo:
        parts.append(f"up to **{filters.dateTo}**")
    
    # Add account filter if specified
    if filters.accountNo:
        parts.append(f"for account **{filters.accountNo}**")
    
    # Join parts into a sentence
    if len(parts) == 1:
        return parts[0]
    else:
        return " ".join(parts)



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
        
        # Show interpretation in plain English
        plain_english = _format_intent_as_plain_english(classification)
        
        col1, col2 = st.columns([1, 5])
        
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
            # Show plain English description
            st.markdown(f"### {plain_english}")
        
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

