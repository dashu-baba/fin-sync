"""Session state management service."""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import List, Dict, Optional, Any
import streamlit as st

from core.config import config
from core.logger import get_logger

log = get_logger("ui/services/session_manager")


class SessionManager:
    """Centralized session state management."""
    
    @staticmethod
    def init_session() -> None:
        """Initialize session-specific state."""
        if "session_upload_dir" not in st.session_state:
            session_id = uuid.uuid4().hex
            session_dir = config.uploads_dir / f"session-{session_id}"
            session_dir.mkdir(parents=True, exist_ok=True)
            st.session_state["session_upload_dir"] = session_dir
            log.info(f"Session folder created: {session_dir}")
        
        if "uploads_meta" not in st.session_state:
            st.session_state["uploads_meta"] = []
        
        if "password" not in st.session_state:
            st.session_state["password"] = ""
        
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        
        # Clarification state
        if "pending_query" not in st.session_state:
            st.session_state["pending_query"] = None
        
        if "pending_intent" not in st.session_state:
            st.session_state["pending_intent"] = None
        
        if "clarification_mode" not in st.session_state:
            st.session_state["clarification_mode"] = None
        
        if "current_conversation" not in st.session_state:
            st.session_state["current_conversation"] = []
        
        if "intent_history" not in st.session_state:
            st.session_state["intent_history"] = []
    
    @staticmethod
    def get_upload_dir() -> Path:
        """Get the current session's upload directory."""
        SessionManager.init_session()
        return st.session_state["session_upload_dir"]
    
    @staticmethod
    def get_uploads_meta() -> List[Dict]:
        """Get metadata for uploaded files."""
        SessionManager.init_session()
        return st.session_state.get("uploads_meta", [])
    
    @staticmethod
    def set_uploads_meta(meta: List[Dict]) -> None:
        """Set metadata for uploaded files."""
        st.session_state["uploads_meta"] = meta
    
    @staticmethod
    def get_password() -> str:
        """Get the session password."""
        SessionManager.init_session()
        return st.session_state.get("password", "")
    
    @staticmethod
    def set_password(password: str) -> None:
        """Set the session password."""
        st.session_state["password"] = password
    
    @staticmethod
    def get_chat_history() -> List[Dict]:
        """Get chat history."""
        SessionManager.init_session()
        return st.session_state.get("chat_history", [])
    
    @staticmethod
    def add_chat_turn(query: str, answer: str, results: Dict, intent: Optional[Dict] = None) -> None:
        """Add a turn to chat history."""
        SessionManager.init_session()
        turn_data = {
            "q": query,
            "a": answer,
            "results": results
        }
        if intent:
            turn_data["intent"] = intent
        st.session_state["chat_history"].append(turn_data)
    
    # Clarification state management
    
    @staticmethod
    def get_pending_query() -> Optional[str]:
        """Get the pending query waiting for clarification."""
        SessionManager.init_session()
        return st.session_state.get("pending_query")
    
    @staticmethod
    def set_pending_query(query: Optional[str]) -> None:
        """Set the pending query."""
        st.session_state["pending_query"] = query
    
    @staticmethod
    def get_pending_intent() -> Optional[Any]:
        """Get the pending intent response."""
        SessionManager.init_session()
        return st.session_state.get("pending_intent")
    
    @staticmethod
    def set_pending_intent(intent: Optional[Any]) -> None:
        """Set the pending intent response."""
        st.session_state["pending_intent"] = intent
    
    @staticmethod
    def get_clarification_mode() -> Optional[str]:
        """Get current clarification mode: 'confirm', 'clarify', or None."""
        SessionManager.init_session()
        return st.session_state.get("clarification_mode")
    
    @staticmethod
    def set_clarification_mode(mode: Optional[str]) -> None:
        """Set clarification mode."""
        st.session_state["clarification_mode"] = mode
    
    @staticmethod
    def is_in_clarification_mode() -> bool:
        """Check if we're currently in clarification mode."""
        return SessionManager.get_clarification_mode() is not None
    
    @staticmethod
    def get_current_conversation() -> List[Dict]:
        """Get the current conversation context."""
        SessionManager.init_session()
        return st.session_state.get("current_conversation", [])
    
    @staticmethod
    def add_conversation_turn(turn_type: str, text: str, metadata: Optional[Dict] = None) -> None:
        """Add a turn to current conversation context."""
        from datetime import datetime, timezone
        SessionManager.init_session()
        turn = {
            "type": turn_type,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        st.session_state["current_conversation"].append(turn)
        log.debug(f"Added conversation turn: {turn_type}")
    
    @staticmethod
    def clear_conversation_context() -> None:
        """Clear the current conversation context."""
        st.session_state["current_conversation"] = []
        log.debug("Cleared conversation context")
    
    @staticmethod
    def clear_clarification_state() -> None:
        """Clear all clarification-related state."""
        st.session_state["pending_query"] = None
        st.session_state["pending_intent"] = None
        st.session_state["clarification_mode"] = None
        SessionManager.clear_conversation_context()
        log.debug("Cleared clarification state")
    
    @staticmethod
    def get_cumulative_query() -> str:
        """Build cumulative query from conversation context."""
        SessionManager.init_session()
        conversation = st.session_state.get("current_conversation", [])
        
        # Combine original query with all clarifications
        parts = []
        for turn in conversation:
            if turn["type"] in ["query", "clarification_response"]:
                parts.append(turn["text"])
        
        return " ".join(parts) if parts else ""
    
    @staticmethod
    def add_intent_to_history(query: str, confidence: float) -> None:
        """Track intent confidence history."""
        SessionManager.init_session()
        st.session_state["intent_history"].append({
            "query": query,
            "confidence": confidence
        })
        # Keep only last 10 for memory efficiency
        if len(st.session_state["intent_history"]) > 10:
            st.session_state["intent_history"] = st.session_state["intent_history"][-10:]

