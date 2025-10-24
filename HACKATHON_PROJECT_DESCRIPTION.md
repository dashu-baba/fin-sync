# FinSync - AI-Powered Personal Financial Assistant

## Project Summary

**FinSync** is an intelligent conversational AI platform that transforms how people manage their personal finances. Users simply upload their bank statements (PDFs), and FinSync automatically parses, understands, and indexes transaction data using **Google Cloud's Vertex AI (Gemini models)** and **Elastic's hybrid search** capabilities. The system enables users to ask natural language questions like *"How much did I spend on groceries last month?"* or *"Show me my biggest expenses"* and receive instant, accurate answers with full context and source citations.

Unlike traditional personal finance apps that require manual data entry or rely on simple keyword matching, FinSync combines **semantic understanding** (through vector embeddings), **powerful analytics** (through Elastic's ES|QL engine), and **conversational AI** (through Gemini) to create an intelligent agent that truly understands financial queries and provides actionable insights.

**Live Demo**: https://fin-sync-899361706979.us-central1.run.app

---

## Challenge Addressed

**Elastic Challenge**: Build the Future of AI-Powered Search

FinSync directly addresses this challenge by:

1. **Hybrid Search Implementation**: Combines Elastic's BM25 keyword search with kNN vector search using Reciprocal Rank Fusion (RRF) to find relevant transactions through both exact matches and semantic similarity.

2. **Conversational AI Interface**: Users interact naturally without learning complex query syntax. The AI understands intent, extracts parameters, and routes queries to optimal search strategies.

3. **Agent-Based System**: An intelligent intent classification system acts as an AI agent, automatically determining whether to use aggregations, semantic search, or hybrid approaches based on query type.

4. **Real-World Impact**: Reimagines personal finance management by making financial data accessible through conversation rather than spreadsheets and dashboards.

---

## Features and Functionality

### 🤖 **Intelligent Intent Classification System**

The heart of FinSync is an advanced intent routing system powered by Gemini 2.5 Pro that classifies user queries into specialized handlers:

- **AGGREGATE**: Pure numeric queries (*"Total spending in June 2025"*)
  - Uses Elastic ES|QL for high-performance aggregations
  - Filters by date ranges, transaction types, accounts
  - Returns precise numeric results

- **AGGREGATE_FILTERED_BY_TEXT**: Semantic + structured combo (*"How much did I spend on groceries?"*)
  - Step 1: Semantic search on transaction descriptions using vector embeddings
  - Step 2: Extract matching merchants/keywords from search results
  - Step 3: Aggregate transactions containing those merchants
  - Solves the "meaning-based filtering" problem

- **TEXT_QA**: Question answering (*"What was my largest transaction last month?"*)
  - Retrieves relevant transactions via hybrid search
  - Gemini analyzes results and answers the question
  - Provides source citations with transaction details

- **PROVENANCE**: Source/metadata queries (*"Show all transactions from IFIC Bank"*)
  - Searches statement metadata and account information
  - Returns full context about sources
  - Useful for multi-bank account management

- **CLARIFICATION**: Handles ambiguous queries interactively
  - Detects when critical information is missing
  - Asks targeted clarification questions
  - Re-classifies with additional context

### 📄 **Intelligent Document Processing**

- **PDF Upload**: Drag-and-drop interface for multiple password-protected PDFs
- **Automatic Parsing**: Gemini 2.5 Pro extracts structured data from unstructured statements
- **Schema Validation**: Pydantic models ensure data quality
- **Duplicate Detection**: Multi-layer protection (filename, content hash, metadata checks)
- **Session Management**: Isolated user sessions with automatic cleanup

### 🔍 **Hybrid Search with Elastic**

- **Vector Embeddings**: Uses Vertex AI's `text-embedding-004` (768-dimensional) for semantic search
- **Keyword Matching**: BM25 scoring for exact phrase matches
- **RRF Fusion**: Combines vector and keyword scores for optimal results
- **ES|QL Analytics**: Advanced aggregations and filtering on transaction data
- **Real-time Indexing**: Immediate availability after document processing

### 💬 **Conversational Interface**

- **Natural Language**: Ask questions in plain English
- **Multi-turn Conversations**: Maintains context across queries
- **Interactive Clarifications**: System asks for missing information when needed
- **Source Citations**: Every answer includes references to source transactions
- **Intent Transparency**: Shows detected intent and confidence scores (debug mode)

### 📊 **Interactive Analytics Dashboard**

- **Monthly Trends**: Visualize income, expenses, and balance over time with Plotly
- **Account Breakdown**: Transaction distribution by bank account
- **Balance Evolution**: Track account balance changes
- **Filtering**: Drill down by account, date range, transaction type

### 🔒 **Security & Data Integrity**

- **Encrypted PDFs**: Handles password-protected documents
- **Session Isolation**: User data isolated in session-specific directories
- **Secret Management**: Production credentials stored in GCP Secret Manager
- **No Data Persistence**: Documents can be deleted anytime by users
- **HTTPS Encryption**: All traffic encrypted via Cloud Run

---

## Technologies Used

### Google Cloud Platform

| Component | Technology | Usage |
|-----------|-----------|-------|
| **LLM** | Gemini 2.5 Pro (Vertex AI) | Document parsing, intent classification, answer generation, clarification questions |
| **Embeddings** | text-embedding-004 (Vertex AI) | Generate 768-dimensional semantic vectors for transaction descriptions |
| **Deployment** | Cloud Run | Serverless container platform with auto-scaling |
| **Storage** | Cloud Storage (GCS) | Production file storage with 11 nines durability |
| **Secrets** | Secret Manager | Secure credential management in production |
| **Logging** | Cloud Logging | Centralized application and infrastructure logs |
| **CI/CD** | Cloud Build | Automated deployments from Git |
| **IAM** | Service Accounts | Least-privilege access control |

### Elastic Platform

| Component | Technology | Usage |
|-----------|-----------|-------|
| **Search Engine** | Elastic Cloud 8.15+ | Managed Elasticsearch deployment |
| **Hybrid Search** | BM25 + kNN + RRF | Combines keyword and semantic search |
| **Vector Search** | Dense Vector (768-dim) | Semantic similarity matching |
| **Analytics** | ES\|QL | Fast aggregations and complex queries |
| **Data Streams** | Time-series indices | Optimized transaction storage |
| **Index Lifecycle** | ILM Policies | Automated data retention management |

### Application Stack

| Component | Technology | Usage |
|-----------|-----------|-------|
| **Frontend** | Streamlit 1.39 | Interactive web UI with chat interface |
| **Backend** | Python 3.11 | Core application logic |
| **PDF Processing** | PyPDF2 | Extract text from encrypted PDFs |
| **Schema Validation** | Pydantic v2 | Type-safe data models |
| **Logging** | Loguru | Structured logging framework |
| **Visualization** | Plotly | Interactive charts and graphs |
| **Container** | Docker | Containerized deployment |

### Architecture Pattern

```
User (Streamlit) → Intent Router (Gemini) → Query Executor (Elastic/ES|QL) → Response Generator (Gemini)
                              ↓
                   Embeddings (text-embedding-004)
                              ↓
                   Hybrid Search (Elastic kNN + BM25)
```

---

## Data Sources

### Primary Data Source
**User-Uploaded Bank Statements (PDF)**
- Password-protected PDF files from various banks
- Contain transaction history (credits, debits, balances)
- Include account metadata (bank name, account number, dates)
- Unstructured format requiring AI parsing

### Derived Data

**Structured Transaction Data** (extracted by Gemini):
```json
{
  "accountName": "John Doe",
  "accountNo": 123456789,
  "accountType": "Savings",
  "statementFrom": "2025-01-01",
  "statementTo": "2025-01-31",
  "bankName": "ABC Bank",
  "statements": [
    {
      "statementDate": "2025-01-02",
      "statementAmount": 5000.00,
      "statementType": "credit",
      "statementDescription": "Salary Deposit - ABC Corp",
      "statementBalance": 12500.00,
      "statementNotes": "Monthly salary"
    }
  ]
}
```

**Semantic Embeddings** (generated by text-embedding-004):
- Transaction descriptions vectorized into 768-dimensional embeddings
- Enables semantic search (e.g., "groceries" matches "supermarket", "food mart")
- Indexed in Elastic's dense_vector field type

### Data Flow

1. **Upload**: User uploads PDF → GCS (production) or local storage (development)
2. **Extract**: PyPDF2 extracts raw text from PDF
3. **Parse**: Gemini converts unstructured text to structured JSON
4. **Embed**: Vertex AI generates vector embeddings for descriptions
5. **Index**: Both structured data and embeddings indexed to Elastic
6. **Query**: User asks question → Hybrid search retrieves relevant data
7. **Answer**: Gemini generates natural language response with citations

---

## Findings and Learnings

### Technical Challenges & Solutions

#### 1. **Semantic Filtering for Aggregations**

**Challenge**: Traditional search engines struggle with queries like *"How much did I spend on food?"* because:
- "food" doesn't exactly match "Restaurant XYZ" or "Grocery Store ABC"
- Simple keyword search misses semantically related transactions
- Pure semantic search returns documents, not aggregated sums

**Solution**: Two-phase hybrid approach
1. **Phase 1**: Use Elastic's vector search to find semantically similar transactions (kNN with `text-embedding-004`)
2. **Phase 2**: Extract merchant names from results, then use ES|QL to aggregate by those specific merchants
3. **Result**: Accurate aggregations that understand *meaning*, not just keywords

**Key Learning**: Combining semantic and structured queries solves problems neither can handle alone. This pattern is broadly applicable to any "filter-then-aggregate" use case.

#### 2. **Intent Classification Accuracy**

**Challenge**: Determining user intent from natural language is non-trivial. Early versions frequently misclassified queries, leading to wrong query types and poor results.

**Solution**: Structured prompt engineering with examples
- Provided Gemini with clear intent definitions and 3-5 examples per intent
- Used JSON schema mode for consistent output format
- Added confidence scoring to trigger clarifications when uncertain
- Implemented interactive clarification flow for ambiguous queries

**Key Learning**: LLMs excel at classification when given:
- Clear, distinct categories with specific criteria
- Representative examples covering edge cases
- Structured output formats (JSON schema)
- Fallback mechanisms for uncertainty

#### 3. **Hybrid Search Optimization**

**Challenge**: Balancing semantic relevance with exact matches. Pure vector search sometimes missed exact keywords; pure keyword search missed semantically similar content.

**Solution**: Reciprocal Rank Fusion (RRF)
- Run both BM25 (keyword) and kNN (vector) searches in parallel
- Use Elastic's RRF to combine rankings
- Tune `rank_constant` (60) based on evaluation

**Key Learning**: Hybrid search consistently outperforms either approach alone. The RRF algorithm elegantly handles different score scales without normalization.

#### 4. **Document Parsing Robustness**

**Challenge**: Bank statements vary wildly in format across institutions. Early parsing attempts frequently failed or produced incomplete data.

**Solution**: Iterative prompt refinement
- Started with basic extraction prompt
- Added specific instructions for handling edge cases (merged cells, multi-line descriptions, missing fields)
- Made optional fields in Pydantic schema to handle variations
- Implemented validation with helpful error messages

**Key Learning**: Gemini's multimodal capabilities are powerful but require:
- Clear, specific instructions
- Examples of desired output format
- Flexible schemas that accommodate real-world variations
- Iterative refinement based on failure cases

#### 5. **Elastic Index Design**

**Challenge**: Should we use one index or multiple? What fields should be vectors vs. keywords?

**Solution**: Two-index strategy
- **`finsync-transactions`** (Data Stream): Individual transactions for ES|QL aggregations
- **`finsync-statements`** (Vector Index): Statement-level data for hybrid search

**Key Learning**: Index design should match query patterns:
- Use data streams for time-series data with frequent aggregations
- Use separate vector indices when semantic search is primary use case
- Keep indices focused and optimized for specific access patterns

#### 6. **Cost Management**

**Challenge**: Vertex AI and Elastic Cloud have usage-based pricing. Unoptimized usage could become expensive.

**Solutions Implemented**:
- Use `gemini-2.0-flash-exp` instead of Pro for most tasks (10x cheaper)
- Batch embedding generation for multiple descriptions
- Cache Elastic client connections (don't recreate on every request)
- Minimize prompt length by removing redundant context
- Use ES|QL instead of multiple Elasticsearch queries

**Cost Impact**: Kept monthly GCP costs under $25 for typical usage (100 uploads, 1000 queries)

**Key Learning**: LLM cost optimization is critical:
- Choose appropriate models for each task
- Minimize token usage without sacrificing quality
- Use structured queries (ES|QL) to reduce LLM processing
- Monitor usage with Cloud Logging

#### 7. **Production Deployment**

**Challenge**: Local development vs. production environment differences (storage, secrets, logging).

**Solution**: Environment-aware configuration
- Created abstraction layer for storage (`core/storage.py`)
- Automatic backend switching based on `ENVIRONMENT` variable
- GCP Secret Manager integration for production secrets
- Unified logging that works locally and in Cloud Run

**Key Learning**: Design for portability from day one:
- Abstract external dependencies behind interfaces
- Use environment variables for configuration
- Test both local and cloud scenarios
- Build deployment automation early (don't wait for "production-ready")

#### 8. **User Experience**

**Challenge**: Technical users want control; non-technical users want simplicity.

**Solution**: Progressive disclosure
- Simple chat interface by default
- Optional "debug mode" shows intent classification and confidence
- Interactive clarifications when needed
- Plain English confirmations and error messages

**Key Learning**: Great UX for AI apps means:
- Transparency when needed (show reasoning)
- Simplicity by default (hide complexity)
- Graceful degradation (clarify instead of failing)
- Clear feedback on what the system is doing

### Performance Insights

**Document Processing**: 3-8 seconds per PDF (mostly Gemini parsing time)
**Query Latency**: 
- Simple aggregations: <500ms
- Hybrid search: 1-2 seconds
- Complex text_qa: 2-4 seconds

**Bottlenecks Identified**:
1. Gemini API calls (network + processing)
2. Embedding generation for long descriptions
3. Large result set processing

**Optimization Opportunities**:
- Implement response caching for common queries
- Batch embed generation during indexing
- Use Gemini's streaming API for faster perceived performance
- Add Redis cache layer for frequent aggregations

### What Worked Exceptionally Well

1. **ES|QL for Analytics**: Fast, powerful, and expressive. Much better than traditional Elasticsearch DSL for aggregations.

2. **Gemini's JSON Mode**: Reliable structured output made intent parsing and document extraction robust.

3. **Streamlit for Rapid Iteration**: Built complete UI in days, not weeks. Session state management is excellent.

4. **Cloud Run Serverless**: Zero-configuration auto-scaling. Perfect for this use case.

5. **Hybrid Search**: Consistently better results than either keyword or semantic search alone.

### What Was Harder Than Expected

1. **Query Ambiguity**: Natural language is inherently ambiguous. Clarification flow was necessary but complex to implement.

2. **PDF Format Variations**: Every bank has different statement layouts. Required extensive prompt engineering.

3. **Embedding Dimensionality**: Initially tried 256-dim embeddings (faster/cheaper) but quality was poor. Switched to 768-dim with significant improvement.

4. **Date Handling**: Users say "last month" but system needs exact dates. Implemented date parsing logic but edge cases remain.

5. **Testing with Real Data**: Synthetic data doesn't capture real-world variations. Needed actual bank statements for meaningful testing.

### Key Takeaways

1. **Combine LLMs with Structured Systems**: LLMs excel at understanding intent and generating responses. Traditional databases (Elastic) excel at structured queries and aggregations. The combination is more powerful than either alone.

2. **Invest in Intent Classification**: Getting intent right is 80% of the battle. A good intent system dramatically improves user experience.

3. **Hybrid Search is Essential**: For real-world search applications, hybrid (keyword + semantic) consistently outperforms pure approaches.

4. **Start with Simple, Add Complexity**: Initial version had one intent type. We evolved to five specialized intents based on usage patterns.

5. **User Feedback Drives Design**: Clarification flow came from watching users struggle with ambiguous queries. Debug mode came from power users wanting visibility.

6. **Cloud-Native from Day One**: Starting with Cloud Run, Secret Manager, and GCS saved weeks of refactoring later.

7. **Documentation Matters**: Comprehensive docs (50+ pages) made team collaboration seamless and debugging faster.

---

## Impact & Use Cases

### Real-World Applications

1. **Personal Finance Management**: Users gain insights into spending without manual categorization
2. **Financial Planning**: Identify spending patterns and optimize budgets
3. **Tax Preparation**: Quickly find specific transactions for deductions
4. **Fraud Detection**: Ask "Show unusual transactions" to spot anomalies
5. **Multi-Bank Aggregation**: Unified view across multiple bank accounts

### Scalability Potential

- **Enterprise**: Adapt for corporate expense management
- **Banking**: White-label for banks to offer to customers
- **Financial Advisors**: Tool for analyzing client finances
- **Government**: Track spending for budgeting and auditing

---

## Future Enhancements

- **Multi-user Authentication**: User accounts with Firebase Auth
- **Predictive Analytics**: ML-based spending forecasts
- **Budget Tracking**: Set budgets and receive alerts
- **Export Capabilities**: Generate reports in PDF/Excel
- **Mobile App**: Flutter-based iOS/Android apps
- **Bank API Integration**: Direct connection to banks via Plaid
- **Advanced Privacy**: Customer-managed encryption keys, VPC endpoints

---

## Conclusion

FinSync demonstrates the power of combining **Google Cloud's Vertex AI** with **Elastic's hybrid search** to create an intelligent, conversational AI agent that transforms how people interact with financial data. By leveraging semantic understanding, structured analytics, and natural language interfaces, we've built a system that makes financial insights accessible to everyone—not just data analysts.

The project showcases:
- ✅ **Technical Excellence**: Sophisticated intent routing, hybrid search, and multi-stage query processing
- ✅ **Real-World Applicability**: Solves genuine personal finance pain points
- ✅ **Production-Ready**: Deployed, monitored, and documented for scale
- ✅ **Innovation**: Novel approach to combining semantic and structured queries
- ✅ **User Experience**: Natural, conversational interface with transparency

**FinSync proves that with the right combination of AI and search technology, we can reimagine how people interact with their data—making complex analytics as simple as asking a question.**

---

## Repository & Links

- **GitHub**: https://github.com/dashu-baba/fin-sync
- **Live Demo**: https://fin-sync-899361706979.us-central1.run.app
- **Youtube demo**: https://youtu.be/yPJ0LnAYAl0
- **Documentation**: See `docs/` directory for complete technical documentation
- **License**: MIT (see LICENSE file)

---

**Built with ❤️ using Google Cloud Vertex AI, Elastic Cloud, and Streamlit**

