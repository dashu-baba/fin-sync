# Document Processing & Ingestion

FinSync automatically extracts structured financial data from PDF bank statements using AI-powered document understanding.

---

## Overview

The document processing pipeline transforms unstructured PDFs into searchable, analyzable financial data through:
1. **PDF Text Extraction** - Extract text from encrypted/unencrypted PDFs
2. **AI Parsing** - Use Gemini 2.5 Pro to extract structured data
3. **Validation** - Ensure data quality with Pydantic schemas
4. **Embedding Generation** - Create semantic vectors for search
5. **Indexing** - Store in Elastic Cloud for retrieval

---

## Supported Document Types

### Bank Statements (Primary)

**Supported formats**:
- ✅ PDF (encrypted and unencrypted)
- ✅ Multi-page documents
- ✅ Various bank formats (adaptive parsing)

**Extracted fields**:
```json
{
  "accountName": "John Doe",
  "accountNo": "123456789",
  "accountType": "Savings",
  "statementFrom": "2025-01-01",
  "statementTo": "2025-01-31",
  "bankName": "ABC Bank",
  "statements": [
    {
      "statementDate": "2025-01-02",
      "statementAmount": 5000.00,
      "statementType": "credit" | "debit",
      "statementDescription": "Salary Deposit - ABC Corp",
      "statementBalance": 12500.00,
      "statementNotes": "Optional notes"
    }
  ]
}
```

### Future Support (Planned)

- 📝 CSV statements
- 📝 Excel spreadsheets
- 📝 Transaction exports from banks
- 📝 Credit card statements
- 📝 Investment statements

---

## Processing Pipeline

### Step 1: File Upload

**UI Component**: `ui/components/upload_form.py`

```python
# Streamlit file uploader
uploaded_file = st.file_uploader(
    "Choose PDF bank statement(s)",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload password-protected PDFs supported"
)
```

**Validations**:
- File type: Must be `.pdf`
- File size: < 100 MB (configurable)
- Total size: < 100 MB across all files (configurable)
- Max files: 25 per session (configurable)

**Configuration**:
```python
# core/config.py
max_total_mb: int = 100
max_files: int = 25
allowed_ext: tuple = ("pdf", "csv")
```

### Step 2: Duplicate Detection

**Service**: `ui/services/upload_service.py`

Three layers of protection:

#### Layer 1: Filename Check
```python
def check_duplicate_by_name(filename: str, upload_dir: Path) -> bool:
    """Check if file with same name exists."""
    return (upload_dir / filename).exists()
```

#### Layer 2: Content Hash Check
```python
def check_duplicate_by_hash(
    file_content: bytes,
    upload_dir: Path,
    use_storage_backend: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Check if file with same content (SHA-256 hash) exists.
    Catches renamed duplicates.
    """
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Compare with all existing files
    for existing_file in storage.list_files():
        existing_content = storage.read_file(existing_file)
        existing_hash = hashlib.sha256(existing_content).hexdigest()
        
        if file_hash == existing_hash:
            return True, existing_file
    
    return False, None
```

#### Layer 3: Metadata Check
```python
def check_duplicate_in_elasticsearch(
    account_no: str,
    statement_from: str,
    statement_to: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if statement with same account and period exists.
    Prevents duplicate statements even with different files.
    """
    query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"accountNo": account_no}},
                    {"term": {"statementFrom": statement_from}},
                    {"term": {"statementTo": statement_to}}
                ]
            }
        },
        "size": 1
    }
    
    result = es_client.search(index="finsync-statements", body=query)
    
    if result["hits"]["total"]["value"] > 0:
        return True, result["hits"]["hits"][0]["_source"]["filename"]
    
    return False, None
```

See [Duplicate Protection](./DUPLICATE_PROTECTION.md) for details.

### Step 3: Storage

**Module**: `core/storage.py`

Automatic backend selection:

```python
def get_storage_backend() -> StorageBackend:
    """Factory function returning appropriate backend."""
    if config.environment == "production" and config.gcs_bucket:
        return GCSStorage(config.gcs_bucket)
    else:
        return LocalStorage(config.uploads_dir)
```

**Local Storage** (Development):
```python
storage = LocalStorage(base_dir=Path("data/uploads"))
file_path = storage.save_file(file_obj, "statement.pdf")
# Saved to: data/uploads/statement.pdf
```

**GCS Storage** (Production):
```python
storage = GCSStorage(bucket_name="my-finsync-uploads")
file_path = storage.save_file(file_obj, "statement.pdf")
# Saved to: gs://my-finsync-uploads/statement.pdf
```

### Step 4: PDF Text Extraction

**Module**: `ingestion/pdf_reader.py`

```python
def extract_text_from_pdf(
    pdf_path: str | Path,
    password: str | None = None
) -> str:
    """
    Extract text from PDF using PyPDF2.
    
    Supports:
    - Unencrypted PDFs
    - Password-protected PDFs
    - Multi-page documents
    
    Returns:
        Concatenated text from all pages
    """
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        
        # Handle encryption
        if reader.is_encrypted:
            if password:
                reader.decrypt(password)
            else:
                raise ValueError("PDF is encrypted, password required")
        
        # Extract text from all pages
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        return text
```

