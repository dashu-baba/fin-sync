# Intent Classification System Architecture

The Intent System is the intelligence layer that understands user queries and routes them to appropriate execution strategies.

---

## Overview

The Intent System bridges natural language and structured queries through:
1. **Classification**: Understanding user intent
2. **Parameter Extraction**: Extracting filters and constraints
3. **Confidence Assessment**: Determining certainty
4. **Clarification**: Interactive refinement when unclear
5. **Execution**: Routing to specialized handlers

---

## Intent Taxonomy

### Supported Intents

| Intent | Category | Data Source | Query Type | Example |
|--------|----------|-------------|------------|---------|
| **aggregate** | Structured | Transactions | ES\|QL Aggregation | "Total spending in Q1" |
| **aggregate_filtered_by_text** | Hybrid | Statements → Transactions | Semantic + ES\|QL | "Spending on groceries" |
| **text_qa** | Unstructured | Statements | Hybrid Search + LLM | "What fees are mentioned?" |
| **provenance** | Unstructured | Statements | Hybrid Search | "Show sources about overdraft" |
| **trend** | Structured | Transactions | Date Histogram | "Monthly spending trend" |
| **listing** | Structured | Transactions | Standard Query | "Last 10 transactions" |

### Intent Decision Tree

```
User Query
    ↓
[Contains semantic question?]
    Yes → Is it asking about sources?
        Yes → provenance
        No → Needs aggregation?
            Yes → aggregate_filtered_by_text
            No → text_qa
    No → Wants aggregation/calculation?
        Yes → Over time?
            Yes → trend
            No → aggregate
        No → Wants transaction list?
            Yes → listing
            No → [Default: text_qa]
```

---

## Classification Architecture

### Model & Prompt

**Model**: `gemini-2.5-pro`  
**Mode**: JSON output with structured schema  
**Temperature**: 0.2 (deterministic)

**Prompt Structure**:
```
System:
You are an intent classifier for financial queries.
Classify into one of: [list of intents]
Extract parameters: dates, amounts, account numbers, text terms.
Output JSON: {intent, confidence, filters, needsClarification, ...}

User Query:
{query}

Examples:
[Few-shot examples for each intent]

Output:
{JSON}
```

### Classification Response Schema

```python
class IntentClassification(BaseModel):
    intent: Literal[
        "aggregate",
        "aggregate_filtered_by_text",
        "text_qa",
        "provenance",
        "trend",
        "listing"
    ]
    confidence: float  # 0.0 - 1.0
    filters: IntentFilters
    needsClarification: bool
    clarifyQuestion: str | None
    reasoning: str  # Why this intent was chosen

class IntentFilters(BaseModel):
    date_from: str | None
    date_to: str | None
    account_numbers: list[str]
    amount_min: float | None
    amount_max: float | None
    transaction_type: Literal["credit", "debit", "all"] | None
    counterparty: list[str]
    text_terms: list[str]
```

### Classification Logic

```python
def classify_intent(query: str, context: list = None) -> IntentResponse:
    """
    Classify user intent from query.
    
    Args:
        query: User's natural language query
        context: Optional conversation history
        
    Returns:
        IntentResponse with classification and parameters
    """
    # Build prompt
    prompt = build_classification_prompt(query, context)
    
    # Call Gemini
    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2
        }
    )
    
    # Parse and validate
    data = json.loads(response.text)
    classification = IntentClassification(**data)
    
    return IntentResponse(
        classification=classification,
        raw_response=response.text,
        processing_time_ms=elapsed
    )
```

---

## Confidence Thresholds

### Decision Logic

```python
if classification.confidence > 0.75 and not classification.needsClarification:
    # High confidence → Execute immediately
    execute_intent(query, classification)
    
elif classification.confidence <= 0.75 and not classification.needsClarification:
    # Low confidence → Ask for confirmation
    show_confirmation_dialog(
        "I understood: {interpretation}. Is this correct?"
    )
    
elif classification.needsClarification:
    # Needs info → Ask specific question
    show_clarification_dialog(
        classification.clarifyQuestion
    )
```

### Confidence Factors

| Factor | Impact on Confidence |
|--------|---------------------|
| **Explicit dates** | +15% |
| **Specific account mentioned** | +10% |
| **Clear aggregation words** (sum, total) | +20% |
| **Ambiguous terms** (recent, some) | -25% |
| **Multiple possible intents** | -30% |

---

## Intent Execution Strategies

### 1. aggregate

**Strategy**: Direct ES|QL aggregation on transactions index

