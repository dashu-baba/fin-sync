# LLM Integration (Vertex AI)

Implementation details for Google Vertex AI integration including Gemini and embedding models.

---

## Module Structure

```
llm/
├── intent_router.py    # Intent classification
├── intent_executor.py  # Intent execution orchestration
└── vertex_chat.py      # Chat completion & answer generation
```

---

## Key Components

### 1. Intent Router (`intent_router.py`)

**Purpose**: Classify user intent from natural language queries

**Main Functions**:

```python
def classify_intent(query: str) -> IntentResponse:
    """
    Classify user intent using Gemini.
    
    Args:
        query: User's natural language query
        
    Returns:
        IntentResponse with classification and extracted parameters
    """
    # Initialize Vertex AI
    aiplatform.init(
        project=config.gcp_project_id,
        location=config.gcp_location
    )
    
    # Build prompt
    prompt = INTENT_ROUTER_PROMPT.format(query=query)
    
    # Call Gemini with JSON mode
    model = GenerativeModel(config.vertex_model_genai)
    response = model.generate_content(
        prompt,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.2,  # Low for consistency
            "max_output_tokens": 2048
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

def classify_intent_with_context(
    query: str,
    conversation: list[dict]
) -> IntentResponse:
    """Re-classify with conversation context for clarifications."""
    # Build cumulative query from conversation
    cumulative = query
    for turn in conversation:
        if turn["type"] == "clarification_response":
            cumulative += " " + turn["text"]
    
    # Re-classify
    return classify_intent(cumulative)
```

**Prompt Engineering**:

```python
INTENT_ROUTER_PROMPT = """
You are an intent classifier for financial queries.

Classify the user's query into ONE of these intents:
- aggregate: Calculations (total, sum, average, count)
- aggregate_filtered_by_text: Aggregations with semantic filtering
- text_qa: Answer questions about statement content
- provenance: Show source documents
- trend: Time-series analysis
- listing: List individual transactions

Extract parameters:
- date_from, date_to: Date range (YYYY-MM-DD)
- transaction_type: "credit", "debit", or "all"
- text_terms: Keywords for filtering
- amount_min, amount_max: Amount range
- account_numbers: List of account numbers
- counterparty: Merchant/vendor names

Assess if clarification is needed:
- needsClarification: true if missing critical info
- clarifyQuestion: Specific question to ask user

Return JSON:
{
    "intent": "aggregate",
    "confidence": 0.85,
    "filters": {...},
    "needsClarification": false,
    "clarifyQuestion": null,
    "reasoning": "User wants to calculate total spending"
}

User Query: {query}
"""
```

### 2. Intent Executor (`intent_executor.py`)

**Purpose**: Orchestrate intent execution and route to appropriate handlers

```python
def execute_intent(query: str, intent_response: IntentResponse) -> dict:
    """
    Execute classified intent.
    
    Routes to:
    - _execute_aggregate()
    - _execute_trend()
    - _execute_listing()
    - _execute_text_qa()
    - _execute_aggregate_filtered_by_text()
    - _execute_provenance()
    """
    intent = intent_response.classification.intent
    
    try:
        if intent == "aggregate":
            return _execute_aggregate(query, intent_response.classification)
        elif intent == "text_qa":
            return _execute_text_qa(query, intent_response.classification)
        # ... other intents
    except Exception as e:
        log.exception(f"Error executing intent {intent}")
        return {
            "intent": intent,
            "answer": f"Sorry, I encountered an error: {str(e)}",
            "error": str(e)
        }
```

### 3. Vertex Chat (`vertex_chat.py`)

**Purpose**: Generate natural language answers using Gemini

**Functions**:

```python
def chat_vertex(prompt: str, context: str = None) -> str:
    """
    Generate chat completion with Gemini.
    
    Args:
        prompt: User prompt or question
        context: Optional context to include
        
    Returns:
        Generated text response
    """
    aiplatform.init(
        project=config.gcp_project_id,
        location=config.gcp_location
    )
    
    model = GenerativeModel(config.vertex_model_genai)
    
    full_prompt = prompt
    if context:
        full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
    
    response = model.generate_content(
        full_prompt,
        generation_config={
            "temperature": 0.7,  # Balanced creativity
            "max_output_tokens": 1024
        }
    )
    
    return response.text

def compose_aggregate_answer(
    query: str,
    aggs: dict,
    classification: IntentClassification
) -> str:
    """
    Compose natural language answer for aggregate results.
    
    Example:
        Input: {"total": 3245.67, "count": 47, "avg": 69.06}
        Output: "You spent $3,245.67 across 47 transactions, 
                 averaging $69.06 per transaction."
    """
    prompt = f"""
Given this financial data:
- Total: ${aggs['total']:.2f}
- Count: {aggs['count']} transactions
- Average: ${aggs['avg']:.2f}

Original question: {query}

Write a concise, friendly answer (2-3 sentences).
"""
    
    return chat_vertex(prompt)

def compose_text_qa_answer(
    query: str,
    context: list[dict],
    citations: list[dict]
) -> str:
    """
    Compose answer for text QA with citations.
    
    Includes source citations at the end.
    """
    # Build context from search results
    context_text = "\n\n".join([
        f"[Source {i+1}]: {doc['rawText'][:500]}"
        for i, doc in enumerate(context[:5])
    ])
    
    # Generate answer
    answer = chat_vertex(query, context=context_text)
    
    # Append citations
    citations_text = "\n\n**Sources:**\n" + "\n".join([
        f"{i+1}. {c['account']} - {c['bank']} ({c['period']})"
        for i, c in enumerate(citations[:3])
    ])
    
    return answer + citations_text
```