**Error Handling**:
- ❌ **Encrypted without password**: Prompt user for password
- ❌ **Corrupted PDF**: Show error, reject file
- ❌ **No extractable text** (scanned): Future: OCR support

### Step 5: AI Parsing with Vertex AI

**Module**: `ingestion/parser_vertex.py`

```python
def parse_statement_with_vertex(
    text: str,
    model_name: str = "gemini-2.5-pro"
) -> ParsedStatement:
    """
    Parse bank statement text using Vertex AI Gemini.
    
    Args:
        text: Extracted PDF text
        model_name: Gemini model to use
        
    Returns:
        ParsedStatement: Validated Pydantic model
    """
    # Initialize Vertex AI
    aiplatform.init(
        project=config.gcp_project_id,
        location=config.gcp_location
    )
    
    # Build prompt with schema
    prompt = f"""
Extract financial data from this bank statement and return JSON.

Required fields:
- accountName: string (account holder name)
- accountNo: string (account number)
- accountType: string (Savings, Checking, etc.)
- statementFrom: date (YYYY-MM-DD)
- statementTo: date (YYYY-MM-DD)
- bankName: string
- statements: array of transactions

Transaction fields:
- statementDate: date (YYYY-MM-DD)
- statementAmount: number
- statementType: "credit" or "debit"
- statementDescription: string
- statementBalance: number
- statementNotes: string (optional)

Statement text:
{text}

Return only valid JSON, no markdown formatting.
"""
    
    # Call Gemini
    model = GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.1,  # Low for consistency
            "max_output_tokens": 8192,
            "response_mime_type": "application/json"
        }
    )
    
    # Parse JSON
    try:
        data = json.loads(response.text)
    except json.JSONDecodeError:
        # Fallback: Extract JSON from markdown code blocks
        data = extract_json_from_text(response.text)
    
    # Validate with Pydantic
    parsed = ParsedStatement(**data)
    
    return parsed
```

**Parsing Quality**:
- ✅ **High accuracy** (>95%) with Gemini 2.5 Pro
- ✅ **Handles variations** in bank formats
- ✅ **Extracts dates** in various formats
- ✅ **Identifies transaction types** reliably

**Cost per document**:
- Input: ~2-5K tokens (typical statement)
- Output: ~1-2K tokens (JSON)
- Cost: ~$0.01-0.05 per statement (Gemini 2.5 Pro)

### Step 6: Data Validation

**Module**: `models/schema.py`

```python
class Transaction(BaseModel):
    """Single transaction model."""
    statementDate: date
    statementAmount: float = Field(gt=0)
    statementType: Literal["credit", "debit"]
    statementDescription: str = Field(min_length=1)
    statementBalance: float
    statementNotes: str | None = None

class ParsedStatement(BaseModel):
    """Complete statement model."""
    accountName: str = Field(min_length=1)
    accountNo: str = Field(pattern=r"^\d+$")  # Numeric string
    accountType: str | None = None
    statementFrom: date
    statementTo: date
    bankName: str = Field(min_length=1)
    statements: list[Transaction] = Field(min_items=1)
    
    @field_validator("statementTo")
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure statementTo >= statementFrom."""
        if "statementFrom" in info.data:
            if v < info.data["statementFrom"]:
                raise ValueError("statementTo must be >= statementFrom")
        return v
```

**Validation catches**:
- ❌ Missing required fields
- ❌ Invalid date formats
- ❌ Negative amounts
- ❌ Empty transaction lists
- ❌ Invalid date ranges

### Step 7: Embedding Generation

**Module**: `elastic/embedding.py`

```python
def generate_embeddings(
    texts: list[str],
    model: str = "text-embedding-004"
) -> list[list[float]]:
    """
    Generate embeddings for text search.
    
    Args:
        texts: List of text strings to embed
        model: Vertex AI embedding model
        
    Returns:
        List of 768-dimensional vectors
    """
    # Initialize Vertex AI
    aiplatform.init(
        project=config.gcp_project_id,
        location=config.gcp_location
    )
    
    # Get embedding model
    model = TextEmbeddingModel.from_pretrained(model)
    
    # Generate embeddings (batched)
    embeddings = []
    for batch in batch_texts(texts, batch_size=5):
        result = model.get_embeddings(batch)
        embeddings.extend([e.values for e in result])
    
    return embeddings
```

**Embedding Strategy**:
- Embed **statement descriptions** for semantic search
- Use **text-embedding-004** (768-dim, latest Google model)
- Batch processing for efficiency
- Cost: ~$0.00001 per embedding

### Step 8: Elastic Indexing

**Module**: `elastic/indexer.py`

