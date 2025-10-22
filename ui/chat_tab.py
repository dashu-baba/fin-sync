import streamlit as st
from datetime import date
from elastic.search import hybrid_search
from llm.vertex_chat import chat_vertex
from core.logger import get_logger as log
from core.config import config as cfg

log = log("ui/chat_tab")

def _filters_from_ui():
    col1, col2, col3 = st.columns(3)
    with col1:
        date_from = st.date_input("From", value=None, format="YYYY-MM-DD")
    with col2:
        date_to = st.date_input("To", value=None, format="YYYY-MM-DD")
    with col3:
        account_no = st.text_input("Account No (optional)", value="")
    return {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "accountNo": account_no.strip() or None
    }

def render():
    st.header("🔎 Search & Chat (Hybrid)")
    st.caption("Semantic (statements) + Keyword (transactions) → grounded Gemini answers with citations")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    filters = _filters_from_ui()
    user_query = st.text_input("Ask about your finances… e.g., “Summarize June expenses by category”")

    if st.button("Search & Answer", type="primary") and user_query.strip():
        with st.spinner("Retrieving…"):
            results = hybrid_search(user_query, filters, top_k=20)
        with st.spinner("Thinking…"):
            answer = chat_vertex(user_query, results["transactions_vector"], results["transactions_keyword"])

        st.session_state.chat_history.append({"q": user_query, "a": answer, "results": results})

    # history
    for turn in reversed(st.session_state.chat_history[-10:]):
        st.markdown(f"**You:** {turn['q']}")
        st.markdown(turn["a"])

        with st.expander("Results (debug)"):
            st.write({"transactions_vector": [h.get("_id") for h in turn["results"]["transactions_vector"]],
                      "transactions_keyword": [h.get("_id") for h in turn["results"]["transactions_keyword"]]})

        st.divider()
