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
    def add_chat_turn(query: str, answer: str, results: Dict) -> None:
        """Add a turn to chat history."""
        SessionManager.init_session()
        st.session_state["chat_history"].append({
            "q": query,
            "a": answer,
            "results": results
        })