```python
def execute_aggregate(classification: IntentClassification) -> dict:
    # Build ES|QL query
    query = f"""
    FROM finsync-transactions
    | WHERE statementDate >= '{filters.date_from}'
      AND statementDate <= '{filters.date_to}'
    """
    
    if filters.transaction_type != "all":
        query += f"| WHERE statementType == '{filters.transaction_type}'"
    
    query += """
    | STATS 
        total = SUM(statementAmount),
        count = COUNT(*),
        avg = AVG(statementAmount),
        max = MAX(statementAmount),
        min = MIN(statementAmount)
    """
    
    # Execute
    result = es_client.esql.query(query=query)
    return parse_aggregation_result(result)
```

### 2. aggregate_filtered_by_text

**Strategy**: Two-step (semantic search → aggregation)

```python
def execute_aggregate_filtered_by_text(
    classification: IntentClassification
) -> dict:
    # Step 1: Find relevant statements semantically
    text_results = execute_text_qa(classification)
    
    # Step 2: Extract merchant/counterparty terms
    merchants = extract_merchants_from_results(text_results)
    
    # Step 3: Aggregate transactions matching those terms
    filters = classification.filters.copy()
    filters.counterparty = merchants
    
    agg_results = execute_aggregate(filters)
    
    # Step 4: Combine results
    return {
        "aggregations": agg_results,
        "semantic_context": text_results,
        "derived_filters": merchants
    }
```

### 3. text_qa

**Strategy**: Hybrid search (BM25 + kNN) + RRF fusion + LLM answer

```python
def execute_text_qa(classification: IntentClassification) -> dict:
    # Build keyword query (BM25)
    keyword_query = {
        "query": {
            "match": {
                "rawText": {
                    "query": " ".join(classification.filters.text_terms)
                }
            }
        }
    }
    
    # Build vector query (kNN)
    query_embedding = generate_embedding(classification.query)
    vector_query = {
        "knn": {
            "field": "desc_vector",
            "query_vector": query_embedding,
            "k": 10,
            "num_candidates": 50
        }
    }
    
    # Execute both
    keyword_results = es_client.search(
        index="finsync-statements",
        body=keyword_query
    )
    
    vector_results = es_client.search(
        index="finsync-statements",
        knn=vector_query["knn"]
    )
    
    # RRF Fusion
    fused_results = rrf_fusion(
        [keyword_results, vector_results],
        k=60
    )
    
    # Generate answer with Gemini
    context = "\n\n".join([
        f"[Source {i+1}]: {doc['rawText']}"
        for i, doc in enumerate(fused_results[:5])
    ])
    
    answer = chat_vertex(
        f"Answer this question based on context:\n\nQuestion: {query}\n\nContext:\n{context}"
    )
    
    return {
        "answer": answer,
        "sources": fused_results[:5],
        "provenance": extract_provenance(fused_results)
    }
```

### 4. provenance

**Strategy**: Reuse text_qa but return sources directly

```python
def execute_provenance(classification: IntentClassification) -> dict:
    # Reuse text_qa search
    results = execute_text_qa(classification)
    
    # Format as source list
    sources = []
    for i, doc in enumerate(results["sources"]):
        sources.append({
            "id": i + 1,
            "account": doc["accountName"],
            "bank": doc["bankName"],
            "period": f"{doc['statementFrom']} to {doc['statementTo']}",
            "relevance_score": doc["_score"],
            "preview": doc["rawText"][:200] + "..."
        })
    
    return {"sources": sources}
```

### 5. trend

**Strategy**: Date histogram aggregation

```python
def execute_trend(classification: IntentClassification) -> dict:
    query = f"""
    FROM finsync-transactions
    | WHERE statementDate >= '{filters.date_from}'
      AND statementDate <= '{filters.date_to}'
    | EVAL month = DATE_FORMAT(statementDate, 'yyyy-MM')
    | STATS 
        income = SUM(CASE(statementType == 'credit', statementAmount, 0)),
        expense = SUM(CASE(statementType == 'debit', statementAmount, 0)),
        count = COUNT(*)
      BY month
    | SORT month ASC
    """
    
    result = es_client.esql.query(query=query)
    return parse_trend_result(result)
```

### 6. listing

**Strategy**: Standard query with sorting

```python
def execute_listing(classification: IntentClassification) -> dict:
    query = {
        "query": {"bool": {"must": build_filters(classification.filters)}},
        "sort": [{"statementDate": "desc"}],
        "size": classification.filters.limit or 10
    }
    
    result = es_client.search(
        index="finsync-transactions",
        body=query
    )
    
    return {
        "transactions": [hit["_source"] for hit in result["hits"]["hits"]]
    }
```

---

## Clarification Flow

### State Machine

