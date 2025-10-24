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

## Upload Services

### UploadService

```python
from ui.services import UploadService

# Check for duplicate by filename
exists = UploadService.check_duplicate_by_name("statement.pdf")

# Check for duplicate by content hash
file_content = file.getvalue()
is_duplicate, existing_filename = UploadService.check_duplicate_by_hash(file_content)

# Check for duplicate statement in Elasticsearch
is_duplicate, existing_file = UploadService.check_duplicate_in_elasticsearch(
    account_no="123456",
    statement_from="2025-01-01",
    statement_to="2025-01-31"
)

# Process file upload
meta = UploadService.process_upload(
    file=uploaded_file,
    password="optional_password"
)

# Delete file from storage
success = UploadService.delete_file("statement.pdf")
```

**Key Methods:**

- `check_duplicate_by_name(filename)` - Check if filename exists in storage
- `check_duplicate_by_hash(file_content)` - Check if file content already uploaded
- `check_duplicate_in_elasticsearch(account_no, statement_from, statement_to)` - Check for duplicate statement period
- `validate_files(files)` - Validate uploaded files against constraints
- `process_upload(file, password)` - Save file to storage and return metadata
- `delete_file(filename)` - Delete file from storage backend (local or GCS)

---

## Models

### ParsedStatement

```python
from models.schema import ParsedStatement

parsed = ParsedStatement(
    accountName="John Doe",       # Optional - can be None
    accountNo="123456",
    statementFrom=date(2025, 1, 1),
    statementTo=date(2025, 1, 31),
    bankName="ABC Bank",          # Optional - can be None
    statements=[...]
)
```

**Note:** `accountName` and `bankName` are now optional fields. If not found during parsing, they default to `None` and display as "Unknown" in the UI.

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

