"""UI pages module."""
from .ingest_page import render as render_ingest_page
from .chat_page import render as render_chat_page
from .analytics_page import render as render_analytics_page

__all__ = ["render_ingest_page", "render_chat_page", "render_analytics_page"]

