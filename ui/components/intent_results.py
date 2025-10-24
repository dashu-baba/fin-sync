"""Visual components for rendering intent-based query results."""
from __future__ import annotations
import streamlit as st
import pandas as pd
from typing import Dict, Any, List
from core.utils import format_currency
from core.config import config


def _get_currency_from_results(data: Dict[str, Any]) -> str:
    """Extract currency from result data, defaulting to USD."""
    # First, try to get currency from the result object directly (for aggregate queries)
    if "currency" in data and data["currency"]:
        return data["currency"]
    
    # Fallback: try to get currency from hits (for listing/search queries)
    hits = data.get("hits", [])
    if hits and isinstance(hits, list) and len(hits) > 0:
        currency = hits[0].get("currency")
        if currency:
            return currency
    
    # Default to USD if not found
    return "USD"


def render_aggregate_results(data: Dict[str, Any]) -> None:
    """
    Render aggregate results with metric cards and top lists.
    
    Args:
        data: Result data from aggregate execution
    """
    aggs = data.get("aggs", {})
    currency = _get_currency_from_results(data)
    
    if not aggs:
        st.info("No aggregation data available")
        return
    
    # Display metrics in columns
    cols = st.columns(4)
    
    # Income metric
    if "sum_income" in aggs:
        with cols[0]:
            st.metric(
                label="💰 Total Income",
                value=format_currency(aggs['sum_income'], currency),
                delta=None
            )
    
    # Expense metric
    if "sum_expense" in aggs:
        with cols[1]:
            st.metric(
                label="💸 Total Expenses",
                value=format_currency(aggs['sum_expense'], currency),
                delta=None
            )
    
    # Net metric
    if "net" in aggs:
        net = aggs["net"]
        with cols[2]:
            st.metric(
                label="📊 Net",
                value=format_currency(abs(net), currency),
                delta=f"{'Profit' if net >= 0 else 'Loss'}"
            )
    
    # Count metric
    if "count" in aggs:
        with cols[3]:
            st.metric(
                label="🔢 Transactions",
                value=f"{aggs['count']:,}",
                delta=None
            )
    
    # Top Merchants
    if "top_merchants" in aggs and aggs["top_merchants"]:
        st.subheader("🏪 Top Merchants")
        merchants_df = pd.DataFrame(aggs["top_merchants"])
        merchants_df["total_amount"] = merchants_df["total_amount"].apply(lambda x: format_currency(x, currency))
        st.dataframe(
            merchants_df,
            column_config={
                "merchant": "Merchant",
                "count": st.column_config.NumberColumn("Transactions", format="%d"),
                "total_amount": "Total Amount"
            },
            hide_index=True,
            use_container_width=True
        )
    
    # Top Categories
    if "top_categories" in aggs and aggs["top_categories"]:
        st.subheader("📂 Top Categories")
        categories_df = pd.DataFrame(aggs["top_categories"])
        categories_df["total_amount"] = categories_df["total_amount"].apply(lambda x: format_currency(x, currency))
        st.dataframe(
            categories_df,
            column_config={
                "category": "Category",
                "count": st.column_config.NumberColumn("Transactions", format="%d"),
                "total_amount": "Total Amount"
            },
            hide_index=True,
            use_container_width=True
        )


def render_trend_results(data: Dict[str, Any]) -> None:
    """
    Render trend results with time-series chart.
    
    Args:
        data: Result data from trend execution
    """
    buckets = data.get("buckets", [])
    granularity = data.get("granularity", "monthly")
    currency = _get_currency_from_results(data)
    
    if not buckets:
        st.info("No trend data available")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(buckets)
    
    if df.empty:
        st.info("No trend data available")
        return
    
    # Format data
    df["date"] = pd.to_datetime(df["date"])
    
    st.subheader(f"📈 Trend Analysis ({granularity.title()})")
    
    # Display chart
    st.line_chart(
        df,
        x="date",
        y=["income", "expense", "net"],
        color=["#00ff00", "#ff0000", "#0000ff"]
    )
    
    # Display summary metrics
    cols = st.columns(3)
    
    with cols[0]:
        total_income = df["income"].sum()
        st.metric("Total Income", format_currency(total_income, currency))
    
    with cols[1]:
        total_expense = df["expense"].sum()
        st.metric("Total Expenses", format_currency(total_expense, currency))
    
    with cols[2]:
        total_net = df["net"].sum()
        st.metric(
            "Total Net",
            format_currency(abs(total_net), currency),
            delta="Profit" if total_net >= 0 else "Loss"
        )
    
    # Display data table (optional)
    with st.expander("📊 View Data Table"):
        display_df = df.copy()
        display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
        display_df["income"] = display_df["income"].apply(lambda x: format_currency(x, currency))
        display_df["expense"] = display_df["expense"].apply(lambda x: format_currency(x, currency))
        display_df["net"] = display_df["net"].apply(lambda x: format_currency(x, currency))
        
        st.dataframe(
            display_df,
            column_config={
                "date": "Date",
                "income": "Income",
                "expense": "Expense",
                "net": "Net",
                "count": st.column_config.NumberColumn("Transactions", format="%d")
            },
            hide_index=True,
            use_container_width=True
        )