---

## Model Selection

### Gemini Models

| Model | Use Case | Cost | Latency |
|-------|----------|------|---------|
| `gemini-2.5-pro` | Complex parsing, high-quality chat | $$$ | Medium |
| `gemini-2.0-flash-exp` | Fast classification, simple tasks | $ | Fast |
| `gemini-1.5-flash` | Legacy, budget option | $ | Fast |

**Configuration**:
```python
# core/config.py
vertex_model = "gemini-2.5-pro"         # Document parsing
vertex_model_genai = "gemini-2.5-pro"   # Chat & classification
```

### Embedding Model

```python
from vertexai.language_models import TextEmbeddingModel

def generate_embedding(text: str) -> list[float]:
    """Generate 768-dim embedding with text-embedding-004."""
    model = TextEmbeddingModel.from_pretrained("text-embedding-004")
    embeddings = model.get_embeddings([text])
    return embeddings[0].values  # 768-dimensional vector
```

---

## Prompt Engineering Best Practices

### Structure

```python
PROMPT_TEMPLATE = """
[ROLE DEFINITION]
You are a <role> that <purpose>.

[TASK DESCRIPTION]
<Clear description of what to do>

[OUTPUT FORMAT]
Return JSON:
{
    "field1": "...",
    "field2": 0.0
}

[EXAMPLES] (optional)
Example 1:
Input: ...
Output: {...}

[CONSTRAINTS]
- Constraint 1
- Constraint 2

[USER INPUT]
{user_input}
"""
```

### Tips

✅ **Be specific**: "Return JSON" > "Format your response"  
✅ **Use examples**: Few-shot learning improves accuracy  
✅ **Set temperature**: 0.1-0.3 for structured, 0.7-0.9 for creative  
✅ **Use JSON mode**: `response_mime_type: "application/json"`  
❌ **Don't be vague**: Unclear prompts = inconsistent results

---

## Cost Optimization

### Token Usage

**Typical Request**:
- Intent classification: ~500 input + ~300 output = ~800 tokens
- Answer generation: ~1000 input + ~500 output = ~1500 tokens
- Document parsing: ~3000 input + ~2000 output = ~5000 tokens

**Costs** (Gemini 2.5 Pro):
- Input: $0.00125 per 1K tokens
- Output: $0.005 per 1K tokens

**Per Query**:
- Intent: ~$0.002
- Answer: ~$0.004
- Parse: ~$0.015

### Optimization Strategies

1. **Cache frequent queries**
```python
@lru_cache(maxsize=100)
def classify_intent_cached(query: str):
    return classify_intent(query)
```

2. **Use cheaper model for simple tasks**
```python
# Use flash for classification
model = "gemini-2.0-flash-exp"  # vs gemini-2.5-pro
```

3. **Batch embeddings**
```python
# Generate multiple embeddings in one call
embeddings = model.get_embeddings([text1, text2, text3])
```

---

## Error Handling

```python
from google.api_core import exceptions

try:
    response = model.generate_content(prompt)
except exceptions.ResourceExhausted:
    log.error("Quota exceeded")
    # Fallback or retry with backoff
except exceptions.InvalidArgument as e:
    log.error(f"Invalid prompt: {e}")
    # Fix prompt and retry
except Exception as e:
    log.exception("Unexpected error")
    # Generic fallback
```

---

## Testing

```python
def test_intent_classification():
    """Test intent router."""
    query = "Total spending last month"
    result = classify_intent(query)
    
    assert result.classification.intent == "aggregate"
    assert result.classification.confidence > 0.7

def test_answer_generation():
    """Test answer composition."""
    query = "How much did I spend?"
    aggs = {"total": 1234.56, "count": 10}
    answer = compose_aggregate_answer(query, aggs, None)
    
    assert "1234.56" in answer or "1,234.56" in answer
    assert "10" in answer
```

---

## Monitoring

### Metrics to Track

```python
# Latency
vertex_ai_latency = Histogram("vertex_ai_latency_seconds")
with vertex_ai_latency.time():
    response = model.generate_content(prompt)

# Token usage
vertex_ai_tokens_input.inc(count_tokens(prompt))
vertex_ai_tokens_output.inc(count_tokens(response.text))

# Error rate
vertex_ai_errors.inc()
```

---

**Related**: [Intent System](../architecture/INTENT_SYSTEM.md) | [Intent Classification](../features/INTENT_CLASSIFICATION.md)

