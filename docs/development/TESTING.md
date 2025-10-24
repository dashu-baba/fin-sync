# Testing Guide

Testing strategies and tools for FinSync.

---

## Test Scripts

Located in `scripts/` directory:

```bash
# Intent classification
python scripts/test_intent_router.py

# Aggregate queries
python scripts/test_aggregate_intent.py

# Duplicate protection
python scripts/test_duplicate_protection.py

# Verify index structures
python scripts/verify_aggregate_structure.py
python scripts/verify_text_qa_structure.py
```

---

## Manual Testing

### 1. Upload & Parse

1. Navigate to **Ingest** page
2. Upload test PDF: `data/uploads/test_statement.pdf`
3. Verify:
   - ✅ No duplicate detected
   - ✅ Parsing completes (~5-10s)
   - ✅ Account info displayed
   - ✅ Transaction count shown

### 2. Intent Classification

1. Navigate to **Chat** page
2. Try test queries:
   - "Total spending last month"
   - "Show transactions over $100"
   - "What fees are mentioned?"
3. Verify:
   - ✅ Intent classified correctly
   - ✅ Confidence shown
   - ✅ Filters extracted
   - ✅ Results displayed

### 3. Analytics

1. Navigate to **Analytics** page (future)
2. Verify:
   - ✅ Charts load
   - ✅ Data accurate
   - ✅ Filters work

---

## Automated Testing (Future)

### Unit Tests

```python
# tests/test_config.py
def test_config_loads():
    from core.config import config
    assert config.gcp_project_id is not None

# tests/test_intent_router.py
def test_aggregate_intent():
    from llm.intent_router import classify_intent
    result = classify_intent("Total spending")
    assert result.classification.intent == "aggregate"
```

### Integration Tests

```python
# tests/integration/test_full_flow.py
def test_upload_and_query():
    # Upload file
    result = upload_service.process_upload(test_file)
    assert result["status"] == "success"
    
    # Query data
    intent = classify_intent("Show transactions")
    result = execute_intent("Show transactions", intent)
    assert len(result["data"]) > 0
```

### Run Tests

```bash
# All tests
pytest tests/

# Specific test
pytest tests/test_config.py

# With coverage
pytest --cov=core --cov=elastic --cov=llm
```

---

**Related**: [Setup](./SETUP.md) | [API Reference](./API_REFERENCE.md)

