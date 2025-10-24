# Data Flow Architecture

This document details how data flows through the FinSync system across different use cases.

---

## Overview

FinSync has three primary data flows:
1. **Ingestion Flow**: PDF → Parsed Data → Indexed Documents
2. **Query Flow**: User Question → Intent → Search → Answer
3. **Analytics Flow**: Aggregation Request → ES|QL → Visualizations

---

## 1. Document Ingestion Flow

### End-to-End Process

```
┌─────────────┐
│ User Upload │
│   PDF File  │
└──────┬──────┘
       │
       ▼
┌──────────────────────────────────────┐
│  1. Upload Service                   │
│  • Validate file type (.pdf)         │
│  • Check size limits (< 100MB)       │
│  • Generate session ID                │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  2. Duplicate Detection               │
│  • Filename check                     │
│  • Content hash (SHA-256)             │
│  • Metadata check (accountNo + dates) │
└──────┬───────────────────────────────┘
       │ [If duplicate → Reject]
       ▼
┌──────────────────────────────────────┐
│  3. Storage Backend                   │
│  • LocalStorage (dev)                 │
│  • GCSStorage (prod)                  │
│  • Save file with session prefix      │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  4. PDF Reader (PyPDF2)               │
│  • Extract text from all pages        │
│  • Handle encrypted PDFs (password)   │
│  • Preserve formatting where possible │
└──────┬───────────────────────────────┘
       │ Raw text
       ▼
┌──────────────────────────────────────┐
│  5. Vertex AI Parser (Gemini)        │
│  • Send text + schema prompt          │
│  • Model: gemini-2.5-pro              │
│  • Extract structured JSON            │
└──────┬───────────────────────────────┘
       │ Parsed JSON
       ▼
┌──────────────────────────────────────┐
│  6. Validation (Pydantic)             │
│  • ParsedStatement model              │
│  • Type checking                      │
│  • Date parsing                       │
└──────┬───────────────────────────────┘
       │ Validated data
       ▼
┌──────────────────────────────────────┐
│  7. Embedding Generation              │
│  • text-embedding-004                 │
│  • Embed statement descriptions       │
│  • Output: 768-dim vectors            │
└──────┬───────────────────────────────┘
       │ Data + embeddings
       ▼
┌──────────────────────────────────────┐
│  8. Elastic Indexing                  │
│  • Index transactions                 │
│  • Index statement with vectors       │
│  • Bulk operations for performance    │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  9. User Confirmation                 │
│  • Display success message            │
│  • Show parsed account info           │
│  • Transaction count                  │
└───────────────────────────────────────┘
```

### Data Transformations

#### Step 1: Raw PDF → Text
```python
# Input: Binary PDF file
file_bytes = uploaded_file.read()

# Output: Text string
text = extract_text_from_pdf(file_bytes, password="optional")
# Example: "Account Statement\nAccount No: 123456\n..."
```

#### Step 2: Text → Structured JSON
```python
# Input: Raw text
text = "Account Statement\nAccount No: 123456\nDate: 2025-01..."

# Gemini prompt includes schema definition
parsed_json = parse_with_vertex_ai(text, model="gemini-2.5-pro")

# Output: Structured JSON
{
  "accountName": "John Doe",
  "accountNo": "123456",
  "statements": [...]
}
```

#### Step 3: JSON → Elastic Documents
```python
# Input: Parsed statement
parsed = ParsedStatement(accountName="John Doe", ...)

# Output 1: Transaction documents (flat)
[
  {
    "accountNo": "123456",
    "statementDate": "2025-01-02",
    "statementAmount": 5000.00,
    "statementType": "credit",
    "statementDescription": "Salary",
    "statementBalance": 12500.00
  },
  ...
]

# Output 2: Statement document (with vector)
{
  "accountNo": "123456",
  "statementFrom": "2025-01-01",
  "statementTo": "2025-01-31",
  "rawText": "Account Statement...",
  "desc_vector": [0.123, -0.456, ...],  # 768 dimensions
  "statements": [nested transactions]
}
```

### Error Handling

| Error | Recovery Strategy |
|-------|-------------------|
| **Invalid PDF** | Show error, reject upload |
| **Password-protected** | Prompt for password |
| **Parse failure** | Retry with different prompt, or manual review |
| **Duplicate detected** | Reject with explanation, show existing file |
| **Indexing failure** | Retry with exponential backoff, log error |

---

## 2. Query Processing Flow

### Intent Classification Path