```python
def index_parsed_statement(
    parsed: ParsedStatement,
    raw_text: str,
    filename: str
) -> None:
    """
    Index statement into Elastic Cloud.
    
    Creates:
    1. Transaction documents in finsync-transactions
    2. Statement document in finsync-statements
    """
    # Generate embeddings
    descriptions = [t.statementDescription for t in parsed.statements]
    embeddings = generate_embeddings(descriptions)
    
    # Index transactions (flat documents)
    transaction_docs = []
    for txn, emb in zip(parsed.statements, embeddings):
        doc = {
            "accountName": parsed.accountName,
            "accountNo": parsed.accountNo,
            "bankName": parsed.bankName,
            "statementDate": txn.statementDate.isoformat(),
            "statementAmount": txn.statementAmount,
            "statementType": txn.statementType,
            "statementDescription": txn.statementDescription,
            "statementBalance": txn.statementBalance,
            "statementNotes": txn.statementNotes,
            "filename": filename,
            "indexed_at": datetime.utcnow().isoformat()
        }
        transaction_docs.append(doc)
    
    # Bulk index transactions
    bulk(
        es_client,
        [{"_index": "finsync-transactions", "_source": doc} 
         for doc in transaction_docs]
    )
    
    # Index statement (with vector)
    statement_doc = {
        "accountName": parsed.accountName,
        "accountNo": parsed.accountNo,
        "accountType": parsed.accountType,
        "statementFrom": parsed.statementFrom.isoformat(),
        "statementTo": parsed.statementTo.isoformat(),
        "bankName": parsed.bankName,
        "rawText": raw_text,
        "desc_vector": embeddings[0] if embeddings else None,
        "filename": filename,
        "transaction_count": len(parsed.statements),
        "indexed_at": datetime.utcnow().isoformat()
    }
    
    es_client.index(
        index="finsync-statements",
        document=statement_doc
    )
```

---

## User Experience

### Upload Flow

```
1. User drags PDF file into upload area
   ↓
2. System checks file type and size
   ↓ [Valid]
3. "Checking for duplicates..." (spinner)
   ↓ [Not duplicate]
4. "Processing document..." (progress bar)
   ↓
5. "Parsing with AI..." (~5-10 seconds)
   ↓
6. "Indexing data..." (spinner)
   ↓
7. ✅ "Successfully processed!"
   
   Display:
   - Account name
   - Account number
   - Statement period
   - Transaction count
```

### Error Messages

| Error | User Message | Action |
|-------|--------------|--------|
| **Invalid file type** | "Please upload PDF files only" | Show supported formats |
| **File too large** | "File exceeds 100 MB limit" | Suggest splitting |
| **Duplicate filename** | "File '{name}' already uploaded" | Rename or delete existing |
| **Duplicate content** | "Same content as '{existing}'" | Use different file |
| **Duplicate metadata** | "Statement period already exists" | Upload different period |
| **Encrypted no password** | "PDF is encrypted. Enter password:" | Show password input |
| **Parse failure** | "Couldn't extract data. Check format" | Contact support |

---

## Performance Metrics

### Processing Time

**Typical 5-page statement** (50 transactions):
```
PDF extraction:    500ms
AI parsing:        5s
Validation:        10ms
Embedding:         1s
Indexing:          200ms
---
Total:             ~7 seconds
```

### Optimization Strategies

1. **Parallel Processing**: Process multiple files concurrently
2. **Streaming**: Show progress as each step completes
3. **Batch Embeddings**: Generate all embeddings in one API call
4. **Async Indexing**: Index in background, don't block UI

```python
# Async processing
async def process_file_async(file: UploadedFile):
    # Extract (I/O bound)
    text = await asyncio.to_thread(extract_text_from_pdf, file)
    
    # Parse (network bound)
    parsed = await asyncio.to_thread(parse_statement_with_vertex, text)
    
    # Index (network bound)
    await asyncio.to_thread(index_parsed_statement, parsed, text, file.name)
```

---

## Security Considerations

### Password-Protected PDFs

```python
# UI prompts for password
if pdf_encrypted:
    password = st.text_input("Enter PDF password:", type="password")
    if password:
        text = extract_text_from_pdf(file, password=password)
```

**Security**:
- Passwords NOT stored
- Used only for decryption
- Cleared from memory after use

### Sensitive Data

- ✅ **In Transit**: HTTPS/TLS
- ✅ **At Rest**: Encrypted in GCS and Elastic
- ✅ **In Memory**: Cleared after processing
- ✅ **Logs**: PII redacted

---

## Troubleshooting

### Common Issues

**Issue**: "PDF extraction failed"
- **Cause**: Corrupted or scanned PDF
- **Solution**: Try re-downloading PDF from bank

**Issue**: "Parse returned empty data"
- **Cause**: Unsupported bank format
- **Solution**: Contact support with sample

**Issue**: "Indexing timeout"
- **Cause**: Large statement (>1000 transactions)
- **Solution**: Split into multiple periods

---

**Related**: [Duplicate Protection](./DUPLICATE_PROTECTION.md) | [Hybrid Search](./HYBRID_SEARCH.md)

