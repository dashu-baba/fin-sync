# API Reference

Key functions and classes in FinSync.

---

## Core Modules

### Configuration

```python
from core.config import config

config.gcp_project_id: str
config.environment: str
config.vertex_model: str
config.elastic_cloud_endpoint: str
```

### Logging

```python
from core.logger import get_logger

log = get_logger("module_name")
log.info("Message", extra={"key": "value"})
```

---

## Elastic Integration

### Client

```python
from elastic.client import es

client = es()  # Singleton
client.search(index="finsync-transactions", query={...})
```

### Indexing

```python
from elastic.indexer import index_parsed_statement

index_parsed_statement(
    parsed=ParsedStatement(...),
    raw_text="...",
    filename="statement.pdf"
)
```

### Search

```python
from elastic.search import hybrid_search, rrf_fusion

results = hybrid_search(query="fees", index="finsync-statements")
fused = rrf_fusion([results1, results2], k=60)
```

---

## LLM Integration

### Intent Classification

```python
from llm.intent_router import classify_intent

result = classify_intent(query="Total spending")
# Returns IntentResponse
```

### Intent Execution

```python
from llm.intent_executor import execute_intent

result = execute_intent(query, intent_response)
# Returns dict with answer, data, citations
```

---

## Models

### ParsedStatement

```python
from models.schema import ParsedStatement

parsed = ParsedStatement(
    accountName="John Doe",
    accountNo="123456",
    statementFrom=date(2025, 1, 1),
    statementTo=date(2025, 1, 31),
    bankName="ABC Bank",
    statements=[...]
)
```

### IntentClassification

```python
from models.intent import IntentClassification

classification = IntentClassification(
    intent="aggregate",
    confidence=0.85,
    filters={...},
    needsClarification=False
)
```

---

**Related**: [Setup](./SETUP.md) | [Testing](./TESTING.md)