```
User Query: "How much did I spend on groceries last month?"
    ↓
┌──────────────────────────────────────┐
│  1. Intent Classification             │
│  • Model: Gemini 2.5 Pro              │
│  • Prompt: INTENT_ROUTER_PROMPT       │
│  • Output: IntentResponse             │
└──────┬───────────────────────────────┘
       │ Classification result
       ▼
┌──────────────────────────────────────┐
│  2. Confidence Check                  │
│  • If < 0.75 → Confirmation dialog    │
│  • If needsClarification → Ask user   │
│  • Else → Proceed                     │
└──────┬───────────────────────────────┘
       │ Confirmed intent
       ▼
┌──────────────────────────────────────┐
│  3. Intent Execution Router           │
│  • aggregate                          │
│  • aggregate_filtered_by_text         │
│  • text_qa                            │
│  • provenance                         │
│  • trend                              │
│  • listing                            │
└──────┬───────────────────────────────┘
       │ Route to executor
       ▼
[See intent-specific flows below]
```

### Intent-Specific Flows

#### **aggregate Intent**
```
Query: "Total spending last month"
    ↓
Extract filters: {
  date_from: "2024-12-01",
  date_to: "2024-12-31",
  type: "debit"
}
    ↓
Build ES|QL query:
```
```sql
FROM finsync-transactions
| WHERE statementDate >= "2024-12-01" 
  AND statementDate <= "2024-12-31"
  AND statementType == "debit"
| STATS 
    total = SUM(statementAmount),
    count = COUNT(*),
    avg = AVG(statementAmount)
```
```
    ↓
Execute on Elastic → Results
    ↓
Compose answer: "You spent $3,245.00 last month across 47 transactions."
```

#### **aggregate_filtered_by_text Intent**
```
Query: "How much did I spend on groceries?"
    ↓
Step 1: Semantic Search on Statements
    ↓
Build hybrid query (BM25 + kNN):
  - Keyword: "groceries"
  - Vector: embedding_of("groceries")
    ↓
Execute → Get matching statements
    ↓
Extract merchant terms: ["Walmart", "Kroger", "Whole Foods"]
    ↓
Step 2: Aggregate Transactions
    ↓
Build ES|QL with derived filters:
```
```sql
FROM finsync-transactions
| WHERE statementDescription LIKE "Walmart" 
   OR statementDescription LIKE "Kroger"
   OR statementDescription LIKE "Whole Foods"
| STATS total = SUM(statementAmount)
```
```
    ↓
Compose answer: "You spent $875.50 on groceries at Walmart, Kroger, and Whole Foods."
```

#### **text_qa Intent**
```
Query: "What fees are mentioned in my statement?"
    ↓
Step 1: Hybrid Search on Statements
    ↓
BM25 query: "fees"
kNN query: embedding_of("What fees are mentioned")
    ↓
RRF Fusion (k=60):
  - Combine keyword + semantic results
  - Score = 1/(k + rank)
    ↓
Top 5 results with provenance
    ↓
Step 2: Generate Answer with Gemini
    ↓
Prompt: "Answer this question based on context: [results]"
    ↓
Answer: "Your statement mentions the following fees: overdraft fee ($35), monthly service fee ($10)..."
    ↓
Append citations: [Statement 1, Page 2]
```

### Clarification Flow

```
User Query: "Show my spending"
    ↓
Classify intent → confidence = 0.68
    ↓
[Low confidence detected]
    ↓
Display confirmation dialog:
  "I understood: Aggregate expenses. Is this correct?"
  [✅ Yes] [❌ No, let me rephrase]
    ↓
If Yes → Proceed with execution
If No → Return to input
```

```
User Query: "bkash transactions"
    ↓
Classify intent → needsClarification = true
    ↓
clarifyQuestion: "Which time period?"
    ↓
Display clarification dialog:
  "🤔 Which time period are you interested in?"
  [Input: "last month"]
  [Continue] [Skip]
    ↓
Re-classify with context:
  - Original: "bkash transactions"
  - Clarification: "last month"
  - Cumulative: "bkash transactions last month"
    ↓
New intent with higher confidence → Execute
```

---

## 3. Analytics Dashboard Flow

