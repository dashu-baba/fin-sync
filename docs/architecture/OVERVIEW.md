# System Architecture Overview

## Introduction

FinSync is an AI-powered personal finance platform that combines **document understanding**, **semantic search**, and **natural language interfaces** to help users manage their financial data through conversational interactions.

---

## High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                  Streamlit Multi-Page Application               │
│                                                                  │
│  Pages: Ingest (Upload) | Chat (Query) | Analytics (Dashboard) │
└───────────┬──────────────────────────────────────┬─────────────┘
            │                                       │
            │ PDF Upload                            │ Natural Language Query
            ▼                                       ▼
┌─────────────────────────┐           ┌──────────────────────────┐
│   DOCUMENT INGESTION    │           │    QUERY PROCESSING      │
│                         │           │                          │
│  • PDF Reader (PyPDF2)  │           │  • Intent Classification │
│  • Vertex AI Parser     │           │  • Intent Execution      │
│  • Duplicate Detection  │           │  • Clarification Manager │
└──────────┬──────────────┘           └──────────┬───────────────┘
           │                                      │
           │ Structured JSON                      │ Intent + Parameters
           ▼                                      ▼
┌──────────────────────────────────────────────────────────────┐
│                   DATA & SEARCH LAYER                         │
│                                                                │
│  ┌──────────────────────┐      ┌──────────────────────────┐  │
│  │  Elastic Cloud       │      │  Vertex AI (GCP)         │  │
│  │                      │      │                          │  │
│  │  • Transactions      │◄────►│  • Gemini 2.5 Pro       │  │
│  │    (ES|QL Analytics) │      │  • text-embedding-004   │  │
│  │  • Statements        │      │  • Document AI          │  │
│  │    (Vector Search)   │      │                          │  │
│  └──────────────────────┘      └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
           │                                      │
           │ Results + Context                    │ Embeddings
           ▼                                      ▼
┌──────────────────────────────────────────────────────────────┐
│                   RESPONSE GENERATION                         │
│                                                                │
│  • Answer Composition (Vertex AI)                             │
│  • Citation Extraction                                        │
│  • Provenance Tracking                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. **User Interface Layer** (`ui/`)

**Technology**: Streamlit 1.39+

**Structure**:
- **Multi-page app** with session state management
- **Pages**: Ingest, Chat, Analytics
- **Components**: Reusable UI widgets
- **Services**: Business logic abstraction
- **Views**: Page-specific rendering logic

**Key Features**:
- 📤 File upload with drag-and-drop
- 💬 Chat interface with conversation history
- 📊 Interactive analytics dashboard (Plotly)
- 🎯 Real-time intent display
- ❓ Interactive clarification dialogs

### 2. **Document Ingestion Pipeline** (`ingestion/`)

**Flow**:
```
PDF File → Extract Text → Parse with Gemini → Validate Schema → Index to Elastic
```

**Components**:
- **`pdf_reader.py`**: Extract text from PDFs (encrypted support)
- **`parser_vertex.py`**: Use Gemini to extract structured data

**Output Schema**:
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
      "statementType": "credit",
      "statementDescription": "Salary Deposit",
      "statementBalance": 12500.00,
      "statementNotes": null
    }
  ]
}
```

### 3. **Intent Classification System** (`llm/intent_router.py`)

**Purpose**: Understand user intent from natural language queries

**Intents Supported**:
| Intent | Description | Example |
|--------|-------------|---------|
| `aggregate` | Numeric calculations | "Total spending last month" |
| `aggregate_filtered_by_text` | Semantic + structured combo | "Spending on groceries" |
| `text_qa` | Question answering | "What fees are mentioned?" |
| `provenance` | Source lookup | "Show statements about overdraft" |
| `trend` | Time-series analysis | "Monthly spending trend" |
| `listing` | Transaction list | "Show last 10 transactions" |

**Process**:
1. Query → Gemini 2.5 Pro → Intent + Confidence + Filters
2. If confidence < 75% or needs clarification → Interactive dialog
3. Else → Execute intent immediately

### 4. **Search & Analytics Layer** (`elastic/`)

**Two Index Strategy**:

#### **Index 1: `finsync-transactions`** (Data Stream)
- **Purpose**: Individual transactions for aggregations
- **Type**: ES|QL optimized data stream
- **Usage**: Numeric aggregations, filtering, sorting
- **Fields**: date, amount, type, description, balance, accountNo

#### **Index 2: `finsync-statements`** (Vector Index)
- **Purpose**: Statement-level semantic search
- **Type**: Dense vector (768-dim) + keyword
- **Usage**: Hybrid search (BM25 + kNN), Q&A
- **Fields**: accountName, bankName, statementText, desc_vector

**Search Strategies**:
- **ES|QL**: Fast aggregations for structured queries
- **Hybrid Search**: BM25 (keyword) + kNN (semantic) with RRF fusion
- **Nested Queries**: Transaction-level filtering

### 5. **LLM Integration** (`llm/`)

**Models Used**:
- **Gemini 2.5 Pro** (`gemini-2.5-pro`)
  - Intent classification
  - Document parsing
  - Answer generation
  - Clarification questions

- **text-embedding-004** (768-dim)
  - Semantic embeddings for search
  - Description vectorization
  - Similarity matching

**Key Functions**:
- `classify_intent()`: Intent classification
- `classify_intent_with_context()`: Context-aware re-classification
- `compose_aggregate_answer()`: Format numeric results
- `compose_text_qa_answer()`: Generate Q&A responses
- `chat_vertex()`: General chat completion

### 6. **Storage Backend** (`core/storage.py`)

**Abstraction Layer**: Automatically switches between local and cloud storage

| Environment | Backend | Storage Location |
|-------------|---------|------------------|
| Development | `LocalStorage` | `data/uploads/` |
| Production | `GCSStorage` | `gs://bucket-name/` |

