"""Intent classification display component."""
from __future__ import annotations
from typing import Optional
import streamlit as st
import json

from models.intent import IntentResponse


def render_intent_display(intent_response: Optional[IntentResponse]) -> None:
    """
    Render intent classification results in an expandable section.
    
    Args:
        intent_response: Intent classification response from LLM
    """
    if not intent_response:
        return
    
    with st.expander("🎯 Intent Classification (Debug)", expanded=False):
        classification = intent_response.classification
        
        # Header with key info
        col1, col2, col3 = st.columns(3)
        
        with col1:
            intent_color = {
                "aggregate": "🔢",
                "text_qa": "💬",
                "aggregate_filtered_by_text": "🔍",
                "listing": "📋",
                "trend": "📈",
                "provenance": "📄"
            }.get(classification.intent, "❓")
            
            st.metric(
                "Intent Type",
                f"{intent_color} {classification.intent}"
            )
        
        with col2:
            confidence_color = "🟢" if classification.confidence >= 0.8 else "🟡" if classification.confidence >= 0.6 else "🔴"
            st.metric(
                "Confidence",
                f"{confidence_color} {classification.confidence:.2f}"
            )
        
        with col3:
            if intent_response.processing_time_ms:
                st.metric(
                    "Processing Time",
                    f"{intent_response.processing_time_ms:.0f}ms"
                )
        
        # Show clarification if needed
        if classification.needsClarification and classification.clarifyQuestion:
            st.warning(f"⚠️ **Needs Clarification:** {classification.clarifyQuestion}")
        
        # Filters section
        if any([
            classification.filters.accountNo,
            classification.filters.dateFrom,
            classification.filters.dateTo,
            classification.filters.counterparty,
            classification.filters.minAmount is not None,
            classification.filters.maxAmount is not None
        ]):
            st.markdown("**📊 Extracted Filters:**")
            filter_data = {}
            
            if classification.filters.accountNo:
                filter_data["Account No"] = classification.filters.accountNo
            if classification.filters.dateFrom:
                filter_data["Date From"] = classification.filters.dateFrom
            if classification.filters.dateTo:
                filter_data["Date To"] = classification.filters.dateTo
            if classification.filters.counterparty:
                filter_data["Counterparty"] = classification.filters.counterparty
            if classification.filters.minAmount is not None:
                filter_data["Min Amount"] = classification.filters.minAmount
            if classification.filters.maxAmount is not None:
                filter_data["Max Amount"] = classification.filters.maxAmount
            
            st.json(filter_data, expanded=True)
        
        # Metrics section
        if classification.metrics:
            st.markdown("**📈 Metrics to Compute:**")
            st.write(", ".join(classification.metrics))
        
        # Additional info
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"**Granularity:** {classification.granularity}")
        
        with col2:
            st.markdown(f"**Answer Style:** {classification.answerStyle}")
        
        with col3:
            table_icon = "✅" if classification.needsTable else "❌"
            st.markdown(f"**Needs Table:** {table_icon}")
        
        # Reasoning if available
        if classification.reasoning:
            st.markdown("**💭 Reasoning:**")
            st.info(classification.reasoning)
        
        # Full JSON for developers (using details/summary instead of nested expander)
        st.markdown("---")
        st.markdown("**📋 Full JSON Response:**")
        with st.container():
            st.json(intent_response.model_dump(), expanded=False)


def render_intent_error(error_message: str) -> None:
    """
    Render error message for failed intent classification.
    
    Args:
        error_message: Error message to display
    """
    with st.expander("🎯 Intent Classification (Debug)", expanded=True):
        st.error(f"❌ **Intent classification failed:** {error_message}")
        st.caption("The system will proceed with the default search workflow.")

