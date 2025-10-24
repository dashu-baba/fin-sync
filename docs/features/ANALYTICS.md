# Analytics Dashboard

Interactive financial analytics and visualizations powered by Elastic aggregations and Plotly charts.

---

## Overview

The Analytics Dashboard provides:
- 📊 **Monthly Income/Expense Trends** - Line charts showing cash flow over time
- 💰 **Net Flow Analysis** - Track surplus/deficit by month
- 📈 **Account Distribution** - Pie charts of transactions by account
- 🔍 **Balance Evolution** - See how account balances change
- 🎯 **Filterable Views** - Drill down by account, date range

---

## Features

### 1. Monthly Trends

**Visualization**: Interactive line chart with dual Y-axes

```
Income vs Expenses (2024)

$8,000 ┤     •                      Income
       │    ╱ ╲                    Expenses
$6,000 ┤   •   •─────•
       │  ╱         ╱ ╲
$4,000 ┤ •       •──   ──•
       │        ╱          ╲
$2,000 ┤   •───•            •
       │
$0     └─────────────────────────────────
        Jan Feb Mar Apr May Jun Jul Aug
```

**Data Query** (ES|QL):
```sql
FROM finsync-transactions
| EVAL month = DATE_FORMAT(statementDate, 'yyyy-MM')
| STATS 
    income = SUM(CASE(statementType == 'credit', statementAmount, 0)),
    expense = SUM(CASE(statementType == 'debit', statementAmount, 0))
  BY month
| EVAL net = income - expense
| SORT month ASC
```

### 2. Account Distribution

**Visualization**: Pie chart showing transaction volume per account

```
Transaction Distribution

┌─────────────────────────┐
│   Savings: 45%  █████   │
│   Checking: 35% ████    │
│   Credit: 20%   ███     │
└─────────────────────────┘
```

**Data Query**:
```sql
FROM finsync-transactions
| STATS count = COUNT(*), total = SUM(statementAmount)
  BY accountNo, accountName
| SORT count DESC
```

### 3. Balance Evolution

**Visualization**: Area chart showing balance over time

```
Account Balance Over Time

$15,000 ┤               ░░░░░
        │           ░░░░    ░░░
$10,000 ┤       ░░░░          ░░
        │   ░░░░
$5,000  ┤░░░
        │
$0      └──────────────────────────
         Jan  Feb  Mar  Apr  May
```

### 4. Top Merchants

**Visualization**: Horizontal bar chart

```
Top 10 Merchants by Spending

Walmart     ████████████████ $1,234
Amazon      ██████████████ $987
Target      ████████████ $765
Kroger      ██████████ $654
Shell       ████████ $543
Starbucks   ██████ $432
Netflix     ████ $321
Uber        ███ $234
McDonald's  ██ $123
Hulu        █ $87
```

---

## User Interface

### Dashboard Layout

```
┌─────────────────────────────────────────────────────────┐
│  Analytics Dashboard                           [Export] │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Filters:                                                │
│  Account: [All Accounts ▼]                              │
│  Date Range: [Last 12 Months ▼]  [2024-01] to [2024-12]│
│  [Apply Filters]                                        │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Key Metrics                                             │
│  ┌───────────┬───────────┬───────────┬───────────┐     │
│  │  Income   │  Expenses │   Net     │   Count   │     │
│  │  $45,231  │  $38,492  │  +$6,739  │    847    │     │
│  └───────────┴───────────┴───────────┴───────────┘     │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Monthly Income vs Expenses                              │
│  [Interactive Plotly Line Chart]                        │
│                                                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────┬─────────────────────────────┐ │
│  │  Account Distribution│  Balance Evolution          │ │
│  │  [Pie Chart]         │  [Area Chart]               │ │
│  └─────────────────────┴─────────────────────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Interactive Features

**Hover**: Show exact values
```
[Hover on point]
Month: January 2024
Income: $5,234.56
Expenses: $4,123.45
Net: +$1,111.11
```

**Click**: Filter to specific month
**Zoom**: Pinch/scroll to zoom in on time periods
**Pan**: Drag to move view
**Download**: Export as PNG, SVG, or data

---

## Implementation

### Backend Query

```python
from elastic.analytics import get_monthly_aggregates

def load_analytics_data(
    account_filter: str = "all",
    date_from: str = None,
    date_to: str = None
) -> dict:
    """
    Load analytics data from Elastic.
    
    Returns:
        {
            "monthly_trends": [...],
            "account_distribution": [...],
            "balance_evolution": [...],
            "top_merchants": [...],
            "summary": {
                "total_income": float,
                "total_expenses": float,
                "net_flow": float,
                "transaction_count": int
            }
        }
    """
    # Build ES|QL query
    query = f"""
    FROM finsync-transactions
    | WHERE statementDate >= '{date_from}' 
      AND statementDate <= '{date_to}'
    """
    
    if account_filter != "all":
        query += f" AND accountNo == '{account_filter}'"
    
    query += """
    | EVAL month = DATE_FORMAT(statementDate, 'yyyy-MM')
    | STATS 
        income = SUM(CASE(statementType == 'credit', statementAmount, 0)),
        expense = SUM(CASE(statementType == 'debit', statementAmount, 0)),
        count = COUNT(*)
      BY month
    | EVAL net = income - expense
    | SORT month ASC
    """
    
    result = es_client.esql.query(query=query)
    return parse_analytics_result(result)