**Features**:
- ✅ Unified API for both backends
- ✅ Automatic backend selection
- ✅ Duplicate detection support
- ✅ File listing and management

### 7. **Configuration & Core** (`core/`)

**Modules**:
- **`config.py`**: Pydantic-based configuration with environment detection
- **`logger.py`**: Structured logging (loguru)
- **`secrets.py`**: GCP Secret Manager integration
- **`storage.py`**: Storage backend abstraction
- **`utils.py`**: Common utilities

**Configuration Sources** (priority order):
1. Environment variables
2. `.env.{environment}` file
3. `.env` file
4. Default values

---

## Data Flow Patterns

### 📄 **Pattern 1: Document Upload & Indexing**

```
User uploads PDF
    ↓
Check duplicates (filename, hash, metadata)
    ↓
Extract text with PyPDF2
    ↓
Parse with Gemini → Structured JSON
    ↓
Generate embeddings (text-embedding-004)
    ↓
Index to Elastic Cloud
    ↓
Confirmation to user
```

### 💬 **Pattern 2: Natural Language Query**

```
User enters query: "How much did I spend on groceries?"
    ↓
Classify intent → aggregate_filtered_by_text
    ↓
Extract filters: text="groceries", type="debit"
    ↓
Step 1: Semantic search on statements
    ↓
Step 2: Extract merchants from results
    ↓
Step 3: Aggregate transactions by merchants
    ↓
Compose answer with Gemini
    ↓
Display results + citations
```

### 📊 **Pattern 3: Analytics Dashboard**

```
User opens Analytics page
    ↓
Query Elastic for monthly aggregations
    ↓
Fetch: income, expenses, balance by month
    ↓
Generate Plotly charts
    ↓
Display interactive visualizations
```

---

## Technology Decisions

### Why Streamlit?
- ✅ Rapid UI development
- ✅ Built-in session state management
- ✅ Native Python (no JS needed)
- ✅ Great for data apps
- ❌ Limited customization compared to React

### Why Elastic Cloud?
- ✅ Hybrid search (BM25 + kNN)
- ✅ ES|QL for powerful analytics
- ✅ Vector search built-in
- ✅ Managed service
- ✅ Scalable and fast

### Why Vertex AI (Gemini)?
- ✅ Latest Google AI models
- ✅ Integrated with GCP ecosystem
- ✅ Multimodal capabilities
- ✅ Good JSON output mode
- ✅ Cost-effective

### Why Cloud Run?
- ✅ Serverless (scales to zero)
- ✅ Container-based deployment
- ✅ Integrated with GCP services
- ✅ Pay-per-use pricing
- ✅ Auto-scaling

---

## Security Architecture

### Authentication & Authorization
- **Development**: No auth (localhost only)
- **Production**: Optional Cloud Identity-Aware Proxy (IAP)

### Secret Management
- **Development**: `.env` files (gitignored)
- **Production**: GCP Secret Manager
- **Access Control**: Service account with least privilege

### Data Protection
- **In Transit**: HTTPS/TLS (Cloud Run default)
- **At Rest**: Encrypted by GCS and Elastic
- **Secrets**: Never in code, logs, or version control

### Network Security
- **Cloud Run**: Public or private VPC
- **Elastic Cloud**: API key authentication
- **Vertex AI**: Project-level IAM

---

## Scalability Considerations

### Horizontal Scaling
- **Cloud Run**: Auto-scales based on requests
- **Elastic Cloud**: Managed scaling
- **GCS**: Unlimited storage

### Performance Optimizations
- **Caching**: Session state for UI
- **Batching**: Bulk indexing to Elastic
- **Async**: Background file processing
- **Connection Pooling**: Reuse Elastic clients

### Limits & Quotas
- **Cloud Run**: 1000 concurrent requests/instance
- **Vertex AI**: 60 requests/min (Gemini)
- **Elastic Cloud**: Based on deployment size
- **GCS**: No practical limits

---

## Monitoring & Observability

### Logging
- **Application**: Loguru → stdout → Cloud Logging
- **Structure**: JSON-formatted logs
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Metrics
- **Cloud Run**: Request latency, error rate, CPU, memory
- **Elastic Cloud**: Query performance, index size
- **Custom**: Intent classification confidence, query types

### Tracing (Future)
- **OpenTelemetry**: Distributed tracing
- **Cloud Trace**: Request flow visualization

---

## Future Architecture Considerations

### Potential Enhancements
1. **Redis Cache**: Cache frequent queries
2. **Message Queue**: Async processing (Pub/Sub)
3. **Database**: PostgreSQL for user accounts
4. **CDN**: Cloud CDN for static assets
5. **WAF**: Cloud Armor for DDoS protection
6. **Multi-tenancy**: User isolation and data segregation

### Migration Paths
- **From Elastic → BigQuery**: For long-term analytics
- **From GCS → Cloud SQL**: For relational data
- **From Streamlit → React**: For more custom UI

---

## Conclusion

FinSync's architecture balances:
- **Simplicity**: Minimal components, clear separation
- **Scalability**: Cloud-native, auto-scaling services
- **Cost-Efficiency**: Serverless, pay-per-use
- **Developer Experience**: Python-first, type-safe, well-structured

The modular design allows each component to evolve independently while maintaining clean interfaces.

---

**Next**: [Data Flow Details](./DATA_FLOW.md) | [Tech Stack Deep Dive](./TECH_STACK.md)

