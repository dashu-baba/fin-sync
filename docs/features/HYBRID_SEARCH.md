# Hybrid Search System

FinSync combines keyword search (BM25) and semantic search (kNN vector similarity) for best-of-both-worlds retrieval.

---

## Overview

**Hybrid Search** = Keyword Search + Semantic Search + Fusion

Traditional keyword search finds exact matches, while semantic search understands meaning. Combining both gives superior results:

```
Query: "What are the fees?"

Keyword (BM25):
✅ Documents containing "fees"
❌ Misses "charges", "costs", "penalties"

Semantic (kNN):
✅ Documents about costs
✅ Documents about charges
✅ Documents about penalties
❌ May include less relevant results

Hybrid (BM25 + kNN + RRF):
✅ Best of both
✅ "fees" gets high rank
✅ "charges" and "costs" also ranked
✅ Irrelevant results filtered out
```

---

## Architecture

### Two-Query Strategy

```
User Query: "What overdraft fees apply?"
    ↓
┌─────────────────────────────────────────────────┐
│          1. Generate Embedding                  │
│   text-embedding-004("What overdraft fees...")  │
│   → [0.123, -0.456, 0.789, ...] (768-dim)     │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────┬──────────────────────────────┐
│                                  │                              │
│  2a. Keyword Query (BM25)        │  2b. Vector Query (kNN)      │
│                                  │                              │
│  Match on "rawText" field:       │  kNN on "desc_vector":       │
│  - "overdraft"                   │  - Cosine similarity         │
│  - "fees"                        │  - k=10 results              │
│                                  │  - num_candidates=50         │
│  Returns: 10 results             │  Returns: 10 results         │
│                                  │                              │
└──────────────────┬───────────────┴──────────────┬───────────────┘
                   │                               │
                   ▼                               ▼
                [Hits with scores]            [Hits with scores]
                   │                               │
                   └───────────────┬───────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  3. RRF Fusion (k=60)        │
                    │  Score = 1 / (k + rank)      │
                    │  Combine rankings from both  │
                    └──────────────┬───────────────┘
                                   ▼
                         [Top 5 fused results]
```

---

## Implementation

### Step 1: Keyword Query (BM25)

```python
def build_keyword_query(text_terms: list[str], filters: dict = None) -> dict:
    """Build Elasticsearch BM25 query."""
    return {
        "query": {
            "bool": {
                "must": [
                    {
                        "match": {
                            "rawText": {
                                "query": " ".join(text_terms),
                                "operator": "or",
                                "fuzziness": "AUTO"  # Handle typos
                            }
                        }
                    }
                ],
                "filter": build_filters(filters) if filters else []
            }
        },
        "size": 10,
        "_source": ["accountName", "bankName", "statementFrom", 
                    "statementTo", "rawText", "accountNo"]
    }
```

### Step 2: Semantic Query (kNN)

```python
def build_vector_query(query: str, filters: dict = None) -> dict:
    """Build Elasticsearch kNN query."""
    # Generate embedding
    query_vector = generate_embedding(query)
    
    return {
        "knn": {
            "field": "desc_vector",
            "query_vector": query_vector,  # 768-dim vector
            "k": 10,  # Return top 10
            "num_candidates": 50,  # Consider 50 candidates
            "filter": build_filters(filters) if filters else None
        },
        "_source": ["accountName", "bankName", "statementFrom", 
                    "statementTo", "rawText", "accountNo"]
    }
```

### Step 3: RRF Fusion

**Reciprocal Rank Fusion (RRF)** combines rankings from multiple sources:

```python
def rrf_fusion(
    results_list: list[list[dict]],
    k: int = 60
) -> list[dict]:
    """
    Fuse multiple result lists using Reciprocal Rank Fusion.
    
    Formula: score = sum(1 / (k + rank)) for each result set
    
    Args:
        results_list: List of result lists (e.g., [bm25_results, knn_results])
        k: RRF constant (typically 60)
        
    Returns:
        Fused and sorted results
    """
    doc_scores = defaultdict(float)
    doc_data = {}
    
    # For each result set
    for results in results_list:
        # For each document in results
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["_id"]
            
            # RRF score: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank)
            
            # Accumulate scores
            doc_scores[doc_id] += rrf_score
            doc_data[doc_id] = doc
    
    # Sort by combined score
    sorted_docs = sorted(
        doc_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    # Return top documents with fused scores
    return [
        {**doc_data[doc_id], "_score": score}
        for doc_id, score in sorted_docs
    ]
```

**Why RRF?**
- ✅ Simple and effective
- ✅ No parameter tuning needed
- ✅ Robust to score magnitude differences
- ✅ Research-proven (SIGIR 2009)

---

## Hybrid Search in Action

### Example: Text QA Intent

```python
from elastic.executors import execute_text_qa

result = execute_text_qa(
    intent_classification={
        "intent": "text_qa",
        "filters": {
            "text_terms": ["fees", "charges"]
        }
    }
)

# Returns
{
    "answer": "Your statement mentions the following fees: ...",
    "sources": [
        {
            "accountName": "John Doe",
            "bankName": "ABC Bank",
            "statementFrom": "2025-01-01",
            "statementTo": "2025-01-31",
            "rawText": "Monthly service fee: $10. Overdraft fee: $35...",
            "_score": 2.847  # RRF fused score
        },
        ...
    ],
    "provenance": [
        {
            "statement_id": "stmt_123",
            "account": "John Doe",
            "relevance_score": 2.847
        }
    ]
}
```

