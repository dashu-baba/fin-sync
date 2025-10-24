# Intent Classification Feature

Natural language understanding that determines user intent from conversational queries.

---

## Overview

Intent Classification transforms natural language questions into structured queries:
- **"How much did I spend last month?"** → `aggregate` intent with date filters
- **"What fees are mentioned?"** → `text_qa` intent for semantic search
- **"Show groceries spending"** → `aggregate_filtered_by_text` for hybrid query

---

## User Experience

### High Confidence Query (>75%)

```
User: "Total spending in January 2025"
    ↓
[System classifies intent instantly]
    ↓
🎯 Intent: aggregate
📊 Filters: date_from=2025-01-01, date_to=2025-01-31, type=debit
✅ Confidence: 92%
    ↓
[Executes query immediately]
    ↓
"You spent $3,245.67 in January 2025 across 47 transactions."
```

### Low Confidence Query (≤75%)

```
User: "show my spending"
    ↓
[System classifies with low confidence]
    ↓
⚠️ Please Confirm
I understood your query as:
• Intent: Aggregate (sum expenses)
• Confidence: 68%

Is this what you're looking for?
[✅ Yes, Continue] [❌ No, Let Me Rephrase]
    ↓
[User clicks Yes]
    ↓
[Executes query]
```

### Clarification Needed

```
User: "bkash transactions"
    ↓
[System identifies missing information]
    ↓
❓ Need More Information
🤔 Which time period are you interested in?

Your response: [last month___]
[Continue] [Skip & Search All]
    ↓
[User enters "last month"]
    ↓
[Re-classifies with context: "bkash transactions last month"]
    ↓
[Executes with higher confidence]
```

---

## Supported Intents

### 1. aggregate
**Purpose**: Calculate totals, averages, counts  
**Examples**:
- "Total spending last month"
- "Average transaction amount in Q1"
- "How many transactions in 2024?"
- "Sum of all debits"

**Extracted Parameters**:
- Date range (from, to)
- Transaction type (credit/debit)
- Account numbers
- Amount range (min, max)
- Counterparty names

### 2. aggregate_filtered_by_text
**Purpose**: Aggregate with semantic filtering  
**Examples**:
- "How much did I spend on groceries?"
- "Total at merchants mentioned in my statement"
- "Spending on dining out"

**Two-Step Process**:
1. Semantic search to find relevant merchants
2. Aggregate transactions for those merchants

### 3. text_qa
**Purpose**: Answer questions about statement content  
**Examples**:
- "What fees are mentioned?"
- "Tell me about overdraft charges"
- "What does my statement say about interest?"

**Process**: Hybrid search + Gemini answer generation

### 4. provenance
**Purpose**: Show source documents  
**Examples**:
- "Show sources about fees"
- "Where did this information come from?"
- "What statements mention ABC Bank?"

**Output**: List of statements with relevance scores

### 5. trend
**Purpose**: Time-series analysis  
**Examples**:
- "Monthly spending trend"
- "Income vs expenses over time"
- "Transaction counts by week"

**Output**: Time-series data for charting

### 6. listing
**Purpose**: List individual transactions  
**Examples**:
- "Show last 10 transactions"
- "List all Amazon purchases"
- "Recent transactions over $100"

**Output**: Sorted list of transactions

---

## Classification Process

### Step 1: Send to Gemini

```python
from llm.intent_router import classify_intent

result = classify_intent(
    query="How much did I spend on groceries last month?"
)

# Returns IntentResponse
{
    "classification": {
        "intent": "aggregate_filtered_by_text",
        "confidence": 0.85,
        "filters": {
            "text_terms": ["groceries"],
            "date_from": "2024-12-01",
            "date_to": "2024-12-31",
            "transaction_type": "debit"
        },
        "needsClarification": False,
        "clarifyQuestion": None,
        "reasoning": "User wants aggregation with text filter 'groceries'"
    },
    "processing_time_ms": 1247
}
```

### Step 2: Confidence Check

```python
from ui.services.clarification_manager import ClarificationManager

if ClarificationManager.should_proceed_immediately(result):
    # High confidence → Execute
    execute_intent(query, result)
    
elif ClarificationManager.should_ask_for_confirmation(result):
    # Low confidence → Ask confirmation
    show_confirmation_dialog(result)
    
elif ClarificationManager.should_ask_for_clarification(result):
    # Missing info → Ask specific question
    show_clarification_dialog(result.classification.clarifyQuestion)
```

### Step 3: Execute or Clarify

**Immediate Execution** (confidence > 75%):
- Route to appropriate executor
- Run query on Elastic
- Generate answer
- Display results

**Confirmation Required** (confidence ≤ 75%):
- Show confirmation dialog
- Display interpreted intent
- Wait for user response
- Execute if confirmed, else return to input

**Clarification Required** (needsClarification = true):
- Show clarification dialog
- Ask specific question
- Collect user response
- Re-classify with context
- Execute with enhanced query

---

## UI Components

### Intent Display

When a query is classified, the system shows:

```
🎯 Intent Classification

Intent Type: aggregate_filtered_by_text
Confidence: 85% ████████████░░░

📋 Extracted Parameters:
• Text Terms: groceries
• Date Range: 2024-12-01 to 2024-12-31
• Transaction Type: debit

💭 Reasoning:
User wants to aggregate transactions filtered by text term "groceries"
for the previous month (debit transactions only).

⏱️ Processing Time: 1.25s
```