```

### Frontend Rendering

```python
import streamlit as st
import plotly.graph_objects as go

def render_analytics_dashboard():
    """Render analytics dashboard with Plotly charts."""
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        account = st.selectbox("Account", ["All", "Savings", "Checking"])
    with col2:
        date_range = st.selectbox("Period", [
            "Last 6 Months",
            "Last 12 Months",
            "Year to Date",
            "Custom"
        ])
    
    # Load data
    data = load_analytics_data(account, *parse_date_range(date_range))
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Income", f"${data['summary']['total_income']:,.2f}")
    col2.metric("Total Expenses", f"${data['summary']['total_expenses']:,.2f}")
    col3.metric("Net Flow", f"${data['summary']['net_flow']:,.2f}")
    col4.metric("Transactions", data['summary']['transaction_count'])
    
    # Monthly trends chart
    fig = go.Figure()
    
    # Income line
    fig.add_trace(go.Scatter(
        x=data['monthly_trends']['months'],
        y=data['monthly_trends']['income'],
        name='Income',
        line=dict(color='green', width=3),
        mode='lines+markers'
    ))
    
    # Expenses line
    fig.add_trace(go.Scatter(
        x=data['monthly_trends']['months'],
        y=data['monthly_trends']['expense'],
        name='Expenses',
        line=dict(color='red', width=3),
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title='Monthly Income vs Expenses',
        xaxis_title='Month',
        yaxis_title='Amount ($)',
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Additional charts...
```

---

## Performance

### Query Optimization

**Use ES|QL for aggregations** (fast):
```python
# ✅ Good: ES|QL aggregation
result = es_client.esql.query(query="""
    FROM finsync-transactions
    | STATS total = SUM(statementAmount) BY month
""")
# Latency: 30-100ms
```

**Avoid fetching all documents** (slow):
```python
# ❌ Bad: Fetch all, aggregate in Python
all_docs = es_client.search(index="finsync-transactions", size=10000)
total = sum(doc['statementAmount'] for doc in all_docs)
# Latency: 500-2000ms
```

### Caching Strategy

```python
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_analytics_data(account, date_from, date_to):
    """Cached analytics data."""
    return fetch_from_elastic(account, date_from, date_to)
```

### Progressive Loading

```python
# Load summary first
summary = load_summary_fast()
st.write(summary)

# Load charts in background
with st.spinner("Loading charts..."):
    charts_data = load_detailed_data()
    render_charts(charts_data)
```

---

## Customization

### Add Custom Chart

```python
# In ui/components/analytics_view.py

def render_custom_chart(data: dict):
    """Render custom analytics chart."""
    fig = go.Figure()
    
    # Your custom visualization
    fig.add_trace(go.Bar(
        x=data['categories'],
        y=data['values'],
        name='Custom Metric'
    ))
    
    fig.update_layout(title='My Custom Chart')
    
    st.plotly_chart(fig, use_container_width=True)
```

### Add Custom Metric

```python
# In elastic/analytics.py

def get_custom_metric() -> float:
    """Calculate custom metric."""
    query = """
    FROM finsync-transactions
    | WHERE statementType == 'debit'
    | STATS avg_daily = SUM(statementAmount) / COUNT(DISTINCT statementDate)
    """
    
    result = es_client.esql.query(query=query)
    return result['values'][0][0]
```

---

## Export Options

### Export as CSV

```python
import pandas as pd

# Convert data to DataFrame
df = pd.DataFrame(data['monthly_trends'])

# Download button
csv = df.to_csv(index=False)
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="analytics_export.csv",
    mime="text/csv"
)
```

### Export as PNG

```python
# Plotly has built-in export
fig.write_image("analytics_chart.png", width=1200, height=600)
```

---

## Best Practices

### For Performance

✅ **Use ES|QL for aggregations** - Much faster than Python  
✅ **Cache results** - Avoid redundant queries  
✅ **Limit date ranges** - Smaller ranges = faster queries  
✅ **Progressive loading** - Load critical data first  
❌ **Don't fetch all documents** - Use aggregations  
❌ **Don't aggregate in Python** - Use Elastic

### For UX

✅ **Show loading states** - Spinners, progress bars  
✅ **Provide filters** - Account, date range  
✅ **Make interactive** - Hover, click, zoom  
✅ **Default to useful range** - Last 12 months  
❌ **Don't auto-refresh too often** - Causes flicker  
❌ **Don't overwhelm with charts** - Focus on key insights

---

## Troubleshooting

### Issue: Charts not loading

**Possible causes**:
- Elastic query failing
- No data for selected filters
- Plotly not installed

**Solutions**:
- Check Elastic connection
- Verify data exists for date range
- Reinstall: `pip install plotly`

### Issue: Slow loading

**Possible causes**:
- Too large date range
- No caching
- Inefficient queries

**Solutions**:
- Limit to 12-24 months
- Enable `@st.cache_data`
- Use ES|QL aggregations

### Issue: Charts not interactive

**Possible causes**:
- Streamlit version < 1.39
- `use_container_width=False`

**Solutions**:
- Upgrade Streamlit
- Set `use_container_width=True`

---

**Related**: [ES|QL Analytics](../implementation/ELASTIC_INTEGRATION.md) | [UI Components](../implementation/UI_COMPONENTS.md)