```
┌─────────────┐
│    IDLE     │
└──────┬──────┘
       │ User query
       ▼
┌─────────────┐
│ CLASSIFYING │
└──────┬──────┘
       │
       ├─ Confidence > 0.75 & !needsClarification
       │  → EXECUTING
       │
       ├─ Confidence ≤ 0.75 & !needsClarification
       │  → AWAITING_CONFIRMATION
       │
       └─ needsClarification
          → AWAITING_CLARIFICATION
          
┌──────────────────────┐
│ AWAITING_CONFIRMATION│
└──────┬───────────────┘
       │
       ├─ User confirms → EXECUTING
       └─ User rejects → IDLE
       
┌───────────────────────┐
│ AWAITING_CLARIFICATION│
└──────┬────────────────┘
       │
       ├─ User provides info → RECLASSIFYING
       └─ User skips → EXECUTING (with original query)
       
┌───────────────┐
│ RECLASSIFYING │
└──────┬────────┘
       │
       ├─ Clear now → EXECUTING
       └─ Still unclear → AWAITING_CLARIFICATION (max 2 times)
```

### Context-Aware Re-classification

```python
def classify_intent_with_context(
    query: str,
    conversation: list[dict]
) -> IntentResponse:
    """
    Re-classify with full conversation context.
    
    Example:
        Initial: "bkash transactions"
        Clarification: "Which time period?" → "last month"
        Context: [
            {"type": "query", "text": "bkash transactions"},
            {"type": "clarification_response", "text": "last month"}
        ]
        Cumulative query: "bkash transactions last month"
    """
    # Build cumulative query
    cumulative = query
    for turn in conversation:
        if turn["type"] == "clarification_response":
            cumulative += " " + turn["text"]
    
    # Re-classify with context
    prompt = f"""
    Original query: {query}
    
    Conversation history:
    {format_conversation(conversation)}
    
    Enhanced query: {cumulative}
    
    Classify the enhanced query considering all context.
    """
    
    return classify_intent(cumulative, context=conversation)
```

---

## Performance Optimization

### Caching Strategy

```python
@lru_cache(maxsize=128)
def classify_intent_cached(query: str) -> IntentResponse:
    """Cache classifications for identical queries."""
    return classify_intent(query)
```

### Parallel Execution

```python
async def execute_with_timeout(
    classification: IntentClassification,
    timeout: int = 30
) -> dict:
    """Execute intent with timeout."""
    return await asyncio.wait_for(
        execute_intent_async(classification),
        timeout=timeout
    )
```

---

## Error Handling

### Fallback Strategy

```python
def execute_intent_with_fallback(
    query: str,
    classification: IntentResponse
) -> dict:
    try:
        # Primary: Intent-based execution
        return execute_intent(query, classification)
    except IntentExecutionError as e:
        log.warning(f"Intent execution failed: {e}")
        # Fallback: Direct text_qa
        return execute_text_qa_fallback(query)
    except Exception as e:
        log.exception("Unexpected error")
        return {
            "error": "An error occurred. Please try rephrasing your query."
        }
```

---

## Monitoring & Metrics

### Key Metrics

```python
# Track intent distribution
intent_counter = Counter()
intent_counter[classification.intent] += 1

# Track confidence distribution
confidence_histogram = Histogram(buckets=[0.0, 0.5, 0.75, 0.9, 1.0])
confidence_histogram.observe(classification.confidence)

# Track clarification rate
clarification_rate = clarifications / total_queries

# Track intent accuracy (requires user feedback)
accuracy = correct_intents / labeled_queries
```

### Logging

```python
log.info(
    "Intent classified",
    extra={
        "query": query,
        "intent": classification.intent,
        "confidence": classification.confidence,
        "processing_time_ms": elapsed,
        "needs_clarification": classification.needsClarification
    }
)
```

---

## Testing Strategy

### Unit Tests

```python
def test_aggregate_intent():
    query = "Total spending last month"
    result = classify_intent(query)
    assert result.classification.intent == "aggregate"
    assert result.classification.confidence > 0.75

def test_text_qa_intent():
    query = "What fees are mentioned in my statement?"
    result = classify_intent(query)
    assert result.classification.intent == "text_qa"
```

### Integration Tests

```python
def test_end_to_end_aggregate():
    query = "How much did I spend in January 2025?"
    
    # Classify
    classification = classify_intent(query)
    
    # Execute
    result = execute_intent(query, classification)
    
    # Verify
    assert "total" in result["aggregations"]
    assert result["aggregations"]["count"] > 0
```

---

## Future Enhancements

1. **Multi-Intent Queries**: Handle queries with multiple intents
2. **Learning from Feedback**: Improve classification based on user corrections
3. **Custom Intents**: Allow user-defined intent types
4. **Slot Filling**: Interactive parameter extraction
5. **Voice Queries**: Support speech-to-text input

---

**Related**: [System Overview](./OVERVIEW.md) | [Clarification Flow](../features/CLARIFICATION_FLOW.md)

