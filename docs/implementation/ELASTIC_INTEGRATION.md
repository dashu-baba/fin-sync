# Elastic Cloud Integration

Complete guide to Elasticsearch integration in FinSync including indexing, search, and analytics.

---

## Module Structure

```
elastic/
├── client.py           # Elasticsearch client singleton
├── indexer.py          # Document indexing
├── mappings.py         # Index mappings & schemas
├── embedding.py        # Vertex AI embeddings
├── search.py           # Hybrid search
├── query_builders.py   # ES|QL query construction
├── executors.py        # Intent query executors
├── analytics.py        # Analytics queries
└── prompts.py          # LLM prompts for search
```

---

## Key Modules

### 1. Client (`client.py`)

**Singleton Elasticsearch client**:

```python
from elasticsearch import Elasticsearch

_es_client = None

def es() -> Elasticsearch:
    """Get singleton Elasticsearch client."""
    global _es_client
    if _es_client is None:
        from core.config import config
        _es_client = Elasticsearch(
            config.elastic_cloud_endpoint,
            api_key=config.elastic_api_key,
            request_timeout=30
        )
    return _es_client
```

**Usage**:
```python
from elastic.client import es

client = es()
result = client.search(index="finsync-transactions", query={...})
```

### 2. Indexing (`indexer.py`)

**Core functions**:
- `index_parsed_statement()` - Index complete statement
- `bulk_index_transactions()` - Batch index transactions
- `create_indices()` - Set up indices with mappings

**Example**:
```python
from elastic.indexer import index_parsed_statement

index_parsed_statement(
    parsed=parsed_statement,  # ParsedStatement object
    raw_text=pdf_text,
    filename="statement.pdf"
)
```

### 3. Mappings (`mappings.py`)

**Transaction Index**:
```python
mapping_transactions = {
    "properties": {
        "accountNo": {"type": "keyword"},
        "statementDate": {"type": "date"},
        "statementAmount": {"type": "double"},
        "statementType": {"type": "keyword"},
        "statementDescription": {"type": "text"},
        "statementBalance": {"type": "double"},
        "bankName": {"type": "keyword"}
    }
}
```

**Statement Index** (with vector):
```python
mapping_statements = {
    "properties": {
        "accountNo": {"type": "keyword"},
        "statementFrom": {"type": "date"},
        "statementTo": {"type": "date"},
        "bankName": {"type": "keyword"},
        "rawText": {"type": "text"},
        "desc_vector": {
            "type": "dense_vector",
            "dims": 768,
            "index": True,
            "similarity": "cosine"
        }
    }
}
```

### 4. Query Builders (`query_builders.py`)

**ES|QL Query Construction**:

```python
def q_aggregate(filters: IntentFilters) -> str:
    """Build aggregate ES|QL query."""
    query = "FROM finsync-transactions"
    
    # Add filters
    where_clauses = []
    if filters.date_from:
        where_clauses.append(f"statementDate >= '{filters.date_from}'")
    if filters.transaction_type != "all":
        where_clauses.append(f"statementType == '{filters.transaction_type}'")
    
    if where_clauses:
        query += f" | WHERE {' AND '.join(where_clauses)}"
    
    # Aggregations
    query += """
    | STATS 
        total = SUM(statementAmount),
        count = COUNT(*),
        avg = AVG(statementAmount)
    """
    
    return query

def q_hybrid(text_terms: list[str]) -> dict:
    """Build hybrid search query (BM25 + kNN)."""
    return {
        "query": {"match": {"rawText": " ".join(text_terms)}},
        "knn": {
            "field": "desc_vector",
            "query_vector": generate_embedding(" ".join(text_terms)),
            "k": 10,
            "num_candidates": 50
        }
    }
```

### 5. Executors (`executors.py`)

**Intent Execution**:

```python
def execute_aggregate(classification: IntentClassification) -> dict:
    """Execute aggregate intent."""
    # Build query
    query = q_aggregate(classification.filters)
    
    # Execute
    result = es().esql.query(query=query)
    
    # Parse results
    return {
        "total": result['values'][0][0],
        "count": result['values'][0][1],
        "avg": result['values'][0][2]
    }

def execute_text_qa(classification: IntentClassification) -> dict:
    """Execute text QA with hybrid search + RRF."""
    # Keyword search
    kw_results = es().search(
        index="finsync-statements",
        query={"match": {"rawText": " ".join(classification.filters.text_terms)}}
    )
    
    # Vector search
    embedding = generate_embedding(" ".join(classification.filters.text_terms))
    vec_results = es().search(
        index="finsync-statements",
        knn={"field": "desc_vector", "query_vector": embedding, "k": 10}
    )
    
    # RRF fusion
    fused = rrf_fusion([kw_results['hits']['hits'], vec_results['hits']['hits']])
    
    return {"results": fused}
```

### 6. Hybrid Search (`search.py`)

**RRF Fusion**:

```python
def rrf_fusion(
    results_list: list[list[dict]],
    k: int = 60
) -> list[dict]:
    """Reciprocal Rank Fusion."""
    from collections import defaultdict
    
    doc_scores = defaultdict(float)
    doc_data = {}
    
    for results in results_list:
        for rank, doc in enumerate(results, start=1):
            doc_id = doc["_id"]
            doc_scores[doc_id] += 1.0 / (k + rank)
            doc_data[doc_id] = doc
    
    sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    
    return [{**doc_data[doc_id], "_score": score} for doc_id, score in sorted_docs]
```

---

## Index Strategy

### Two-Index Approach

**Why Two Indices?**
1. **Transactions** - Optimized for aggregations (ES|QL)
2. **Statements** - Optimized for semantic search (vectors)

### Data Flow

```
PDF → Parse → 
  ├─ Individual transactions → finsync-transactions (flat)
  └─ Statement with vector → finsync-statements (nested)
```

### Index Lifecycle

```
1. Create indices on first run
2. Bulk index transactions
3. Index statement with vector
4. Refresh for immediate search
5. (Future) Rollover for time-series data
```

---

## Query Patterns

### 1. Aggregation (ES|QL)

```sql
FROM finsync-transactions
| WHERE statementDate >= '2025-01-01'
| STATS total = SUM(statementAmount) BY statementType
```

### 2. Hybrid Search (BM25 + kNN)

```python
{
    "query": {"match": {"rawText": "fees"}},
    "knn": {
        "field": "desc_vector",
        "query_vector": [...],
        "k": 10
    }
}
```

### 3. Filtered Aggregation

```sql
FROM finsync-transactions
| WHERE statementDescription LIKE "Walmart"
| STATS total = SUM(statementAmount)
```

---

## Performance Optimization

### Best Practices

✅ **Use ES|QL for aggregations** - 10x faster than Python  
✅ **Batch indexing** - Use bulk() for multiple documents  
✅ **Limit kNN candidates** - Balance recall vs speed  
✅ **Filter before kNN** - Reduce search space  
❌ **Don't fetch all documents** - Use pagination or aggregations

### Benchmarks

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Single document index | 10-30ms | 100-300 docs/sec |
| Bulk index (100 docs) | 200-500ms | 5000+ docs/sec |
| ES\|QL aggregation | 20-100ms | - |
| kNN search (k=10) | 30-80ms | - |
| Hybrid search + RRF | 50-150ms | - |

---

## Error Handling

```python
from elasticsearch.exceptions import ElasticsearchException

try:
    result = es().search(index="finsync-transactions", query=query)
except ElasticsearchException as e:
    log.error(f"Elastic query failed: {e}", exc_info=True)
    return {"error": "Search service unavailable"}
```

---

## Testing

```python
# Test client connection
def test_elastic_connection():
    from elastic.client import es
    assert es().ping() == True

# Test indexing
def test_index_document():
    from elastic.indexer import index_parsed_statement
    result = index_parsed_statement(test_data)
    assert result["_id"] is not None

# Test search
def test_hybrid_search():
    from elastic.search import hybrid_search
    results = hybrid_search("test query")
    assert len(results) > 0
```

---

**Related**: [Hybrid Search](../features/HYBRID_SEARCH.md) | [Analytics](../features/ANALYTICS.md)

