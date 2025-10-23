"""Analytics view component - renders charts and tables."""
from __future__ import annotations
from typing import Dict, Any, List
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from core.logger import get_logger
from elastic.analytics import (
    get_monthly_inflow_outflow,
    get_available_accounts,
    ensure_monthly_rollup_transform
)

log = get_logger("ui/components/analytics_view")


def render(filters: Dict[str, Any]) -> None:
    """
    Render analytics view with charts and tables.
    
    Args:
        filters: Dictionary containing date range and filter options
    """
    # Ensure transform exists and is running
    _initialize_transforms()
    
    # Fetch rollup data
    rollup_data = _fetch_rollup_data(filters)
    
    # Overview metrics section
    st.subheader("📈 Overview Metrics")
    _render_kpi_cards(rollup_data)
    
    st.divider()
    
    # Charts section
    st.subheader("📊 Charts & Visualizations")
    
    # Create tabs for different chart views
    chart_tab1, chart_tab2, chart_tab3, chart_tab4 = st.tabs([
        "Monthly Cash Flow",
        "Category Breakdown",
        "Trends Analysis",
        "Account Comparison"
    ])
    
    with chart_tab1:
        _render_monthly_cash_flow(rollup_data, filters)
    
    with chart_tab2:
        _render_category_breakdown(filters)
    
    with chart_tab3:
        _render_spending_trends(filters)
    
    with chart_tab4:
        _render_account_comparison(filters)
    
    st.divider()
    
    # Tables section
    st.subheader("📋 Detailed Tables")
    _render_transaction_tables(rollup_data, filters)


def _initialize_transforms() -> None:
    """Initialize and ensure transforms are running."""
    try:
        with st.spinner("Initializing analytics transforms..."):
            ensure_monthly_rollup_transform()
    except Exception as e:
        log.error(f"Failed to initialize transforms: {e}")
        st.error(f"Failed to initialize analytics: {e}")


