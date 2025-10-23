"""Clarification management service for interactive query refinement."""
from __future__ import annotations
from typing import Optional, Tuple
from datetime import datetime, timezone

from core.logger import get_logger
from models.intent import IntentResponse, ConversationContext
from ui.services.session_manager import SessionManager

log = get_logger("ui/services/clarification_manager")


class ClarificationManager:
    """Manages clarification flow and decision logic."""
    
    # Maximum number of clarification attempts before proceeding anyway
    MAX_CLARIFICATION_ITERATIONS = 2
    
    @staticmethod
    def should_ask_for_confirmation(intent: IntentResponse) -> bool:
        """
        Determine if we should ask for generic confirmation.
        
        Args:
            intent: Intent classification response
            
        Returns:
            True if confidence is low but no specific clarification needed
        """
        classification = intent.classification
        return (
            classification.confidence <= 0.75 and
            not classification.needsClarification
        )
    
    @staticmethod
    def should_ask_for_clarification(intent: IntentResponse) -> bool:
        """
        Determine if we should ask for specific clarification.
        
        Args:
            intent: Intent classification response
            
        Returns:
            True if LLM identified specific clarification needed
        """
        classification = intent.classification
        return (
            classification.needsClarification and
            classification.clarifyQuestion is not None
        )
    
    @staticmethod
    def should_proceed_immediately(intent: IntentResponse) -> bool:
        """
        Determine if we should proceed with search immediately.
        
        Args:
            intent: Intent classification response
            
        Returns:
            True if confidence is high and no clarification needed
        """
        classification = intent.classification
        return (
            classification.confidence > 0.75 and
            not classification.needsClarification
        )
    
    @staticmethod
    def enter_confirmation_mode(query: str, intent: IntentResponse) -> None:
        """
        Enter confirmation mode - ask user to confirm understanding.
        
        Args:
            query: User's query
            intent: Intent classification response
        """
        log.info(f"Entering confirmation mode for query: '{query}' (confidence: {intent.classification.confidence})")
        
        # Store state
        SessionManager.set_pending_query(query)
        SessionManager.set_pending_intent(intent)
        SessionManager.set_clarification_mode("confirm")
        
        # Add to conversation context
        SessionManager.add_conversation_turn("query", query, {
            "confidence": intent.classification.confidence,
            "intent": intent.classification.intent
        })
        
        # Track intent
        SessionManager.add_intent_to_history(query, intent.classification.confidence)
    
    @staticmethod
    def enter_clarification_mode(query: str, intent: IntentResponse) -> None:
        """
        Enter clarification mode - ask user for specific information.
        
        Args:
            query: User's query
            intent: Intent classification response
        """
        log.info(f"Entering clarification mode for query: '{query}'")
        
        # Store state
        SessionManager.set_pending_query(query)
        SessionManager.set_pending_intent(intent)
        SessionManager.set_clarification_mode("clarify")
        
        # Add to conversation context
        SessionManager.add_conversation_turn("query", query, {
            "confidence": intent.classification.confidence,
            "intent": intent.classification.intent
        })
        
        clarify_question = intent.classification.clarifyQuestion
        SessionManager.add_conversation_turn("clarification_request", clarify_question or "", {
            "confidence": intent.classification.confidence
        })
        
        # Track intent
        SessionManager.add_intent_to_history(query, intent.classification.confidence)
    
    @staticmethod
    def handle_confirmation_response(confirmed: bool) -> Tuple[bool, Optional[str]]:
        """
        Handle user's confirmation response.
        
        Args:
            confirmed: Whether user confirmed (True) or rejected (False)
            
        Returns:
            Tuple of (should_proceed, query_to_use)
        """
        pending_query = SessionManager.get_pending_query()
        
        if confirmed:
            log.info(f"User confirmed query: '{pending_query}'")
            SessionManager.add_conversation_turn("confirmation", "yes", {
                "action": "confirmed"
            })
            # Clear clarification mode but keep the query
            SessionManager.set_clarification_mode(None)
            return True, pending_query
        else:
            log.info(f"User rejected query: '{pending_query}'")
            SessionManager.add_conversation_turn("confirmation", "no", {
                "action": "rejected"
            })
            # Clear everything and let user rephrase
            SessionManager.clear_clarification_state()
            return False, None
    
    @staticmethod
    def handle_clarification_input(clarification: str) -> Tuple[bool, str]:
        """
        Handle user's clarification input.
        
        Args:
            clarification: User's clarification text
            
        Returns:
            Tuple of (needs_reclassification, cumulative_query)
        """
        log.info(f"User provided clarification: '{clarification}'")
        
        # Add clarification to conversation
        SessionManager.add_conversation_turn("clarification_response", clarification)
        
        # Build cumulative query
        cumulative_query = SessionManager.get_cumulative_query()
        
        log.debug(f"Cumulative query after clarification: '{cumulative_query}'")
        
        # Check iteration count
        conversation = SessionManager.get_current_conversation()
        clarification_count = sum(
            1 for turn in conversation 
            if turn["type"] == "clarification_request"
        )
        
        if clarification_count >= ClarificationManager.MAX_CLARIFICATION_ITERATIONS:
            log.warning(f"Reached max clarification iterations ({ClarificationManager.MAX_CLARIFICATION_ITERATIONS}), proceeding anyway")
            SessionManager.set_clarification_mode(None)
            return False, cumulative_query
        
        # Need to reclassify with context
        return True, cumulative_query
    
    @staticmethod
    def build_conversation_context_for_llm() -> str:
        """
        Build formatted conversation context for LLM prompt.
        
        Returns:
            Formatted conversation context string
        """
        conversation = SessionManager.get_current_conversation()
        
        if not conversation:
            return ""
        
        lines = ["### Previous Conversation:"]
        for turn in conversation:
            turn_type = turn["type"]
            text = turn["text"]
            
            if turn_type == "query":
                lines.append(f"User originally asked: {text}")
            elif turn_type == "clarification_request":
                lines.append(f"System asked for clarification: {text}")
            elif turn_type == "clarification_response":
                lines.append(f"User clarified: {text}")
            elif turn_type == "confirmation":
                lines.append(f"User confirmed: {text}")
        
        lines.append("")  # Empty line for separation
        return "\n".join(lines)
    
    @staticmethod
    def get_clarification_summary() -> str:
        """
        Get a human-readable summary of the clarification process.
        
        Returns:
            Summary string
        """
        conversation = SessionManager.get_current_conversation()
        
        if not conversation:
            return "No clarifications"
        
        parts = []
        for turn in conversation:
            if turn["type"] == "query":
                parts.append(f"• Original: \"{turn['text']}\"")
            elif turn["type"] == "clarification_response":
                parts.append(f"• Clarified: \"{turn['text']}\"")
        
        return "\n".join(parts) if parts else "No clarifications"
    
    @staticmethod
    def reset_and_prepare_for_search() -> None:
        """Prepare state for executing search after clarifications complete."""
        log.info("Clearing clarification mode, ready for search")
        SessionManager.set_clarification_mode(None)
        # Keep conversation context for this search, clear after results