### Confirmation Dialog

```
⚠️ Please Confirm

I understood your query as:
• Calculate total spending
• For all transactions
• No specific time period

Confidence: 68%

Is this what you're looking for?

[✅ Yes, Continue]  [❌ No, Let Me Rephrase]
```

### Clarification Dialog

```
❓ Need More Information

🤔 Which time period are you interested in?

Examples: "last month", "2024", "last 3 months"

Your response:
[_________________________________]

[Continue]  [Skip & Search All]
```

---

## Advanced Features

### Context-Aware Re-classification

After clarification, the system re-classifies with full context:

```python
from llm.intent_router import classify_intent_with_context

# Original query
original = "show bkash transactions"

# Conversation history
conversation = [
    {"type": "query", "text": "show bkash transactions"},
    {"type": "clarification_request", "text": "Which time period?"},
    {"type": "clarification_response", "text": "last month"}
]

# Re-classify with context
result = classify_intent_with_context(
    query=original,
    conversation=conversation
)

# Now has higher confidence and complete filters
{
    "intent": "listing",
    "confidence": 0.93,  # Higher than initial
    "filters": {
        "text_terms": ["bkash"],
        "date_from": "2024-12-01",
        "date_to": "2024-12-31"
    }
}
```

### Multi-Turn Clarification

System can ask multiple questions (up to 2) if needed:

```
User: "show transactions"
    ↓
System: "Which account?"
    ↓
User: "savings"
    ↓
System: "Which time period?"
    ↓
User: "last quarter"
    ↓
[Executes with both clarifications]
```

---

## Configuration

### Confidence Threshold

```python
# In ui/services/clarification_manager.py
CONFIDENCE_THRESHOLD = 0.75

# Adjust based on accuracy requirements
# Higher (0.85) = Less clarification, more errors
# Lower (0.65) = More clarification, fewer errors
```

### Max Clarification Attempts

```python
# Maximum times to ask for clarification
MAX_CLARIFICATION_ITERATIONS = 2

# Prevents infinite clarification loops
```

### Model Selection

```python
# In llm/intent_router.py
MODEL_NAME = "gemini-2.5-pro"  # Best quality
# or
MODEL_NAME = "gemini-2.0-flash-exp"  # Faster, cheaper
```

---

## Performance

### Latency

| Operation | Typical Time |
|-----------|--------------|
| Intent classification | 500-2000ms |
| Confidence check | <1ms |
| Re-classification (with context) | 700-1500ms |
| Total (high confidence) | 500-2000ms |
| Total (with clarification) | 1500-4000ms |

### Accuracy

Based on internal testing:
- **High confidence queries** (>75%): 95% accuracy
- **Low confidence queries** (50-75%): 78% accuracy
- **With clarification**: 92% accuracy
- **Overall**: 91% accuracy

### Cost

Per query (Gemini 2.5 Pro):
- Input: ~500-800 tokens (prompt + query)
- Output: ~200-400 tokens (JSON response)
- Cost: ~$0.001-0.003 per query

---

## Troubleshooting

### Issue: All queries have low confidence

**Possible causes**:
- Model needs better examples
- Queries are genuinely ambiguous
- Threshold too high

**Solutions**:
- Add more few-shot examples to prompt
- Lower confidence threshold
- Improve prompt clarity

### Issue: Wrong intent classified

**Possible causes**:
- Ambiguous query
- Missing keywords
- Uncommon phrasing

**Solutions**:
- User clarifies query
- System learns from feedback (future)
- Add examples for specific cases

### Issue: Clarification loop

**Possible causes**:
- Query genuinely unclear
- Model not using context properly
- Re-classification failing

**Solutions**:
- Check MAX_CLARIFICATION_ITERATIONS
- Review conversation context building
- Skip to default search

---

## Best Practices

### For Users

✅ **Be specific**: "Last month" better than "recently"  
✅ **Include dates**: "January 2025" better than "last month"  
✅ **Use keywords**: "total", "sum", "show", "list"  
❌ **Avoid ambiguity**: "some", "a bit", "around"

### For Developers

✅ **Log all classifications**: Track accuracy over time  
✅ **Monitor confidence distribution**: Adjust threshold  
✅ **Collect user feedback**: "Was this helpful?"  
✅ **Test edge cases**: Unusual queries  
❌ **Don't bypass classification**: Tempting but defeats purpose

---

## Testing

### Manual Testing

```bash
# Run intent classifier test
cd /Users/nowshadurrahaman/Projects/Nowshad/fin-sync
python scripts/test_intent_router.py
```

### Unit Tests

```python
def test_aggregate_intent():
    query = "Total spending last month"
    result = classify_intent(query)
    assert result.classification.intent == "aggregate"
    assert result.classification.confidence > 0.75

def test_clarification_needed():
    query = "show transactions"
    result = classify_intent(query)
    assert result.classification.needsClarification == True
```

---

**Related**: [Clarification Flow](./CLARIFICATION_FLOW.md) | [Intent System Architecture](../architecture/INTENT_SYSTEM.md)