def _fetch_rollup_data(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fetch rollup data based on filters.
    
    Args:
        filters: Filter dictionary with date range and account filters
        
    Returns:
        List of rollup data records
    """
    try:
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        accounts = filters.get("accounts", [])
        
        # Convert date objects to datetime
        start_dt = datetime.combine(start_date, datetime.min.time()) if start_date else None
        end_dt = datetime.combine(end_date, datetime.max.time()) if end_date else None
        
        data = get_monthly_inflow_outflow(
            start_date=start_dt,
            end_date=end_dt,
            account_numbers=accounts if accounts else None
        )
        
        log.info(f"Fetched {len(data)} rollup records")
        return data
        
    except Exception as e:
        log.error(f"Error fetching rollup data: {e}")
        st.error(f"Error fetching analytics data: {e}")
        return []


def _render_kpi_cards(rollup_data: List[Dict[str, Any]]) -> None:
    """Render KPI metric cards."""
    # Calculate totals from rollup data
    total_inflow = sum(record.get("inflow", 0) for record in rollup_data)
    total_outflow = sum(record.get("outflow", 0) for record in rollup_data)
    net_savings = total_inflow - total_outflow
    total_tx = sum(record.get("txCount", 0) for record in rollup_data)
    
    # Calculate number of days in period
    num_months = len(set(record.get("month") for record in rollup_data if record.get("month")))
    avg_days = num_months * 30 if num_months > 0 else 1
    avg_daily_spend = total_outflow / avg_days if avg_days > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Income",
            value=f"${total_inflow:,.2f}",
            help="Total credits in selected period"
        )
    
    with col2:
        st.metric(
            label="Total Expenses",
            value=f"${total_outflow:,.2f}",
            help="Total debits in selected period"
        )
    
    with col3:
        st.metric(
            label="Net Savings",
            value=f"${net_savings:,.2f}",
            delta=f"{(net_savings/total_inflow*100) if total_inflow > 0 else 0:.1f}%",
            help="Income minus expenses"
        )
    
    with col4:
        st.metric(
            label="Transactions",
            value=f"{total_tx:,}",
            help="Total number of transactions"
        )


def _render_monthly_cash_flow(rollup_data: List[Dict[str, Any]], filters: Dict[str, Any]) -> None:
    """Render monthly inflow/outflow chart."""
    st.markdown("### 💰 Monthly Inflow vs Outflow")
    
    if not rollup_data:
        st.info("📊 No data available. Please upload and parse some bank statements first.")
        st.markdown("""
        **To see this chart:**
        1. Go to the **Ingest** tab
        2. Upload your bank statement PDFs
        3. Parse and index the statements
        4. Return here to see your monthly cash flow analysis
        """)
        return
    
    # Convert to DataFrame for easier processing
    df = pd.DataFrame(rollup_data)
    
    # Convert month string to datetime
    df['month_dt'] = pd.to_datetime(df['month'])
    df['month_str'] = df['month_dt'].dt.strftime('%Y-%m')
    
    # Group by month and sum across accounts
    monthly_summary = df.groupby('month_str').agg({
        'inflow': 'sum',
        'outflow': 'sum',
        'txCount': 'sum'
    }).reset_index()
    
    # Sort by month
    monthly_summary = monthly_summary.sort_values('month_str')
    
    # Calculate net flow
    monthly_summary['net_flow'] = monthly_summary['inflow'] - monthly_summary['outflow']
    
    # Create the chart
    fig = go.Figure()
    
    # Add inflow bars
    fig.add_trace(go.Bar(
        x=monthly_summary['month_str'],
        y=monthly_summary['inflow'],
        name='Inflow (Credits)',
        marker_color='#10b981',  # Green
        text=monthly_summary['inflow'].apply(lambda x: f'${x:,.0f}'),
        textposition='auto',
    ))
    
    # Add outflow bars
    fig.add_trace(go.Bar(
        x=monthly_summary['month_str'],
        y=monthly_summary['outflow'],
        name='Outflow (Debits)',
        marker_color='#ef4444',  # Red
        text=monthly_summary['outflow'].apply(lambda x: f'${x:,.0f}'),
        textposition='auto',
    ))
    
    # Add net flow line
    fig.add_trace(go.Scatter(
        x=monthly_summary['month_str'],
        y=monthly_summary['net_flow'],
        name='Net Flow',
        mode='lines+markers',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=8),
        yaxis='y2'
    ))
    
    # Update layout
    fig.update_layout(
        title="Monthly Inflow vs Outflow",
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        yaxis2=dict(
            title="Net Flow ($)",
            overlaying='y',
            side='right'
        ),
        barmode='group',
        hovermode='x unified',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show summary table
    with st.expander("📊 View Data Table"):
        summary_display = monthly_summary.copy()
        summary_display.columns = ['Month', 'Inflow', 'Outflow', 'Transactions', 'Net Flow']
        summary_display['Inflow'] = summary_display['Inflow'].apply(lambda x: f'${x:,.2f}')
        summary_display['Outflow'] = summary_display['Outflow'].apply(lambda x: f'${x:,.2f}')
        summary_display['Net Flow'] = summary_display['Net Flow'].apply(lambda x: f'${x:,.2f}')
        st.dataframe(summary_display, use_container_width=True, hide_index=True)
    
    # Account breakdown if multiple accounts
    if df['accountNo'].nunique() > 1:
        st.markdown("#### 🏦 By Account")
        
        # Create multi-account chart
        fig_accounts = go.Figure()
        
        for account in df['accountNo'].unique():
            account_data = df[df['accountNo'] == account].groupby('month_str').agg({
                'inflow': 'sum',
                'outflow': 'sum'
            }).reset_index()
            account_data = account_data.sort_values('month_str')
            account_data['net'] = account_data['inflow'] - account_data['outflow']
            
            fig_accounts.add_trace(go.Scatter(
                x=account_data['month_str'],
                y=account_data['net'],
                name=f'Account {account}',
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=6)
            ))
        
        fig_accounts.update_layout(
            title="Net Flow by Account",
            xaxis_title="Month",
            yaxis_title="Net Flow ($)",
            hovermode='x unified',
            height=400,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig_accounts, use_container_width=True)


def _render_spending_trends(filters: Dict[str, Any]) -> None:
    """Render spending trends over time chart."""
    st.info("📊 Spending Trends Chart - Skeleton")
    st.markdown("""
    **This section will display:**
    - Line chart showing spending trends over time
    - Daily/Weekly/Monthly aggregation options
    - Credit vs Debit comparison
    - Trend lines and moving averages
    """)
    
    # Placeholder for actual chart
    st.empty()
    
    # Time granularity selector
    col1, col2 = st.columns([3, 1])
    with col2:
        st.selectbox(
            "Granularity",
            options=["Daily", "Weekly", "Monthly"],
            key="spending_trends_granularity"
        )


def _render_category_breakdown(filters: Dict[str, Any]) -> None:
    """Render category breakdown chart."""
    st.info("🥧 Category Breakdown Chart - Skeleton")
    st.markdown("""
    **This section will display:**
    - Pie chart or donut chart for expense categories
    - Bar chart for top spending categories
    - Category-wise comparison tables
    - Percentage distribution
    """)
    
    # Placeholder for actual chart
    st.empty()
    
    # Chart type selector
    col1, col2 = st.columns([3, 1])
    with col2:
        st.selectbox(
            "Chart Type",
            options=["Pie Chart", "Bar Chart", "Treemap"],
            key="category_chart_type"
        )


def _render_cash_flow(filters: Dict[str, Any]) -> None:
    """Render cash flow analysis chart."""
    st.info("💰 Cash Flow Chart - Skeleton")
    st.markdown("""
    **This section will display:**
    - Waterfall chart showing cash flow
    - Income vs Expenses over time
    - Running balance line
    - Cumulative savings trend
    """)
    
    # Placeholder for actual chart
    st.empty()


def _render_account_comparison(filters: Dict[str, Any]) -> None:
    """Render account comparison chart."""
    st.info("🏦 Account Comparison Chart - Skeleton")
    st.markdown("""
    **This section will display:**
    - Side-by-side comparison of different accounts
    - Balance trends per account
    - Activity heatmap
    - Account performance metrics
    """)
    
    # Placeholder for actual chart
    st.empty()


def _render_transaction_tables(rollup_data: List[Dict[str, Any]], filters: Dict[str, Any]) -> None:
    """Render detailed transaction tables."""
    # Create tabs for different table views
    table_tab1, table_tab2, table_tab3 = st.tabs([
        "Monthly Summary",
        "Account Details",
        "Transaction Stats"
    ])
    
    with table_tab1:
        st.markdown("**Monthly Summary**")
        
        if not rollup_data:
            st.info("No data available")
        else:
            df = pd.DataFrame(rollup_data)
            df['month_dt'] = pd.to_datetime(df['month'])
            df['month_str'] = df['month_dt'].dt.strftime('%Y-%m')
            
            summary = df.groupby('month_str').agg({
                'inflow': 'sum',
                'outflow': 'sum',
                'txCount': 'sum'
            }).reset_index()
            
            summary['net_savings'] = summary['inflow'] - summary['outflow']
            summary['savings_rate'] = (summary['net_savings'] / summary['inflow'] * 100).round(2)
            
            summary.columns = ['Month', 'Inflow', 'Outflow', 'Transactions', 'Net Savings', 'Savings Rate (%)']
            summary = summary.sort_values('Month', ascending=False)
            
            # Format currency columns
            for col in ['Inflow', 'Outflow', 'Net Savings']:
                summary[col] = summary[col].apply(lambda x: f'${x:,.2f}')
            
            st.dataframe(summary, use_container_width=True, hide_index=True)
    
    with table_tab2:
        st.markdown("**Account Details**")
        
        if not rollup_data:
            st.info("No data available")
        else:
            df = pd.DataFrame(rollup_data)
            
            account_summary = df.groupby('accountNo').agg({
                'inflow': 'sum',
                'outflow': 'sum',
                'txCount': 'sum'
            }).reset_index()
            
            account_summary['net'] = account_summary['inflow'] - account_summary['outflow']
            account_summary['avg_monthly_inflow'] = account_summary['inflow'] / df.groupby('accountNo')['month'].nunique().values
            account_summary['avg_monthly_outflow'] = account_summary['outflow'] / df.groupby('accountNo')['month'].nunique().values
            
            account_summary.columns = ['Account', 'Total Inflow', 'Total Outflow', 'Transactions', 'Net', 'Avg Monthly Inflow', 'Avg Monthly Outflow']
            
            # Format currency columns
            for col in ['Total Inflow', 'Total Outflow', 'Net', 'Avg Monthly Inflow', 'Avg Monthly Outflow']:
                account_summary[col] = account_summary[col].apply(lambda x: f'${x:,.2f}')
            
            st.dataframe(account_summary, use_container_width=True, hide_index=True)
    
    with table_tab3:
        st.markdown("**Transaction Statistics**")
        
        if not rollup_data:
            st.info("No data available")
        else:
            df = pd.DataFrame(rollup_data)
            
            total_months = df['month'].nunique()
            total_accounts = df['accountNo'].nunique()
            total_inflow = df['inflow'].sum()
            total_outflow = df['outflow'].sum()
            total_tx = df['txCount'].sum()
            
            stats_data = {
                'Metric': [
                    'Total Months',
                    'Total Accounts',
                    'Total Transactions',
                    'Total Inflow',
                    'Total Outflow',
                    'Net Flow',
                    'Avg Monthly Inflow',
                    'Avg Monthly Outflow',
                    'Avg Transactions/Month'
                ],
                'Value': [
                    f'{total_months}',
                    f'{total_accounts}',
                    f'{total_tx:,}',
                    f'${total_inflow:,.2f}',
                    f'${total_outflow:,.2f}',
                    f'${total_inflow - total_outflow:,.2f}',
                    f'${total_inflow / total_months:,.2f}' if total_months > 0 else '$0.00',
                    f'${total_outflow / total_months:,.2f}' if total_months > 0 else '$0.00',
                    f'{total_tx / total_months:.1f}' if total_months > 0 else '0'
                ]
            }
            
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