```
User Opens Analytics Page
    ↓
┌──────────────────────────────────────┐
│  1. Initialize Filters                │
│  • Account: All / Specific            │
│  • Date range: Custom / Presets       │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  2. Query Monthly Aggregates          │
│  • ES|QL query with date_histogram    │
│  • Group by month                     │
│  • Sum income, expenses                │
└──────┬───────────────────────────────┘
       │ Aggregation results
       ▼
┌──────────────────────────────────────┐
│  3. Transform Data for Plotly         │
│  • Convert to DataFrame format        │
│  • Calculate net = income - expenses  │
│  • Format dates                       │
└──────┬───────────────────────────────┘
       │ Chart data
       ▼
┌──────────────────────────────────────┐
│  4. Generate Visualizations           │
│  • Line chart: Income vs Expenses     │
│  • Bar chart: Net flow by month       │
│  • Pie chart: Account distribution    │
└──────┬───────────────────────────────┘
       │ Plotly figures
       ▼
┌──────────────────────────────────────┐
│  5. Render in Streamlit               │
│  • st.plotly_chart()                  │
│  • Interactive hover/zoom             │
│  • Responsive layout                  │
└───────────────────────────────────────┘
```

---

## Session State Management

### Session Variables

```python
{
    # File upload tracking
    "uploaded_files": list,
    "session_id": str,
    
    # Chat conversation
    "chat_history": list[dict],
    "pending_query": str | None,
    
    # Clarification state
    "clarification_mode": str | None,  # "confirm" | "clarify"
    "pending_intent": IntentResponse | None,
    "current_conversation": list,
    
    # Analytics filters
    "selected_account": str,
    "date_range": tuple[date, date],
    
    # UI state
    "show_intent_details": bool,
    "active_tab": str
}
```

### State Transitions

```
IDLE
  ↓ [User uploads file]
UPLOADING
  ↓ [File saved]
PARSING
  ↓ [Parse complete]
IDLE

IDLE
  ↓ [User enters query]
CLASSIFYING
  ↓ [Low confidence]
AWAITING_CONFIRMATION
  ↓ [User confirms]
EXECUTING
  ↓ [Results ready]
IDLE

IDLE
  ↓ [User enters query]
CLASSIFYING
  ↓ [Needs clarification]
AWAITING_CLARIFICATION
  ↓ [User provides info]
RECLASSIFYING
  ↓ [Clear now]
EXECUTING
  ↓ [Results ready]
IDLE
```

---

## Performance Characteristics

### Latency Breakdown

**Document Upload**:
```
File upload: 100-500ms (network)
PDF extraction: 200-1000ms (file size dependent)
Vertex AI parsing: 3-10 seconds (complexity dependent)
Embedding generation: 500-2000ms (batch size)
Elastic indexing: 100-500ms (document count)
---
Total: 4-14 seconds
```

**Query Processing**:
```
Intent classification: 500-2000ms (Gemini)
Elastic search: 20-200ms (query complexity)
Answer generation: 1-3 seconds (Gemini)
---
Total: 2-5 seconds
```

**Analytics Loading**:
```
ES|QL aggregation: 50-300ms (data size)
Chart rendering: 100-500ms (browser)
---
Total: < 1 second
```

### Optimization Opportunities

1. **Caching**: Cache frequent queries in Redis
2. **Batching**: Batch multiple embeddings in one call
3. **Streaming**: Stream Gemini responses for faster perceived latency
4. **Precomputation**: Pre-compute common aggregations
5. **Lazy Loading**: Load analytics charts on demand

---

## Error Propagation

```
Component Error
    ↓
Log with context (logger.error)
    ↓
Wrap in user-friendly message
    ↓
Display in UI with error icon
    ↓
Offer recovery actions:
  - Retry
  - Modify query
  - Contact support
```

### Example Error Handling

```python
try:
    result = execute_aggregate(filters)
except ElasticsearchException as e:
    log.error(f"Elastic query failed: {e}", exc_info=True)
    return {
        "error": "Search service unavailable. Please try again.",
        "technical_details": str(e)  # Only in dev mode
    }
except Exception as e:
    log.exception("Unexpected error in aggregation")
    return {
        "error": "An unexpected error occurred. Our team has been notified."
    }
```

---

## Data Consistency

### Eventual Consistency

Elastic indexing is **near-realtime**:
- Documents indexed within 1 second (refresh_interval)
- Queries may not immediately see new documents
- Analytics use refresh to ensure consistency

### Transaction Boundaries

No distributed transactions. Operations are:
1. **Idempotent**: Safe to retry
2. **Atomic per-index**: Single document operations
3. **Best-effort**: Duplicate detection catches most issues

---

## Conclusion

FinSync's data flows are designed for:
- **Reliability**: Multiple layers of validation
- **Performance**: Async operations, efficient queries
- **Observability**: Comprehensive logging at each step
- **User Experience**: Clear feedback, graceful error handling

Each flow prioritizes user experience while maintaining data integrity.

---

**Related**: [System Overview](./OVERVIEW.md) | [Intent System](./INTENT_SYSTEM.md)

