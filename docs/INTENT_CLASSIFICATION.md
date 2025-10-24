# Intent Classification System

## Overview

The Intent Classification System is an intelligent layer that analyzes user queries before executing the main search and chat workflow. It uses Google Vertex AI to understand the user's intent and extract relevant parameters from natural language queries.

## Architecture

### Components

1. **Intent Router** (`llm/intent_router.py`)
   - Core module that handles LLM calls for intent classification
   - Uses Vertex AI Gemini model with strict JSON output
   - Implements error handling and retry logic

2. **Intent Models** (`models/intent.py`)
   - Pydantic models for type-safe intent classification
   - Validates LLM responses against schema
   - Includes: `IntentClassification`, `IntentFilters`, `IntentResponse`

3. **UI Components** (`ui/components/intent_display.py`)
   - Visual display of intent classification results
   - Shows extracted filters, metrics, and confidence scores
   - Includes debug information for developers

4. **Chat Integration** (`ui/pages/chat_page.py`)
   - Integrates intent classification into chat workflow
   - Displays intent results before executing search
   - Maintains backward compatibility with existing workflow

## Intent Types

The system classifies queries into 6 distinct intent types:

| Intent Type | Description | Example Queries |
|------------|-------------|-----------------|
| `aggregate` | Numeric aggregations, totals, counts | "Total spending last month?" |
| `text_qa` | Semantic text Q&A from statements | "What is a debit transaction?" |
| `aggregate_filtered_by_text` | Aggregate with text-based filtering | "Total fees mentioned in statements?" |
| `listing` | Tabular list of transactions | "Show last 10 bkash transactions" |
| `trend` | Time-series trends | "Monthly spending trend for 2024" |
| `provenance` | Source citations and evidence | "Which page shows my loan details?" |

## Extracted Parameters

### Filters
- `accountNo`: Exact account number if specified
- `dateFrom` / `dateTo`: ISO-8601 dates (resolved from relative expressions)
- `counterparty`: Merchant/payee keywords (e.g., "bkash", "uber")
- `minAmount` / `maxAmount`: Numeric amount boundaries

### Metrics
Available metrics include:
- `sum_income`, `sum_expense`, `net`
- `count`, `avg`
- `top_merchants`, `top_categories`
- `monthly_trend`, `weekly_trend`, `daily_trend`

### Other Parameters
- `granularity`: "daily" | "weekly" | "monthly"
- `needsTable`: Boolean indicating if results should be tabular
- `answerStyle`: "concise" | "detailed"
- `confidence`: 0.0-1.0 score
- `needsClarification`: Boolean flag with optional clarification question

## Usage

### Basic Usage

```python
from llm.intent_router import classify_intent

# Classify a user query
result = classify_intent("What was my total spending last month?")

print(f"Intent: {result.classification.intent}")
print(f"Confidence: {result.classification.confidence}")
print(f"Date Range: {result.classification.filters.dateFrom} to {result.classification.filters.dateTo}")
```

### Safe Usage (Recommended)

```python
from llm.intent_router import classify_intent_safe

# Returns None on failure instead of raising exception
result = classify_intent_safe("Show me bkash transactions")

if result:
    classification = result.classification
    # Use classification...
else:
    # Fallback to default behavior
    pass
```

### In UI/Chat Context

The intent classification is automatically integrated into the chat workflow:

1. User enters a query
2. System classifies intent (shown in expandable debug section)
3. Existing search and chat workflow executes as before
4. Results are displayed with intent context

## Workflow Integration

### Current Flow

```
User Query
    ↓
[NEW] Intent Classification (LLM Call #1)
    ↓
Display Intent JSON (Debug UI)
    ↓
Hybrid Search (Existing)
    ↓
Answer Generation (LLM Call #2 - Existing)
    ↓
Display Results
```

### Key Features

1. **Non-Breaking**: Existing workflow continues unchanged
2. **Observable**: Intent classification results are visible in UI
3. **Fault-Tolerant**: System continues even if intent classification fails
4. **Logged**: All steps are properly logged for debugging

## Testing

### Manual Testing

Run the test script:

```bash
cd /Users/nowshadurrahaman/Projects/Nowshad/fin-sync
python scripts/test_intent_router.py
```

### Test Queries

The script tests various query types:
- Aggregate: "What was my total spending last month?"
- Text QA: "What is a debit transaction?"
- Listing: "Show me the last 10 transactions"
- Trend: "Show my monthly spending trend for 2024"

### Integration Testing

1. Start the Streamlit app: `streamlit run ui/app.py`
2. Navigate to the "Chat" tab
3. Enter test queries and check:
   - Intent classification appears in debug expander
   - Correct intent type is identified
   - Filters and parameters are extracted
   - Existing chat functionality works

## Configuration

### Environment Variables

The system uses existing Vertex AI configuration:

```env
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
VERTEX_MODEL_GENAI=gemini-1.5-flash-002
```

### Model Settings

Intent classification uses:
- **Temperature**: 0.0 (deterministic)
- **Max Tokens**: 2048
- **Output Format**: JSON only

## Logging

All intent classification operations are logged:

```python
from core.logger import get_logger

log = get_logger("llm/intent_router")
```

Log levels:
- `INFO`: Successful classifications, timing
- `DEBUG`: Raw LLM responses, detailed processing
- `WARNING`: Classification failures (safe mode)
- `ERROR`: Exceptions and errors
- `EXCEPTION`: Full stack traces

## Future Enhancements

The intent classification system is designed for future integration:

1. **Intent-Based Routing**: Route queries to specialized handlers
2. **Smart Filtering**: Apply extracted filters to searches
3. **Metric Computation**: Directly compute requested metrics
4. **Clarification Dialogs**: Ask users for clarification when confidence is low
5. **Query Rewriting**: Enhance queries based on intent understanding

## Troubleshooting

### Common Issues

**Issue**: "Empty response from LLM"
- **Cause**: Model returned no text
- **Solution**: Check GCP credentials and quota

**Issue**: "Invalid JSON from LLM"
- **Cause**: Model didn't follow JSON format
- **Solution**: Review prompt or try different model temperature

**Issue**: "Intent classification failed"
- **Cause**: Network, auth, or model error
- **Solution**: Check logs, verify GCP setup

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("llm/intent_router").setLevel(logging.DEBUG)
```

## Performance

Typical performance metrics:

- **Classification Time**: 500-2000ms (depending on model and network)
- **Token Usage**: ~500-1000 tokens per classification
- **Accuracy**: High confidence (>0.8) for clear queries

## Security & Privacy

- All queries are processed through Google Vertex AI
- Data is subject to GCP's privacy and security policies
- Queries and classifications are logged locally for debugging
- No sensitive data is exposed in UI (debug mode only)

## Contributing

When modifying the intent system:

1. Update intent types in `models/intent.py`
2. Adjust prompt in `llm/intent_router.py`
3. Update UI components if needed
4. Add test cases to `scripts/test_intent_router.py`
5. Update this documentation

## References

- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Pydantic Models](https://docs.pydantic.dev/)
- [Streamlit Components](https://docs.streamlit.io/)