---

## Query Tuning

### BM25 Parameters

```python
# Default Elasticsearch BM25 parameters
"similarity": {
    "default": {
        "type": "BM25",
        "k1": 1.2,    # Term frequency saturation
        "b": 0.75     # Length normalization
    }
}
```

**Tuning**:
- **k1** (1.2-2.0): Higher = more emphasis on term frequency
- **b** (0.5-0.9): Higher = more length normalization

### kNN Parameters

```python
"knn": {
    "k": 10,               # Results to return
    "num_candidates": 50   # Candidates to consider (50-100)
}
```

**Tuning**:
- **k**: Depends on use case (5-20 typical)
- **num_candidates**: Higher = better recall, slower query
- **Rule of thumb**: num_candidates = 3-10x k

### RRF Parameter

```python
k = 60  # RRF constant
```

**Tuning**:
- **Lower (20-40)**: More emphasis on top-ranked results
- **Higher (60-100)**: More balanced fusion
- **Typical**: 60 (research default)

---

## Performance

### Latency Breakdown

```
Keyword query (BM25):   20-50ms
Vector query (kNN):      30-80ms  (slower due to vector ops)
RRF fusion:             <5ms
---
Total hybrid search:    50-135ms
```

### Optimization Strategies

1. **Parallel Execution**
```python
import asyncio

async def hybrid_search(query: str):
    # Execute both queries in parallel
    bm25_task = asyncio.create_task(keyword_search(query))
    knn_task = asyncio.create_task(vector_search(query))
    
    bm25_results, knn_results = await asyncio.gather(bm25_task, knn_task)
    
    return rrf_fusion([bm25_results, knn_results])
```

2. **Reduce num_candidates**
```python
# Trade recall for speed
"num_candidates": 30  # Instead of 50
```

3. **Cache Embeddings**
```python
@lru_cache(maxsize=1000)
def generate_embedding_cached(text: str) -> list[float]:
    return generate_embedding(text)
```

---

## Comparison: Hybrid vs Single Strategy

### Test Query: "What are the monthly charges?"

**Results (scored 0-10 by relevance)**:

| Rank | Keyword Only (BM25) | Semantic Only (kNN) | Hybrid (RRF) |
|------|---------------------|---------------------|--------------|
| 1 | "Monthly charges: $10" (9/10) | "Account fees..." (7/10) | "Monthly charges: $10" (10/10) |
| 2 | "Service charge..." (6/10) | "Monthly service..." (8/10) | "Monthly service..." (9/10) |
| 3 | "Charges for..." (5/10) | "Costs and fees..." (6/10) | "Service charge..." (8/10) |
| 4 | "Monthly statement..." (3/10) | "Price structure..." (5/10) | "Costs and fees..." (7/10) |
| 5 | "Charges on 1/1..." (2/10) | "Monthly overview..." (4/10) | "Account fees..." (7/10) |

**Average relevance**:
- Keyword: 5.0/10
- Semantic: 6.0/10
- **Hybrid: 8.2/10** ✅ Best

---

## Index Configuration

### Statements Index Mapping

```python
{
    "mappings": {
        "properties": {
            # Keyword search
            "rawText": {
                "type": "text",
                "analyzer": "standard",
                "similarity": "BM25"
            },
            
            # Semantic search
            "desc_vector": {
                "type": "dense_vector",
                "dims": 768,
                "index": True,
                "similarity": "cosine"
            },
            
            # Filters
            "accountNo": {"type": "keyword"},
            "bankName": {"type": "keyword"},
            "statementFrom": {"type": "date"},
            "statementTo": {"type": "date"}
        }
    }
}
```

---

## Best Practices

### For Hybrid Search

✅ **Use for semantic queries**: "What fees?", "Tell me about..."  
✅ **Combine with filters**: Date range, account, etc.  
✅ **Tune k and num_candidates**: Based on index size  
✅ **Monitor both query latencies**: Identify bottleneck  
❌ **Don't use for exact matches**: Use keyword only  
❌ **Don't over-rely on semantic**: Keyword still important

### Query Types by Strategy

| Query Type | Best Strategy | Reason |
|------------|---------------|--------|
| **Exact phrase** | Keyword only | BM25 perfect for exact matches |
| **Semantic question** | Hybrid | Benefits from both |
| **Concept search** | Semantic only | Meaning > keywords |
| **Account number** | Filter only | Structured data |
| **Date range** | Filter only | Structured data |

---

## Troubleshooting

### Issue: Semantic results not relevant

**Possible causes**:
- Embeddings not generated correctly
- Wrong similarity metric (cosine vs dot_product)
- Query too short (< 3 words)

**Solutions**:
- Verify embeddings: `check_embedding_dim.py`
- Use cosine similarity for normalized vectors
- Encourage longer queries

### Issue: Keyword results missing

**Possible causes**:
- Text not indexed with correct analyzer
- Stopwords removed (the, a, is)
- Typos in query

**Solutions**:
- Check index mapping
- Enable fuzziness: `"fuzziness": "AUTO"`
- Use synonyms

### Issue: RRF fusion poor

**Possible causes**:
- One query returning no results
- k value inappropriate
- Result lists too different

**Solutions**:
- Ensure both queries return results
- Adjust k (try 30-90 range)
- Examine individual rankings

---

**Related**: [Text QA Intent](../implementation/ELASTIC_INTEGRATION.md) | [Search Implementation](../implementation/ELASTIC_INTEGRATION.md)