def render_listing_results(data: Dict[str, Any]) -> None:
    """
    Render listing results as a table.
    
    Args:
        data: Result data from listing execution
    """
    hits = data.get("hits", [])
    total = data.get("total", 0)
    currency = _get_currency_from_results(data)
    
    if not hits:
        st.info("No transactions found")
        return
    
    st.subheader(f"📋 Transactions (Showing {len(hits)} of {total:,})")
    
    # Convert to DataFrame
    df = pd.DataFrame(hits)
    
    # Format columns
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    
    if "amount" in df.columns:
        df["amount_display"] = df["amount"].apply(lambda x: format_currency(x, currency))
    
    if "balance" in df.columns:
        df["balance_display"] = df["balance"].apply(lambda x: format_currency(x, currency))
    
    # Select and order columns
    display_columns = []
    column_config = {}
    
    if "date" in df.columns:
        display_columns.append("date")
        column_config["date"] = "Date"
    
    if "type" in df.columns:
        display_columns.append("type")
        column_config["type"] = "Type"
    
    if "amount_display" in df.columns:
        display_columns.append("amount_display")
        column_config["amount_display"] = "Amount"
    
    if "description" in df.columns:
        display_columns.append("description")
        column_config["description"] = st.column_config.TextColumn("Description", width="large")
    
    if "category" in df.columns:
        display_columns.append("category")
        column_config["category"] = "Category"
    
    if "balance_display" in df.columns:
        display_columns.append("balance_display")
        column_config["balance_display"] = "Balance"
    
    if "accountNo" in df.columns:
        display_columns.append("accountNo")
        column_config["accountNo"] = "Account"
    
    # Display table
    st.dataframe(
        df[display_columns],
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=400
    )


def render_text_qa_results(data: Dict[str, Any], citations: List[Dict[str, Any]]) -> None:
    """
    Render text_qa results with citations.
    
    Args:
        data: Result data from text_qa execution
        citations: Citation/provenance list
    """
    if not citations:
        return
    
    # Only show sources in development mode as a debug section
    if config.environment == "development":
        with st.expander("🔧 Debug: Statement Sources", expanded=False):
            st.caption("Technical information about which statements were used (for development/verification)")
            
            for i, citation in enumerate(citations[:5], start=1):
                with st.container():
                    st.markdown(f"**[{i}] {citation.get('source', 'Unknown Source')}**")
                    
                    cols = st.columns([1, 1, 2])
                    
                    with cols[0]:
                        st.caption("**Page**")
                        st.write(citation.get("page", "N/A"))
                    
                    with cols[1]:
                        st.caption("**Relevance**")
                        score = citation.get("score", 0.0)
                        st.write(f"{score:.1%}")
                    
                    with cols[2]:
                        st.caption("**Statement ID**")
                        st.code(citation.get("statementId", "N/A"), language=None)
                    
                    if i < len(citations[:5]):
                        st.markdown("---")


def render_aggregate_filtered_results(data: Dict[str, Any], citations: List[Dict[str, Any]]) -> None:
    """
    Render aggregate_filtered_by_text results with both aggregations and citations.
    
    Args:
        data: Result data from aggregate_filtered_by_text execution
        citations: Citation/provenance list
    """
    # Render aggregation results
    render_aggregate_results(data)
    
    # Show derived filters and citations only in development mode
    if config.environment == "development":
        # Show derived filters used
        derived_filters = data.get("derived_filters", [])
        if derived_filters or citations:
            with st.expander("🔧 Debug: Technical Details", expanded=False):
                if derived_filters:
                    st.markdown("**Filters Derived from Statements:**")
                    st.caption("The following terms were extracted from your statements and used to filter transactions:")
                    for i, filter_term in enumerate(derived_filters[:5], start=1):
                        st.markdown(f"{i}. `{filter_term[:100]}`")
                
                if citations:
                    if derived_filters:
                        st.markdown("---")
                    st.markdown("**Statement Sources:**")
                    st.caption("Technical information about which statements were used")
                    for i, citation in enumerate(citations[:5], start=1):
                        source = citation.get('source', 'Unknown Source')
                        page = citation.get("page", "N/A")
                        st.markdown(f"{i}. {source} (Page {page})")


def render_provenance_results(data: Dict[str, Any], citations: List[Dict[str, Any]]) -> None:
    """
    Render provenance results (same as text_qa sources).
    
    Args:
        data: Result data from provenance execution
        citations: Citation/provenance list
    """
    render_text_qa_results(data, citations)


def render_intent_results(intent: str, data: Dict[str, Any], citations: List[Dict[str, Any]] = None) -> None:
    """
    Main dispatcher for rendering intent-based results.
    
    Args:
        intent: Intent type (aggregate, trend, listing, etc.)
        data: Result data
        citations: Optional citations list
    """
    citations = citations or []
    
    if intent == "aggregate":
        render_aggregate_results(data)
    
    elif intent == "trend":
        render_trend_results(data)
    
    elif intent == "listing":
        render_listing_results(data)
    
    elif intent == "text_qa":
        render_text_qa_results(data, citations)
    
    elif intent == "aggregate_filtered_by_text":
        render_aggregate_filtered_results(data, citations)
    
    elif intent == "provenance":
        render_provenance_results(data, citations)
    
    else:
        st.info(f"No visualization available for intent: {intent}")

